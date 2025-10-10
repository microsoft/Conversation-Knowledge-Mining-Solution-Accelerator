"""
Provides the ChatService class and related utilities for handling chat interactions,
streaming responses, RAG (Retrieval-Augmented Generation) processing, and chart data
generation for visualization in a call center knowledge mining solution.

Includes thread management, caching, and integration with Azure OpenAI and FastAPI.
"""

import json
import logging
import time
import uuid
from types import SimpleNamespace
import asyncio
import re
import pyodbc

from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from azure.ai.projects.aio import AIProjectClient
from agent_framework import ChatAgent, HostedFileSearchTool
from agent_framework.azure import AzureAIAgentClient
from agent_framework.exceptions import ServiceResponseException

from cachetools import TTLCache

from common.database.sqldb_service import get_db_connection
from helpers.utils import format_stream_response
from helpers.azure_credential_utils import get_azure_credential_async
from common.config.config import Config

# Constants
HOST_NAME = "CKM"
HOST_INSTRUCTIONS = "Answer questions about call center operations"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExpCache(TTLCache):
    """Extended TTLCache that deletes Azure AI agent threads when items expire."""
 
    def __init__(self, *args, **kwargs):
        """Initialize cache with optional project client for thread cleanup."""
        super().__init__(*args, **kwargs)
        config = Config()
        self.project_client = AIProjectClient(
            endpoint=config.ai_project_endpoint,
            credential=get_azure_credential_async()
        )
 
    def expire(self, time=None):
        """Remove expired items and delete associated Azure AI threads."""
        items = super().expire(time)
        for key, thread_id in items:
            try:
                if self.project_client:
                    asyncio.create_task(self._delete_thread_async(thread_id))
                    logger.info("Thread deleted: %s", thread_id)
            except Exception as e:
                logger.error("Failed to delete thread for key %s: %s", key, e)
        return items
 
    def popitem(self):
        """Remove item using LRU eviction and delete associated Azure AI thread."""
        key, thread_id = super().popitem()
        try:
            if self.project_client:
                asyncio.create_task(self._delete_thread_async(thread_id))
                logger.info("Thread deleted (LRU evict): %s", thread_id)
        except Exception as e:
            logger.error("Failed to delete thread for key %s (LRU evict): %s", key, e)
        return key, thread_id
 
    async def _delete_thread_async(self, thread_id: str):
        """Asynchronously delete a thread using the Azure AI Project Client."""
        try:
            if self.project_client and thread_id:
                await self.project_client.agents.threads.delete(thread_id=thread_id)
        except Exception as e:
            logger.error("Failed to delete thread %s: %s", thread_id, e)

class SQLTool(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    conn: pyodbc.Connection

    async def get_sql_response(self, sql_query: str) -> str:
        cursor = None
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql_query)
            result = ''.join(str(row) for row in cursor.fetchall())
            return result
        except Exception as e:
            logging.error("Error executing SQL query: %s", e)
            return f"Error executing SQL query: {str(e)}"
        finally:
            if cursor:
                cursor.close()

