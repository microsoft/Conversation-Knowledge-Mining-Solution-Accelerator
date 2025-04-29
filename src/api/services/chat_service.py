import json
import logging
import time
import uuid

import aiohttp
import openai
from cachetools import TTLCache
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from azure.ai.projects.models import AzureAISearchTool, ConnectionType
from azure.identity.aio import DefaultAzureCredential

from semantic_kernel.agents import AzureAIAgent, AzureAIAgentThread
from semantic_kernel.exceptions.agent_exceptions import AgentInvokeException
from semantic_kernel.contents import StreamingChatMessageContent, StreamingAnnotationContent, StreamingTextContent


from common.config.config import Config
from helpers.utils import format_stream_response

from plugins.chat_with_data_plugin import ChatWithDataPlugin
from services.memory_service import MemoryService
from dotenv import load_dotenv

load_dotenv()

# Constants
HOST_NAME = "CKM"
HOST_INSTRUCTIONS = "Answer questions about call center operations"
MEMORY_INDEX_NAME = "memory-vector"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


thread_cache = TTLCache(maxsize=1000, ttl=3600)


class ChatService:
    def __init__(self):
        config = Config()
        self.azure_openai_endpoint = config.azure_openai_endpoint
        self.azure_openai_api_key = config.azure_openai_api_key
        self.azure_openai_api_version = config.azure_openai_api_version
        self.azure_openai_deployment_name = config.azure_openai_deployment_model
        self.azure_ai_project_conn_string = config.azure_ai_project_conn_string
        self.azure_ai_search_index = config.azure_ai_search_index
        self.azure_ai_search_api_key = config.azure_ai_search_api_key
        self.memory_service = MemoryService()  # Initialize memory service

    def process_rag_response(self, rag_response, query):
        """
        Parses the RAG response dynamically to extract chart data for Chart.js.
        """
        try:
            client = openai.AzureOpenAI(
                azure_endpoint=self.azure_openai_endpoint,
                api_key=self.azure_openai_api_key,
                api_version=self.azure_openai_api_version,
            )

            system_prompt = """You are an assistant that helps generate valid chart data to be shown using chart.js with version 4.4.4 compatible.
            Include chart type and chart options.
            Pick the best chart type for given data.
            Do not generate a chart unless the input contains some numbers. Otherwise return a message that Chart cannot be generated.
            Only return a valid JSON output and nothing else.
            Verify that the generated JSON can be parsed using json.loads.
            Do not include tooltip callbacks in JSON.
            Always make sure that the generated json can be rendered in chart.js.
            Always remove any extra trailing commas.
            Verify and refine that JSON should not have any syntax errors like extra closing brackets.
            Ensure Y-axis labels are fully visible by increasing **ticks.padding**, **ticks.maxWidth**, or enabling word wrapping where necessary.
            Ensure bars and data points are evenly spaced and not squished or cropped at **100%** resolution by maintaining appropriate **barPercentage** and **categoryPercentage** values."""
            user_prompt = f"""Generate chart data for -
            {query}
            {rag_response}
            """
            logger.info(f">>> Processing chart data for response: {rag_response}")

            completion = client.chat.completions.create(
                model=self.azure_openai_deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
            )

            chart_data = completion.choices[0].message.content.strip().replace("```json", "").replace("```", "")
            logger.info(f">>> Generated chart data: {chart_data}")

            return json.loads(chart_data)

        except Exception as e:
            logger.error(f"Error processing RAG response: {e}")
            return {"error": "Chart could not be generated from this data. Please ask a different question."}
        
    async def fetch_azure_search_content(self, url):
        """Fetch content from the given URL using the Azure AI Search API key."""
        headers = {
            "api-key": self.azure_ai_search_api_key,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    response_json = await response.json()
                    return {
                        "id": response_json.get("id", "Unknown"),
                        "content": response_json.get("content", "No content available"),
                    }
                else:
                    return {"content": f"Failed to fetch content. HTTP Status: {response.status}", "id": "Unknown"}

    async def stream_openai_text(self, conversation_id: str, query: str, memory: bool = False) -> StreamingResponse:
        """
        Get a streaming text response from OpenAI.
        """
        try:
            if not query:
                query = "Please provide a query."

            async with DefaultAzureCredential() as creds:
                async with AzureAIAgent.create_client(
                    credential=creds,
                    conn_str=self.azure_ai_project_conn_string,
                ) as client:
                    AGENT_NAME = "agent"
                    AGENT_INSTRUCTIONS = '''You are a helpful assistant.
                    You have three tools available to you:
                    1. Azure AI Search: You can use this tool to search for memories in the knowledge base.
                    3. Chat with Data: You can use this tool to chat with data and get answers to questions.
                    
                    Use the Azure AI Search tool whenever a user asks about something that might have been stored in memory.
                    '''

                    conn_list = await client.connections.list()

                    ai_search_conn_id = ""
                    for conn in conn_list:
                        if conn.connection_type == ConnectionType.AZURE_AI_SEARCH and conn.authentication_type == "ApiKey":
                            ai_search_conn_id = conn.id
                            break

                    # Create tool for memory search
                    ai_search = AzureAISearchTool(index_connection_id=ai_search_conn_id, index_name=MEMORY_INDEX_NAME)

                    # Combine tools and their resources
                    tools = ai_search.definitions
                    
                    tool_resources = ai_search.resources

                    # Create agent definition
                    agent_definition = await client.agents.create_agent(
                        model=self.azure_openai_deployment_name,
                        name=AGENT_NAME,
                        instructions=AGENT_INSTRUCTIONS,
                        tools=tools,
                        tool_resources=tool_resources,
                        headers={"x-ms-enable-preview": "true"},
                    )

                    # Create the AzureAI Agent
                    agent = AzureAIAgent(
                        client=client,
                        definition=agent_definition,
                        plugins=[ChatWithDataPlugin()],
                    )

                    thread: AzureAIAgentThread = None
                    thread_id = thread_cache.get(conversation_id, None)

                    if thread_id and memory:
                        print(f"Adding memory to agent, agent ID: {agent.id}")

                        # Create a message
                        message = await client.agents.create_message(
                            thread_id=thread_id,
                            role="user",
                            content=f"{query}. Remember this fact about the user and respond to say you have store this to memory.",
                        )
                            
                        # Run the agent
                        run = await client.agents.create_and_process_run(thread_id=thread.id,agent_id=agent.id)
                        
                        if run.status == "failed":
                            print('agent run failed')

                        else: 
                            # Store the memory  
                            memory_result = await self.memory_service.store_memory(thread_id, query)
                            
                            if memory_result["success"]:
                                print(f"Memory stored successfully: {memory_result['message']}")

                    elif memory:
                        # Create a new thread for the conversation
                        thread = await client.agents.create_thread()
                        thread_cache[conversation_id] = thread.id
                        print(f"Adding memory to agent, agent ID: {agent.id}")

                        # Create a message
                        message = await client.agents.create_message(
                            thread_id=thread.id,
                            role="user",
                            content=f"{query}. Remember this fact about the user and respond to say you have store this to memory.",
                        )
                            
                        # Run the agent
                        run = await client.agents.create_and_process_run(thread_id=thread.id,agent_id=agent.id)

                        # Store the memory
                        memory_result = await self.memory_service.store_memory(thread.id, query)
                        thread = AzureAIAgentThread(client=agent.client, thread_id=thread_id)

                    elif thread_id:
                        thread = AzureAIAgentThread(client=agent.client, thread_id=thread_id)

                    footnotes: list[StreamingAnnotationContent] = []
                    async for response in agent.invoke_stream(messages=query, thread=thread):
                        thread_cache[conversation_id] = response.thread.id
                        thread = response.thread
                        footnotes.extend([item for item in response.items if isinstance(item, StreamingAnnotationContent)])
                        yield response.content
                    yield footnotes

        except Exception as e:
            logger.error(f"Error in stream_openai_text: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error streaming OpenAI text")

    async def stream_chat_request(self, request_body, conversation_id, query):
        """
        Handles streaming chat requests.
        """
        history_metadata = request_body.get("history_metadata", {})
        
        # Check if this is a memory save request
        is_memory_request = self.memory_service.is_memory_save_request(query)
        is_memory_retrieval_request = self.memory_service.is_memory_retrieval_request(query)
        
        async def generate():
            try:
                # If this is a memory save request, handle it
                if is_memory_request == 'True':
                    logger.info(f"Detected memory save request: {query}")
                    memory = True
                else:
                    memory = False

                if is_memory_retrieval_request == 'True':
                    logger.info(f"Detected memory retrieval request")
                    memories = await self.memory_service.retrieve_all_memories()
                    query_memories = json.dumps(memories) + "\n\n"
                    query = f"""
                    Can you return this list of memories in bullet point format? 
                    Make sure to remove the user request to save the memory.
                    \n{query_memories}
                    """
                
                # If not a memory request, proceed with normal chat flow
                assistant_content = ""
                citations = []
                
                # Call the OpenAI streaming method
                async for response in self.stream_openai_text(conversation_id, query, memory=memory):
                    # Extract the content from the response
                    if isinstance(response, StreamingChatMessageContent):
                        assistant_content += str(response)
                    elif isinstance(response, list) and all(isinstance(item, StreamingAnnotationContent) for item in response):
                        for item in response:
                            citation = {
                                "content": "",
                                "url": item.url,
                                "title": item.quote,
                            }
                            if citation not in citations:
                                citations.append(citation)

                        citations = sorted(citations, key=lambda x: x["title"])
                        
                    if assistant_content:
                        chat_completion_chunk = {
                            "id": str(uuid.uuid4()),
                            "model": "rag-model",
                            "created": int(time.time()),
                            "object": "extensions.chat.completion.chunk",
                            "answer": assistant_content,
                            "citations": json.dumps(citations),
                            "choices": [
                                {
                                    "messages": [],
                                    "delta": {},
                                }
                            ],
                            "history_metadata": history_metadata,
                            "apim-request-id": "",
                        }

                        yield json.dumps(chat_completion_chunk) + "\n\n"

            except AgentInvokeException as e:
                error_message = str(e)
                retry_after = "sometime"
                if "Rate limit is exceeded" in error_message:
                    import re
                    match = re.search(r"Try again in (\d+) seconds", error_message)
                    if match:
                        retry_after = f"{match.group(1)} seconds"
                    logger.error(f"Rate limit error: {error_message}")
                    yield json.dumps({"error": f"Rate limit is exceeded. Try again in {retry_after}."}) + "\n\n"
                else:
                    logger.error(f"AgentInvokeException: {error_message}")
                    yield json.dumps({"error": "An error occurred. Please try again later."}) + "\n\n"

            except Exception as e:
                logger.error(f"Error in stream_chat_request: {e}", exc_info=True)
                yield json.dumps({"error": "An error occurred while processing the request."}) + "\n\n"

        return generate()

    async def complete_chat_request(self, query, last_rag_response=None):
        """
        Completes a chat request by generating a chart from the RAG response.
        """
        if not last_rag_response:
            return {"error": "A previous RAG response is required to generate a chart."}

        # Process RAG response to generate chart data
        chart_data = self.process_rag_response(last_rag_response, query)

        if not chart_data or "error" in chart_data:
            return {
                "error": "Chart could not be generated from this data. Please ask a different question.",
                "error_desc": str(chart_data),
            }

        logger.info("Successfully generated chart data.")
        return {
            "id": str(uuid.uuid4()),
            "model": "azure-openai",
            "created": int(time.time()),
            "object": chart_data,
        }

#Uncomment to test the stream_chat_request function locally
# import asyncio

# async def test_stream_chat():
#     new_chat = ChatService()
#     # Get the generator function
#     generator = await new_chat.stream_chat_request(query="Can you show me all my memories", conversation_id="12345")
#     # Execute the generator
#     async for chunk in generator:
#         try:
#             # Parse the JSON to extract just the answer
#             data = json.loads(chunk)
#             if "answer" in data:
#                 # Print only the answer text without the JSON structure
#                 print(data["answer"], end="", flush=True)
#             elif "error" in data:
#                 # Print any error messages
#                 print(f"\nError: {data['error']}")
#         except json.JSONDecodeError:
#             # If it's not valid JSON, print it as is
#             print(chunk)

# # Run the test function
# if __name__ == "__main__":
#     asyncio.run(test_stream_chat())