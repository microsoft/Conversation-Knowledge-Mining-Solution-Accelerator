#!/usr/bin/env python3
"""
01_create_search_index.py - Creates Azure Search Index with vector search configuration
"""

# Early debug output - this should appear immediately
print("01_create_search_index.py: Script execution started")
print("01_create_search_index.py: Importing modules...")

from azure.keyvault.secrets import SecretClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
    SearchIndex
)
from azure_credential_utils import get_azure_credential
import logging
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('01_create_search_index.log')  # Write to current directory
    ]
)
logger = logging.getLogger(__name__)

# Also print startup message to ensure visibility
print("=== STARTING 01_create_search_index.py ===")
print(f"Working directory: {os.getcwd()}")
print(f"Python version: {sys.version}")
logger.info("=== STARTING 01_create_search_index.py ===")
logger.info("Working directory: %s", os.getcwd())
logger.info("Python version: %s", sys.version)

# === Configuration ===
print("01_create_search_index.py: Setting up configuration...")
KEY_VAULT_NAME = 'kv_to-be-replaced'
MANAGED_IDENTITY_CLIENT_ID = 'mici_to-be-replaced'
INDEX_NAME = "call_transcripts_index"

print(f"01_create_search_index.py: Configuration - KEY_VAULT_NAME: {KEY_VAULT_NAME}")
print(f"01_create_search_index.py: Configuration - INDEX_NAME: {INDEX_NAME}")
logger.info("Configuration loaded:")
logger.info("KEY_VAULT_NAME: %s", KEY_VAULT_NAME)
logger.info("MANAGED_IDENTITY_CLIENT_ID: %s", MANAGED_IDENTITY_CLIENT_ID)
logger.info("INDEX_NAME: %s", INDEX_NAME)

print("01_create_search_index.py: About to define functions...")


def get_secrets_from_kv(secret_name: str) -> str:
    """
    Retrieves a secret value from Azure Key Vault.

    Args:
        secret_name (str): Name of the secret.
        credential (ManagedIdentityCredential): Credential with access to Key Vault.

    Returns:
        str: The secret value.
    """
    try:
        logger.info(f"Attempting to retrieve secret: {secret_name}")
        kv_credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
        logger.info("Azure credential obtained successfully")
        
        secret_client = SecretClient(
            vault_url=f"https://{KEY_VAULT_NAME}.vault.azure.net/",
            credential=kv_credential
        )
        logger.info(f"SecretClient created for vault: {KEY_VAULT_NAME}")
        
        secret_value = secret_client.get_secret(secret_name).value
        logger.info(f"Successfully retrieved secret: {secret_name}")
        return secret_value
        
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        raise


def create_search_index():
    """
    Creates or updates an Azure Cognitive Search index configured for:
    - Text fields
    - Vector search using Azure AI Foundry embeddings
    - Semantic search using prioritized fields
    """
    try:
        logger.info("=== Starting create_search_index function ===")
        
        # Shared credential
        logger.info("Creating Azure credential...")
        credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
        logger.info("Azure credential created successfully")

        # Retrieve secrets from Key Vault
        logger.info("Retrieving secrets from Key Vault...")
        search_endpoint = get_secrets_from_kv("AZURE-SEARCH-ENDPOINT")
        azure_ai_model_endpoint = get_secrets_from_kv("AZURE-OPENAI-ENDPOINT")
        embedding_model = get_secrets_from_kv("AZURE-OPENAI-EMBEDDING-MODEL")
        
        logger.info(f"Search endpoint: {search_endpoint}")
        logger.info(f"Azure AI model endpoint: {azure_ai_model_endpoint}")
        logger.info(f"Embedding model: {embedding_model}")

        logger.info("Creating SearchIndexClient...")
        index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
        logger.info("SearchIndexClient created successfully")

        # Define index schema
        logger.info("Defining index schema...")
        fields = [
            SearchField(name="id", type=SearchFieldDataType.String, key=True),
            SearchField(name="chunk_id", type=SearchFieldDataType.String),
            SearchField(name="content", type=SearchFieldDataType.String),
            SearchField(name="sourceurl", type=SearchFieldDataType.String),
            SearchField(
                name="contentVector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=1536,
                vector_search_profile_name="myHnswProfile"
            )
        ]
        logger.info(f"Index schema defined with {len(fields)} fields")

        # Define vector search settings
        logger.info("Defining vector search settings...")
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(name="myHnsw")
            ],
            profiles=[
                VectorSearchProfile(
                    name="myHnswProfile",
                    algorithm_configuration_name="myHnsw",
                    vectorizer_name="myOpenAI"
                )
            ],
            vectorizers=[
                AzureOpenAIVectorizer(
                    vectorizer_name="myOpenAI",
                    kind="azureOpenAI",
                    parameters=AzureOpenAIVectorizerParameters(
                        resource_url=azure_ai_model_endpoint,
                        deployment_name=embedding_model,
                        model_name=embedding_model
                    )
                )
            ]
        )
        logger.info("Vector search settings defined")

        # Define semantic configuration
        logger.info("Defining semantic configuration...")
        semantic_config = SemanticConfiguration(
            name="my-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                keywords_fields=[SemanticField(field_name="chunk_id")],
                content_fields=[SemanticField(field_name="content")]
            )
        )

        # Create the semantic settings with the configuration
        semantic_search = SemanticSearch(configurations=[semantic_config])
        logger.info("Semantic search settings defined")

        # Define and create the index
        logger.info("Creating search index...")
        index = SearchIndex(
            name=INDEX_NAME,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )

        logger.info("Submitting index creation request...")
        result = index_client.create_or_update_index(index)
        logger.info(f"Search index '{result.name}' created or updated successfully.")
        print(f"Search index '{result.name}' created or updated successfully.")
        
        logger.info("=== create_search_index function completed successfully ===")
        
    except Exception as e:
        logger.error(f"ERROR in create_search_index: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"ERROR: {str(e)}")
        raise

def main():
    """Main execution wrapper with error handling"""
    print("=== MAIN EXECUTION STARTED ===")
    logger.info("=== STARTING 01_create_search_index.py MAIN ===")
    
    try:
        print("About to call create_search_index()")
        create_search_index()
        print("=== COMPLETED 01_create_search_index.py SUCCESSFULLY ===")
        logger.info("=== COMPLETED 01_create_search_index.py SUCCESSFULLY ===")
    except Exception as e:
        print(f"=== FAILED 01_create_search_index.py ===")
        print(f"Main execution error: {str(e)}")
        logger.error("=== FAILED 01_create_search_index.py ===")
        logger.error("Main execution error: %s", str(e))
        logger.error("Error type: %s", type(e).__name__)
        import traceback
        logger.error("Full traceback: %s", traceback.format_exc())
        print(f"MAIN ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
else:
    # When imported as module during deployment
    logger.info("Script imported as module, calling create_search_index()")
    create_search_index()