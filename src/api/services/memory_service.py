import uuid
import logging
import hashlib
import re
from typing import Optional, Dict, Any

import openai
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswParameters,
    HnswAlgorithmConfiguration,
    SemanticPrioritizedFields,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticSearch,
    SemanticConfiguration,
    SemanticField,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmKind,
    VectorSearchAlgorithmMetric,
    ExhaustiveKnnAlgorithmConfiguration,
    ExhaustiveKnnParameters,
    VectorSearchProfile,
)

from common.config.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default memory index name
MEMORY_INDEX_NAME = "memory-vector"

class MemoryService:
    """Service for managing memory storage in Azure AI Search."""
    
    def __init__(self):
        config = Config()
        self.azure_openai_endpoint = config.azure_openai_endpoint
        self.azure_openai_api_key = config.azure_openai_api_key
        self.azure_openai_api_version = config.azure_openai_api_version
        self.azure_openai_deployment_name = config.azure_openai_deployment_model
        self.azure_ai_search_endpoint = config.azure_ai_search_endpoint
        self.azure_ai_search_api_key = config.azure_ai_search_api_key
        self.memory_index_name = MEMORY_INDEX_NAME  # Default memory index name
        
        # Initialize the memory index if it doesn't exist
        self.ensure_memory_index_exists()
        
    def is_memory_save_request(self, query: str) -> bool:
        """
        Detects if the user's query is a request to save memory.
        
        Args:
            query: User's input text
            
        Returns:
            bool: True if the query contains a memory save request, False otherwise
        """

        client = openai.AzureOpenAI(
                azure_endpoint=self.azure_openai_endpoint,
                api_key=self.azure_openai_api_key,
                api_version=self.azure_openai_api_version,
            )
        
        # Define patterns for memory save requests
        memory_patterns = [
            r"save\s+this\s+to\s+memory",
            r"remember\s+this",
            r"store\s+this\s+in\s+memory",
            r"save\s+to\s+memory",
            r"memorize\s+this",
        ]

        system_prompt = f"""
        You are an assistant helping to see if a user has asked to save some information into memory.
        If the user is asking for information to be saved as a memory respond with the bool True. If not repsond with False. 
        Only respond with the bool and nothing else. Here are some examples of what the user might say:
        {memory_patterns}
        """
        user_prompt = f"{query}"
        logger.info(f">>> assesing if: {query} is memory")

        completion = client.chat.completions.create(
            model=self.azure_openai_deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        result = completion.choices[0].message.content
        
        logger.info(f">>> add memory?: {result}")
        
        return result
    
    def create_memory_index_definition(self, name: str) -> SearchIndex:
        """
        Creates an Azure AI Search index definition for memory storage.
        
        Args:
            name: Name of the index to create
            
        Returns:
            SearchIndex: The search index definition
        """
        # The fields we want to index. The "embedding" field is a vector field that will
        # be used for vector search.
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="thread_id", type=SearchFieldDataType.String),
            SimpleField(name="role", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(name="embedding", type=SearchFieldDataType.String),
            SearchField(
                name="contentVector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                # Size of the vector created by the text-embedding-ada-002 model.
                vector_search_dimensions=1536,
                vector_search_profile_name="myHnswProfile",
            ),
        ]

        # The "content" field should be prioritized for semantic ranking.
        semantic_config = SemanticConfiguration(
            name="default",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="thread_id"),
                keywords_fields=[],
                content_fields=[SemanticField(field_name="content")],
            ),
        )

        # For vector search, we want to use the HNSW algorithm with cosine distance
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="myHnsw",
                    kind=VectorSearchAlgorithmKind.HNSW,
                    parameters=HnswParameters(
                        m=4,
                        ef_construction=400,
                        ef_search=500,
                        metric=VectorSearchAlgorithmMetric.COSINE,
                    ),
                ),
                ExhaustiveKnnAlgorithmConfiguration(
                    name="myExhaustiveKnn",
                    kind=VectorSearchAlgorithmKind.EXHAUSTIVE_KNN,
                    parameters=ExhaustiveKnnParameters(
                        metric=VectorSearchAlgorithmMetric.COSINE
                    ),
                ),
            ],
            profiles=[
                VectorSearchProfile(
                    name="myHnswProfile",
                    algorithm_configuration_name="myHnsw",
                ),
                VectorSearchProfile(
                    name="myExhaustiveKnnProfile",
                    algorithm_configuration_name="myExhaustiveKnn",
                ),
            ],
        )

        # Create the semantic settings with the configuration
        semantic_search = SemanticSearch(configurations=[semantic_config])

        # Create the search index.
        index = SearchIndex(
            name=name,
            fields=fields,
            semantic_search=semantic_search,
            vector_search=vector_search,
        )

        return index
    
    def ensure_memory_index_exists(self):
        """
        Creates the memory index if it doesn't already exist.
        """
        try:
            # Create a search index client
            search_index_client = SearchIndexClient(
                endpoint=self.azure_ai_search_endpoint,
                credential=AzureKeyCredential(self.azure_ai_search_api_key)
            )
            
            # Check if index exists
            try:
                existing_index = search_index_client.get_index(name=self.memory_index_name)
                logger.info(f"Memory index '{self.memory_index_name}' already exists.")
                return
            except Exception:
                # Index doesn't exist, create it
                logger.info(f"Creating memory index '{self.memory_index_name}'...")
                
                # Create index definition
                index = self.create_memory_index_definition(self.memory_index_name)
                
                # Create the index
                result = search_index_client.create_or_update_index(index)
                logger.info(f"Memory index '{self.memory_index_name}' created successfully.")
                
        except Exception as e:
            logger.error(f"Error ensuring memory index exists: {str(e)}", exc_info=True)
            # Continue execution even if index creation fails
            # The application will attempt to use the index if it exists
    
    async def store_memory(self, thread_id: str, content: str) -> Dict[str, Any]:
        """
        Stores content in memory using Azure AI Search.
        
        Args:
            conversation_id: ID of the conversation
            content: Content to store in memory
            
        Returns:
            Dict: Result of the memory storage operation
        """
        try:
            # Create a unique ID for this memory
            memory_id = f"{thread_id}-{hashlib.md5(content.encode()).hexdigest()}"
            
            # Create a search client
            search_client = SearchClient(
                endpoint=self.azure_ai_search_endpoint,
                index_name=self.memory_index_name,
                credential=AzureKeyCredential(self.azure_ai_search_api_key)
            )
            
            # Create embeddings for the content
            client = openai.AzureOpenAI(
                azure_endpoint=self.azure_openai_endpoint,
                api_key=self.azure_openai_api_key,
                api_version=self.azure_openai_api_version,
            )
            
            model_id = "text-embedding-ada-002"  # Default embedding model
            embeddings = client.embeddings.create(input=content, model=model_id).data[0].embedding
            
            # Create the memory document
            document = {
                "id": memory_id,
                "thread_id": thread_id,
                "role": "user",
                "content": content,
                "contentVector": embeddings,
                "embedding": str(embeddings)
            }
            
            # Store in Azure AI Search
            result = search_client.upload_documents(documents=[document])
            logger.info(f"Memory stored with ID: {memory_id}")
            
            return {
                "success": True,
                "memory_id": memory_id,
                "message": "Memory has been successfully saved."
            }
            
        except Exception as e:
            logger.error(f"Error storing memory: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to save memory."
            }
        
    async def retrieve_all_memories(self) -> Dict[str, Any]:
        """
        Retrieves all stored memories from Azure AI Search.
        
        Returns:
            Dict: A dictionary containing the success status and either a list of memories or an error message.
        """
        try:
            # Create a search client for the memory index
            search_client = SearchClient(
                endpoint=self.azure_ai_search_endpoint,
                index_name=self.memory_index_name,
                credential=AzureKeyCredential(self.azure_ai_search_api_key)
            )
            
            # Search for all documents with "*" wildcard
            result = search_client.search(search_text="*", top=1000, include_total_count=True)
            
            total_count = result.get_count()
            
            if total_count == 0:
                return {
                    "success": True,
                    "memories": [],
                    "message": "No memories found."
                }
            
            # Process and format the results
            memories = []
            for document in result:
                memories.append({
                    "id": document["id"],
                    "thread_id": document["thread_id"],
                    "content": document["content"]
                })
            
            # Format the memories as bullet points
            formatted_text = "\n".join([f"• Memory: {mem['content']}" for mem in memories])
            
            return {
                "success": True,
                "memories": memories,
                "formatted_text": formatted_text,
                "message": f"Successfully retrieved {total_count} memories."
            }
            
        except Exception as e:
            logger.error(f"Error retrieving memories: {str(e)}", exc_info=True)
            return {
                "success": False,
                "memories": None,
                "message": f"Failed to retrieve memories: {str(e)}"
            }
            
    def is_memory_retrieval_request(self, query: str) -> bool:
        """
        Detects if the user's query is a request to retrieve all memories.
        """
        # Simple pattern matching for memory retrieval requests
        memory_patterns = [
            r"show\s+(?:all|my)\s+memories",
            r"list\s+(?:all|my)\s+memories",
            r"retrieve\s+(?:all|my)\s+memories",
            r"get\s+(?:all|my)\s+memories",
            r"what\s+(?:have|did)\s+(?:I|you)\s+(?:stored|saved|memorized)",
            r"what's\s+in\s+(?:your|my)\s+memory",
        ]

        client = openai.AzureOpenAI(
                azure_endpoint=self.azure_openai_endpoint,
                api_key=self.azure_openai_api_key,
                api_version=self.azure_openai_api_version,
            )
        
        system_prompt = f"""
        You are an assistant helping to see if the user's query is a request to retrieve all memories.
        If the user is asking to retrieve all memories respond with the bool True. If not repsond with False. 
        Only respond with the bool and nothing else. Here are some examples of what the user might say:
        {memory_patterns}
        """
        user_prompt = f"{query}"
        logger.info(f">>> assesing if: {query} is memory retrieval request")

        completion = client.chat.completions.create(
            model=self.azure_openai_deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        result = completion.choices[0].message.content
        
        logger.info(f">>> returning list of memories")
        
        return result