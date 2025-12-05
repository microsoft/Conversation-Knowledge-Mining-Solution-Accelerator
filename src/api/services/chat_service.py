"""
Provides the ChatService class and related utilities for handling chat interactions,
streaming responses, RAG (Retrieval-Augmented Generation) processing, and chart data
generation for visualization in a call center knowledge mining solution.

Includes thread management, caching, and integration with Azure OpenAI and FastAPI.
"""

import asyncio
import json
import logging
import random
import re

from helpers.azure_credential_utils import get_azure_credential_async
from common.database.sqldb_service import SQLTool, get_db_connection as get_sqldb_connection

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from azure.ai.projects.aio import AIProjectClient

from agent_framework import ChatAgent
from agent_framework.azure import AzureAIClient
from agent_framework.exceptions import ServiceResponseException

from cachetools import TTLCache

from common.config.config import Config

# Constants
HOST_NAME = "CKM"
HOST_INSTRUCTIONS = "Answer questions about call center operations"

logger = logging.getLogger(__name__)


class ExpCache(TTLCache):
    """Extended TTLCache that deletes Azure AI agent threads when items expire."""

    def __init__(self, *args, **kwargs):
        """Initialize cache without creating persistent client connections."""
        super().__init__(*args, **kwargs)

    def expire(self, time=None):
        """Remove expired items and delete associated Azure AI threads."""
        items = super().expire(time)
        for key, thread_conversation_id in items:
            try:
                # Create task for async deletion with proper session management
                asyncio.create_task(self._delete_thread_async(thread_conversation_id))
                logger.info("Scheduled thread deletion: %s", thread_conversation_id)
            except Exception as e:
                logger.error("Failed to schedule thread deletion for key %s: %s", key, e)
        return items

    def popitem(self):
        """Remove item using LRU eviction and delete associated Azure AI thread."""
        key, thread_conversation_id = super().popitem()
        try:
            # Create task for async deletion with proper session management
            asyncio.create_task(self._delete_thread_async(thread_conversation_id))
            logger.info("Scheduled thread deletion (LRU evict): %s", thread_conversation_id)
        except Exception as e:
            logger.error("Failed to schedule thread deletion for key %s (LRU evict): %s", key, e)
        return key, thread_conversation_id

    async def _delete_thread_async(self, thread_conversation_id: str):
        """Asynchronously delete a thread using a properly managed Azure AI Project Client."""
        credential = None
        config = Config()
        try:
            if thread_conversation_id:
                # Get credential and use async context managers to ensure proper cleanup
                credential = await get_azure_credential_async(client_id=config.azure_client_id)
                async with AIProjectClient(
                    endpoint=config.ai_project_endpoint,
                    credential=credential
                ) as project_client:
                    openai_client = project_client.get_openai_client()
                    await openai_client.conversations.delete(conversation_id=thread_conversation_id)
                    logger.info("Thread deleted successfully: %s", thread_conversation_id)
        except Exception as e:
            logger.error("Failed to delete thread %s: %s", thread_conversation_id, e)
        finally:
            # Close credential to prevent unclosed client session warnings
            if credential is not None:
                await credential.close()


thread_cache = None


