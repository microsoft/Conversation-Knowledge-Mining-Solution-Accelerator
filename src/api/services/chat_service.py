"""
Provides the ChatService class and related utilities for handling chat interactions,
streaming responses, RAG (Retrieval-Augmented Generation) processing, and chart data
generation for visualization in a call center knowledge mining solution.

Includes thread management, caching, and integration with Azure OpenAI and FastAPI.
"""

import asyncio
import json
import logging
import os
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

# Suppress informational warnings from agent_framework about runtime
# tool/structured_output overrides not being supported by AzureAIClient.
# This can be made configurable via env var if needed for debugging.
agent_log_level = os.getenv("AGENT_FRAMEWORK_LOG_LEVEL", "ERROR").upper()
logging.getLogger("agent_framework.azure").setLevel(getattr(logging, agent_log_level, logging.ERROR))


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
        logger.info("stream_openai_text called: conversation_id=%s, query_length=%d",
                    conversation_id, len(query) if query else 0)
        async with (
            await get_azure_credential_async(client_id=self.azure_client_id) as credential,
            AIProjectClient(endpoint=self.ai_project_endpoint, credential=credential) as project_client,
        ):
            complete_response = ""
            db_conn = None
            try:
                if not query:
                    query = "Please provide a query."

                # Create provider for agent management
                provider = AzureAIProjectAgentProvider(project_client=project_client)

                db_conn = await get_sqldb_connection()
                custom_tool = SQLTool(conn=db_conn)

                thread_conversation_id = None
                cache = self.get_thread_cache()
                thread_conversation_id = cache.get(conversation_id, None)
                if thread_conversation_id:
                    logger.info("Reusing existing thread %s for conversation %s",
                                thread_conversation_id, conversation_id)

                # Get agent with tools using provider
                logger.info("Retrieving orchestrator agent: '%s'", self.orchestrator_agent_name)
                agent = await provider.get_agent(
                    name=self.orchestrator_agent_name,
                    tools=custom_tool.get_sql_response
                )
                logger.info("Orchestrator agent retrieved successfully: '%s'", self.orchestrator_agent_name)

                citations = []
                first_chunk = True
                citation_marker_map = {}  # Maps original markers to sequential numbers
                citation_counter = 0

                if not thread_conversation_id:
                    # Create a conversation using OpenAI client for conversation continuity
                    logger.info("No existing thread found, creating new thread for conversation %s", conversation_id)
                    openai_client = project_client.get_openai_client()
                    conversation = await openai_client.conversations.create()
                    thread_conversation_id = conversation.id
                    logger.info("New thread created: %s for conversation %s", thread_conversation_id, conversation_id)

                def replace_citation_marker(match):
                    nonlocal citation_counter
                    marker = match.group(0)
                    if marker not in citation_marker_map:
                        citation_counter += 1
                        citation_marker_map[marker] = citation_counter
                    return f"[{citation_marker_map[marker]}]"

                logger.info("Starting agent.run stream for conversation %s, thread %s",
                            conversation_id, thread_conversation_id)
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
                        complete_response += chunk_text
                        if first_chunk:
                            first_chunk = False
                            logger.info("First chunk received for conversation %s, streaming response", conversation_id)
                            yield "{ \"answer\": " + chunk_text
                        else:
                            yield chunk_text

                logger.info("Streaming complete for conversation %s: response_length=%d, citation_count=%d",
                            conversation_id, len(complete_response), len(citations))
                cache[conversation_id] = thread_conversation_id

                if citations:
                    citation_list = []
                    seen_doc_ids = set()  # Track unique document IDs to avoid duplicates

                    for citation in citations:
                        get_url = (citation.get("additional_properties") or {}).get("get_url")
                        url = get_url if get_url else 'N/A'
                        title = citation.get('title', 'N/A')

                        # Extract document ID from the get_url to use as a more meaningful title
                        doc_id = None
                        if get_url and title.startswith('doc_'):
                            # URL format: .../indexes/{index_name}/docs/{document_id}?api-version=...
                            match = re.search(r'/docs/([^?]+)', get_url)
                            if match:
                                doc_id = match.group(1)
                                title = doc_id

                        # Skip duplicate citations based on document ID
                        if doc_id and doc_id in seen_doc_ids:
                            continue

                        if doc_id:
                            seen_doc_ids.add(doc_id)

                        citation_list.append(json.dumps({"url": url, "title": title}))
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
                # Close the DB connection to prevent connection leaks
                if db_conn is not None:
                    try:
                        db_conn.close()
                    except Exception:
                        pass
                # Provide a fallback response when no data is received from OpenAI.
                if complete_response == "":
                    logger.info("No response received from OpenAI.")
                    yield "I cannot answer this question with the current data. Please rephrase or add more details."

    async def stream_chat_request(self, conversation_id, query):
        """
        Handles streaming chat requests.
        """
        logger.info("stream_chat_request called: conversation_id=%s", conversation_id)

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
