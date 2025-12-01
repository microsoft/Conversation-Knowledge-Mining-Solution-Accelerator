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

# === Configuration ===
KEY_VAULT_NAME = 'kv_to-be-replaced'
MANAGED_IDENTITY_CLIENT_ID = 'mici_to-be-replaced'
INDEX_NAME = "call_transcripts_index"

print("calling create_search_index()....")


def get_secrets_from_kv(secret_name: str) -> str:
    """
    Retrieves a secret value from Azure Key Vault.

    Args:
        secret_name (str): Name of the secret.
        credential (ManagedIdentityCredential): Credential with access to Key Vault.

    Returns:
        str: The secret value.
    """
    kv_credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)
    secret_client = SecretClient(
        vault_url=f"https://{KEY_VAULT_NAME}.vault.azure.net/",
        credential=kv_credential
    )
    return secret_client.get_secret(secret_name).value


def create_search_index():
    """
    Creates or updates an Azure Cognitive Search index configured for:
    - Text fields
    - Vector search using Azure OpenAI embeddings
    - Semantic search using prioritized fields
    """
    # Shared credential
    credential = get_azure_credential(client_id=MANAGED_IDENTITY_CLIENT_ID)

    # Retrieve secrets from Key Vault
    search_endpoint = get_secrets_from_kv("AZURE-SEARCH-ENDPOINT")
    openai_resource_url = get_secrets_from_kv("AZURE-OPENAI-ENDPOINT")
    embedding_model = get_secrets_from_kv("AZURE-OPENAI-EMBEDDING-MODEL")

    index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)

    # Define index schema
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

    # Define vector search settings
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
                    resource_url=openai_resource_url,
                    deployment_name=embedding_model,
                    model_name=embedding_model
                )
            )
        ]
    )

    # Define semantic configuration
    semantic_config = SemanticConfiguration(
        name="my-semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            keywords_fields=[SemanticField(field_name="chunk_id")],
            content_fields=[SemanticField(field_name="content")]
        )
    )

    # Create the semantic settings with the configuration
    semantic_search = SemanticSearch(configurations=[semantic_config])

    # Define and create the index
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search
    )

    result = index_client.create_or_update_index(index)
    print(f"Search index '{result.name}' created or updated successfully.")


create_search_index()