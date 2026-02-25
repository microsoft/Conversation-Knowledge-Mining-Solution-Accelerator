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

from agent_framework.azure import AzureAIProjectAgentProvider

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
            complete_response = ""
            try:
                if not query:
                    query = "Please provide a query."

                # Create provider for agent management
                provider = AzureAIProjectAgentProvider(project_client=project_client)

                custom_tool = SQLTool(conn=await get_sqldb_connection())

                thread_conversation_id = None
                cache = self.get_thread_cache()
                thread_conversation_id = cache.get(conversation_id, None)

                # Get agent with tools using provider
                agent = await provider.get_agent(
                    name=self.orchestrator_agent_name,
                    tools=custom_tool.get_sql_response
                )

                citations = []
                first_chunk = True
                citation_marker_map = {}  # Maps original markers to sequential numbers
                citation_counter = 0

                if not thread_conversation_id:
                    # Create a conversation using OpenAI client for conversation continuity
                    openai_client = project_client.get_openai_client()
                    conversation = await openai_client.conversations.create()
                    thread_conversation_id = conversation.id

                def replace_citation_marker(match):
                    nonlocal citation_counter
                    marker = match.group(0)
                    if marker not in citation_marker_map:
                        citation_counter += 1
                        citation_marker_map[marker] = citation_counter
                    return f"[{citation_marker_map[marker]}]"

                async for chunk in agent.run(query, stream=True, conversation_id=thread_conversation_id):
                    # Collect citations from Azure AI Search responses
                    for content in getattr(chunk, "contents", []):
                        annotations = getattr(content, "annotations", [])
                        if annotations:
                            citations.extend(annotations)

                    chunk_text = str(chunk.text) if chunk.text else ""

                    # Replace complete citation markers like 【4:0†source】 with [1], [2], etc.
                    chunk_text = re.sub(r'【\d+:\d+†[^】]+】', replace_citation_marker, chunk_text)

                    if chunk_text:
                        if first_chunk:
                            first_chunk = False
                            yield "{ \"answer\": " + chunk_text
                        else:
                            complete_response += chunk_text
                            yield chunk_text

                cache[conversation_id] = thread_conversation_id

                if citations:
                    # Use dict to track unique citations by title to avoid duplicates
                    unique_citations = {}
                    for citation in citations:
                        get_url = (citation.get("additional_properties") or {}).get("get_url")
                        url = get_url if get_url else 'N/A'
                        title = citation.get('title', 'N/A')
                        # Use title as key to ensure uniqueness
                        if title not in unique_citations:
                            unique_citations[title] = {"url": url, "title": title}

                    # Sort by title and convert to JSON string format
                    citation_list = [
                        f"{{\"url\": \"{item['url']}\", \"title\": \"{item['title']}\"}}"
                        for item in sorted(unique_citations.values(), key=lambda x: x['title'])
                    ]
                    yield ", \"citations\": [" + ",".join(citation_list) + "]}"
                else:
                    yield ", \"citations\": []}"

            except Exception as e:
                complete_response = str(e)
                logger.error("Error in stream_openai_text: %s", e)
                cache = self.get_thread_cache()
                thread_conversation_id = cache.pop(conversation_id, None)
                if thread_conversation_id is not None:
                    corrupt_key = f"{conversation_id}_corrupt_{random.randint(1000, 9999)}"
                    cache[corrupt_key] = thread_conversation_id

                # Provide user-friendly error messages
                error_message = str(e).lower()
                if "too many requests" in error_message or "429" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="The service is currently experiencing high demand. Please try again in a few moments."
                    ) from e
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="An error occurred while processing the request."
                    ) from e

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

            except Exception as e:
                logger.error("Unexpected error: %s", e)
                # Extract user-friendly message from HTTPException if available
                if isinstance(e, HTTPException):
                    error_message = e.detail
                else:
                    error_message = "An error occurred while processing the request."
                error_response = {"error": error_message}
                yield json.dumps(error_response) + "\n\n"

        return generate()