class ChatService:
    """
    Service for handling chat interactions, including streaming responses,
    processing RAG responses, and generating chart data for visualization.
    """

    thread_cache = None

    def __init__(self, request : Request):
        config = Config()
        self.azure_openai_deployment_name = config.azure_openai_deployment_model
        self.agent = request.app.state.conversation_agent

        if ChatService.thread_cache is None:
            ChatService.thread_cache = ExpCache(maxsize=1000, ttl=3600.0)

    async def stream_openai_text(self, conversation_id: str, query: str) -> StreamingResponse:
        """
        Get a streaming text response from OpenAI.
        """
        thread = None
        try:
            if not query:
                query = "Please provide a query."

            thread_id = None

            config = Config()
            # Correctly await the credential before using it
            credential = await get_azure_credential_async()
            client = AIProjectClient(endpoint=config.ai_project_endpoint, credential=credential)
            
            try:
                custom_tool = SQLTool(conn=await get_db_connection())

                search_tool = HostedFileSearchTool(
                    additional_properties={
                        "index_name": config.azure_ai_search_index,
                        "query_type": "simple",
                        "top_k": 5
                    }
                )

                my_tools = [custom_tool.get_sql_response, search_tool]

                agent_ai_client = AzureAIAgentClient(
                    project_client=client,
                    agent_id=self.agent.id,
                    project_endpoint=config.ai_project_endpoint
                )
                
                async with ChatAgent(
                    chat_client=agent_ai_client,
                    tools=my_tools,
                    tool_choice="auto",
                    project_endpoint=config.ai_project_endpoint,
                    model_id=config.azure_openai_deployment_model,
                ) as agent:
                    if ChatService.thread_cache is not None:
                        thread_id = ChatService.thread_cache.get(conversation_id, None)
                    if thread_id:
                        thread = agent.get_new_thread(service_thread_id=thread_id)
                    else:
                        service_thread = await client.agents.threads.create()
                        thread = agent.get_new_thread(service_thread_id=service_thread.id)

                    async for response in agent.run_stream(messages=query, thread=thread):
                        yield response.text

            finally:
                # Close the client properly after use
                await client.close()

        except ServiceResponseException as e:
            if "Rate limit is exceeded" in str(e):
                logger.error("Rate limit error: %s", e)
                retry_time = 60
                match = re.search(r"Try again in (\d+) seconds", str(e))
                if match:
                    retry_time = int(match.group(1))
                raise ServiceResponseException(f"Rate limit is exceeded. Please try again in {retry_time} seconds.") from e
            else:
                logger.error("RuntimeError: %s", e)
                raise ServiceResponseException(f"An unexpected runtime error occurred: {str(e)}") from e

        except Exception as e:
            logger.error("Error in stream_openai_text: %s", e)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error streaming OpenAI text") from e

    async def stream_chat_request(self, request_body, conversation_id, query):
        """
        Handles streaming chat requests.
        """
        history_metadata = request_body.get("history_metadata", {})

        async def generate():
            try:
                assistant_content = ""
                async for chunk in self.stream_openai_text(conversation_id, query):
                    if isinstance(chunk, dict):
                        chunk = json.dumps(chunk)  # Convert dict to JSON string
                    assistant_content += str(chunk)

                    if assistant_content:
                        chat_completion_chunk = {
                            "id": "",
                            "model": "",
                            "created": 0,
                            "object": "",
                            "choices": [
                                {
                                    "messages": [],
                                    "delta": {},
                                }
                            ],
                            "history_metadata": history_metadata,
                            "apim-request-id": "",
                        }

                        chat_completion_chunk["id"] = str(uuid.uuid4())
                        chat_completion_chunk["model"] = "rag-model"
                        chat_completion_chunk["created"] = int(time.time())
                        chat_completion_chunk["object"] = "extensions.chat.completion.chunk"
                        chat_completion_chunk["choices"][0]["messages"].append(
                            {"role": "assistant", "content": assistant_content}
                        )
                        chat_completion_chunk["choices"][0]["delta"] = {
                            "role": "assistant",
                            "content": assistant_content,
                        }

                        completion_chunk_obj = json.loads(
                            json.dumps(chat_completion_chunk),
                            object_hook=lambda d: SimpleNamespace(**d),
                        )
                        yield json.dumps(format_stream_response(completion_chunk_obj, history_metadata, "")) + "\n\n"

            except ServiceResponseException as e:
                error_message = str(e)
                retry_after = "sometime"
                if "Rate limit is exceeded" in error_message:
                    match = re.search(r"Try again in (\d+) seconds", error_message)
                    if match:
                        retry_after = f"{match.group(1)} seconds"
                    logger.error("Rate limit error: %s", error_message)
                    yield json.dumps({"error": f"Rate limit is exceeded. Try again in {retry_after}."}) + "\n\n"
                else:
                    logger.error("ServiceResponseException: %s", error_message)
                    yield json.dumps({"error": "An error occurred. Please try again later."}) + "\n\n"
            except Exception as e:
                logger.error("Error in stream_chat_request: %s", e, exc_info=True)
                yield json.dumps({"error": "An error occurred while processing the request."}) + "\n\n"

        return generate()
