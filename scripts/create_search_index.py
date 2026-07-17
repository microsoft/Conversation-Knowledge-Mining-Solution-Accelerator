"""Create the Knowledge Mining Azure AI Search index (solution / non-external scenarios).

Usage:
    python scripts/create_search_index.py --search-endpoint <url> --openai-endpoint <url>
"""

import argparse
import os
import sys

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)


def create_search_index(
    endpoint: str,
    index_name: str,
    openai_endpoint: str,
    embedding_model: str,
    credential=None,
):
    """Create or update the standard knowledge-mining index (vector + semantic search)."""
    credential = credential or DefaultAzureCredential()
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-config",
                vectorizer_name="openai-vectorizer",
            )
        ],
        vectorizers=[
            AzureOpenAIVectorizer(
                vectorizer_name="openai-vectorizer",
                kind="azureOpenAI",
                parameters=AzureOpenAIVectorizerParameters(
                    resource_url=openai_endpoint,
                    deployment_name=embedding_model,
                    model_name=embedding_model,
                ),
            )
        ],
    )

    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="summary"),
                    keywords_fields=[SemanticField(field_name="key_phrases")],
                    content_fields=[SemanticField(field_name="text")],
                ),
            )
        ]
    )

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(name="doc_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SearchableField(name="text", type=SearchFieldDataType.String),
        SearchableField(name="summary", type=SearchFieldDataType.String),
        SimpleField(name="type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="product", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="timestamp", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="source_file", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="key_phrases", type=SearchFieldDataType.String, collection=True, filterable=True),
        SearchableField(name="entities", type=SearchFieldDataType.String, collection=True, filterable=True),
        SearchableField(name="topics", type=SearchFieldDataType.String, collection=True, filterable=True),
        SearchField(
            name="text_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="vector-profile",
        ),
    ]

    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )
    return index_client.create_or_update_index(index)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the Knowledge Mining search index")
    parser.add_argument("--search-endpoint", default=os.getenv("AZURE_SEARCH_ENDPOINT", ""))
    parser.add_argument("--index-name", default=os.getenv("AZURE_SEARCH_INDEX_NAME", "knowledge-mining-index"))
    parser.add_argument("--openai-endpoint", default=os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    parser.add_argument("--embedding-deployment", default=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"))
    args = parser.parse_args()

    if not args.search_endpoint:
        print("ERROR: search endpoint not provided (--search-endpoint or AZURE_SEARCH_ENDPOINT).")
        return 1

    print(f"Ensuring Azure AI Search index '{args.index_name}' on {args.search_endpoint} ...")
    try:
        result = create_search_index(
            args.search_endpoint, args.index_name, args.openai_endpoint, args.embedding_deployment
        )
    except Exception as e:
        print(f"[FAIL] Could not create search index: {e}")
        return 1

    print(f"[OK] Search index '{result.name}' ready ({len(result.fields)} fields)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