class ChatService:
    """
    Service for handling chat interactions, including streaming responses,
    processing RAG responses, and generating chart data for visualization.
    """

    def __init__(self):
        config = Config()
        self.azure_openai_deployment_name = config.azure_openai_deployment_model
        self.orchestrator_agent_name = config.orchestrator_agent_name
        self.azure_client_id = config.azure_client_id
        self.ai_project_endpoint = config.ai_project_endpoint

    def get_thread_cache(self):
        """Get or create the global thread cache."""
        global thread_cache
        if thread_cache is None:
            thread_cache = ExpCache(maxsize=1000, ttl=3600.0)
        return thread_cache

    async def stream_openai_text(self, conversation_id: str, query: str) -> StreamingResponse:
        """
        Get a streaming text response from OpenAI.
        """
        async with (
            await get_azure_credential_async(client_id=self.azure_client_id) as credential,
            AIProjectClient(endpoint=self.ai_project_endpoint, credential=credential) as project_client,
        ):
            thread = None
            complete_response = ""
            try:
                if not query:
                    query = "Please provide a query."

                # Create chat client with existing agent
                chat_client = AzureAIClient(
                    project_client=project_client,
                    agent_name=self.orchestrator_agent_name,
                    use_latest_version=True,
                )

                custom_tool = SQLTool(conn=await get_sqldb_connection())
                my_tools = [custom_tool.get_sql_response]

                thread_conversation_id = None
                cache = self.get_thread_cache()
                thread_conversation_id = cache.get(conversation_id, None)

                async with ChatAgent(
                    chat_client=chat_client,
                    tools=my_tools,
                    tool_choice="auto",
                    store=True,
                ) as chat_agent:
                    citations = []
                    first_chunk = True

                    if thread_conversation_id:
                        thread = chat_agent.get_new_thread(service_thread_id=thread_conversation_id)
                    else:
                        # Create a conversation using OpenAI client
                        openai_client = project_client.get_openai_client()
                        conversation = await openai_client.conversations.create()
                        thread_conversation_id = conversation.id
                        thread = chat_agent.get_new_thread(service_thread_id=thread_conversation_id)

                    async for chunk in chat_agent.run_stream(messages=query, thread=thread):
                        # # Collect citations from Azure AI Search responses
                        # if hasattr(chunk, "contents") and chunk.contents:
                        #     for content in chunk.contents:
                        #         if hasattr(content, "annotations") and content.annotations:
                        #             citations.extend(content.annotations)

                        if first_chunk:
                            if chunk is not None and chunk.text != "":
                                first_chunk = False
                                yield "{ \"answer\": " + str(chunk.text)
                        else:
                            complete_response += str(chunk.text)
                            yield str(chunk.text)

                    cache[conversation_id] = thread_conversation_id

                    if citations:
                        citation_list = [f"{{\"url\": \"{citation.url}\", \"title\": \"{citation.title}\"}}" for citation in citations]
                        yield ", \"citations\": [" + ",".join(citation_list) + "]}"
                    else:
                        yield ", \"citations\": []}"

            except ServiceResponseException as e:
                complete_response = str(e)
                if "Rate limit is exceeded" in str(e):
                    logger.error("Rate limit error: %s", e)
                    raise ServiceResponseException(f"Rate limit is exceeded. {str(e)}") from e
                else:
                    logger.error("RuntimeError: %s", e)
                    raise ServiceResponseException(f"An unexpected runtime error occurred: {str(e)}") from e

            except Exception as e:
                complete_response = str(e)
                logger.error("Error in stream_openai_text: %s", e)
                cache = self.get_thread_cache()
                thread_conversation_id = cache.pop(conversation_id, None)
                if thread_conversation_id is not None:
                    corrupt_key = f"{conversation_id}_corrupt_{random.randint(1000, 9999)}"
                    cache[corrupt_key] = thread_conversation_id
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error streaming OpenAI text") from e

            finally:
                # Provide a fallback response when no data is received from OpenAI.
                if complete_response == "":
                    logger.info("No response received from OpenAI.")
                    yield "I cannot answer this question with the current data. Please rephrase or add more details."

    async def stream_chat_request(self, conversation_id, query):
        """
        Handles streaming chat requests.
        """

        async def generate():
            try:
                assistant_content = ""
                async for chunk in self.stream_openai_text(conversation_id, query):
                    if isinstance(chunk, dict):
                        chunk = json.dumps(chunk)  # Convert dict to JSON string
                    assistant_content += str(chunk)

                    if assistant_content:
                        # Optimized response - only send fields used by frontend
                        response = {
                            "choices": [
                                {
                                    "messages": [
                                        {"role": "assistant", "content": assistant_content}
                                    ]
                                }
                            ]
                        }
                        yield json.dumps(response) + "\n\n"

            except ServiceResponseException as e:
                error_message = str(e)
                retry_after = "sometime"
                if "Rate limit is exceeded" in error_message:
                    match = re.search(r"Try again in (\d+) seconds.", error_message)
                    if match:
                        retry_after = f"{match.group(1)} seconds"
                    logger.error("Rate limit error: %s", error_message)
                    yield json.dumps({"error": f"Rate limit is exceeded. Try again in {retry_after}."}) + "\n\n"
                else:
                    logger.error("ServiceResponseException: %s", error_message)
                    yield json.dumps({"error": "An error occurred. Please try again later."}) + "\n\n"

            except Exception as e:
                logger.error("Unexpected error: %s", e)
                error_response = {"error": "An error occurred while processing the request."}
                yield json.dumps(error_response) + "\n\n"

        return generate()
