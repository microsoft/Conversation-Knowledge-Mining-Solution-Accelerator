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
import random
import re

from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse

from semantic_kernel.agents import AzureAIAgentThread
from semantic_kernel.exceptions.agent_exceptions import AgentException

from azure.ai.agents.models import TruncationObject

from cachetools import TTLCache

from helpers.utils import format_stream_response
from common.config.config import Config

# Constants
HOST_NAME = "CKM"
HOST_INSTRUCTIONS = "Answer questions about call center operations"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExpCache(TTLCache):
    """
    Extended TTLCache that associates an agent and deletes Azure AI agent threads when items expire or are evicted (LRU).
    """
    def __init__(self, *args, agent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = agent

    def expire(self, time=None):
        items = super().expire(time)
        for key, thread_id in items:
            try:
                if self.agent:
                    thread = AzureAIAgentThread(client=self.agent.client, thread_id=thread_id)
                    asyncio.create_task(thread.delete())
                    print(f"Thread deleted : {thread_id}")
            except Exception as e:
                logger.error("Failed to delete thread for key %s: %s", key, e)
        return items

    def popitem(self):
        key, thread_id = super().popitem()
        try:
            if self.agent:
                thread = AzureAIAgentThread(client=self.agent.client, thread_id=thread_id)
                asyncio.create_task(thread.delete())
                print(f"Thread deleted (LRU evict): {thread_id}")
        except Exception as e:
            logger.error("Failed to delete thread for key %s (LRU evict): %s", key, e)
        return key, thread_id


class ChatService:
    """
    Service for handling chat interactions, including streaming responses,
    processing RAG responses, and generating chart data for visualization.
    """

    thread_cache = None

    def __init__(self, request : Request):
        config = Config()
        self.azure_openai_deployment_name = config.azure_openai_deployment_model
        self.agent = request.app.state.agent

        if ChatService.thread_cache is None:
            ChatService.thread_cache = ExpCache(maxsize=1000, ttl=3600.0, agent=self.agent)

    async def stream_openai_text(self, conversation_id: str, query: str) -> StreamingResponse:
        """
        Get a streaming text response from OpenAI.
        """
        thread = None
        complete_response = ""
        try:
            if not query:
                query = "Please provide a query."

            thread_id = None
            if ChatService.thread_cache is not None:
                thread_id = ChatService.thread_cache.get(conversation_id, None)
            if thread_id:
                thread = AzureAIAgentThread(client=self.agent.client, thread_id=thread_id)

            truncation_strategy = TruncationObject(type="last_messages", last_messages=4)

            async for response in self.agent.invoke_stream(messages=query, thread=thread, truncation_strategy=truncation_strategy):
                if ChatService.thread_cache is not None:
                    ChatService.thread_cache[conversation_id] = response.thread.id
                complete_response += str(response.content)
                yield response.content

        except RuntimeError as e:
            complete_response = str(e)
            if "Rate limit is exceeded" in str(e):
                logger.error("Rate limit error: %s", e)
                raise AgentException(f"Rate limit is exceeded. {str(e)}") from e
            else:
                logger.error("RuntimeError: %s", e)
                raise AgentException(f"An unexpected runtime error occurred: {str(e)}") from e

        except Exception as e:
            complete_response = str(e)
            logger.error("Error in stream_openai_text: %s", e)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error streaming OpenAI text") from e

        finally:
            # Provide a fallback response when no data is received from OpenAI.
            if complete_response == "":
                logger.info("No response received from OpenAI.")
                thread_id = None
                if ChatService.thread_cache is not None:
                    thread_id = ChatService.thread_cache.pop(conversation_id, None)
                    if thread_id is not None:
                        corrupt_key = f"{conversation_id}_corrupt_{random.randint(1000, 9999)}"
                        ChatService.thread_cache[corrupt_key] = thread_id
                yield "I cannot answer this question with the current data. Please rephrase or add more details."

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

            except AgentException as e:
                error_message = str(e)
                retry_after = "sometime"
                if "Rate limit is exceeded" in error_message:
                    match = re.search(r"Try again in (\d+) seconds", error_message)
                    if match:
                        retry_after = f"{match.group(1)} seconds"
                    logger.error("Rate limit error: %s", error_message)
                    yield json.dumps({"error": f"Rate limit is exceeded. Try again in {retry_after}."}) + "\n\n"
                else:
                    logger.error("AgentInvokeException: %s", error_message)
                    yield json.dumps({"error": "An error occurred. Please try again later."}) + "\n\n"

            except Exception as e:
                logger.error("Error in stream_chat_request: %s", e, exc_info=True)
                yield json.dumps({"error": "An error occurred while processing the request."}) + "\n\n"

        return generate()
