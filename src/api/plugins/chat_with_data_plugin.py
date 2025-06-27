"""Plugin for handling chat interactions with data sources using Azure OpenAI and Azure AI Search.

This module provides functions for:
- Responding to greetings and general questions.
- Generating SQL queries and fetching results from a database.
- Answering questions using call transcript data from Azure AI Search.
"""

from typing import Annotated

from semantic_kernel.functions.kernel_function_decorator import kernel_function
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from common.database.sqldb_service import execute_sql_query
from common.config.config import Config
from helpers.azure_openai_helper import get_azure_openai_client


class ChatWithDataPlugin:
    def __init__(self):
        config = Config()
        self.azure_openai_deployment_model = config.azure_openai_deployment_model
        self.ai_project_endpoint = config.ai_project_endpoint
        self.azure_ai_search_endpoint = config.azure_ai_search_endpoint
        self.azure_ai_search_api_key = config.azure_ai_search_api_key
        self.azure_ai_search_index = config.azure_ai_search_index
        self.use_ai_project_client = config.use_ai_project_client

    @kernel_function(name="Greeting",
                     description="Respond to any greeting or general questions")
    async def greeting(self, input: Annotated[str, "the question"]) -> Annotated[str, "The output is a string"]:
        query = input

        try:
            if self.use_ai_project_client:
                project = AIProjectClient(
                    endpoint=self.ai_project_endpoint,
                    credential=DefaultAzureCredential()
                )
                client = project.inference.get_chat_completions_client()

                completion = client.complete(
                    model=self.azure_openai_deployment_model,
                    messages=[
                        {"role": "system",
                         "content": "You are a helpful assistant to respond to any greeting or general questions."},
                        {"role": "user", "content": query},
                    ],
                    temperature=0,
                )
            else:
                client = get_azure_openai_client()

                completion = client.chat.completions.create(
                    model=self.azure_openai_deployment_model,
                    messages=[
                        {"role": "system",
                         "content": "You are a helpful assistant to respond to any greeting or general questions."},
                        {"role": "user", "content": query},
                    ],
                    temperature=0,
                )
            answer = completion.choices[0].message.content
        except Exception:
            answer = 'Details could not be retrieved. Please try again later.'
        return answer

    @kernel_function(name="ChatWithSQLDatabase",
                     description="Provides quantified results from the database.")
    async def get_SQL_Response(
            self,
            input: Annotated[str, "the question"]
    ):
        query = input

        sql_prompt = f'''Generate a valid T-SQL query to find {query} for tables and columns provided below:
                1. Table: km_processed_data
                Columns: ConversationId,EndTime,StartTime,Content,summary,satisfied,sentiment,topic,keyphrases,complaint
                2. Table: processed_data_key_phrases
                Columns: ConversationId,key_phrase,sentiment
                Use ConversationId as the primary key as the primary key in tables for queries but not for any other operations.
                **Always** return a valid T-SQL query with correct syntax. Only return the generated SQL query. Do not return anything else.'''

        try:
            if self.use_ai_project_client:
                project = AIProjectClient(
                    endpoint=self.ai_project_endpoint,
                    credential=DefaultAzureCredential()
                )
                client = project.inference.get_chat_completions_client()

                completion = client.complete(
                    model=self.azure_openai_deployment_model,
                    messages=[
                        {"role": "system", "content": "You are an assistant that helps generate valid T-SQL queries."},
                        {"role": "user", "content": sql_prompt},
                    ],
                    temperature=0,
                )
                sql_query = completion.choices[0].message.content
                sql_query = sql_query.replace("```sql", '').replace("```", '')
            else:
                client = get_azure_openai_client()

                completion = client.chat.completions.create(
                    model=self.azure_openai_deployment_model,
                    messages=[
                        {"role": "system", "content": "You are an assistant that helps generate valid T-SQL queries."},
                        {"role": "user", "content": sql_prompt},
                    ],
                    temperature=0,
                )
                sql_query = completion.choices[0].message.content
                sql_query = sql_query.replace("```sql", '').replace("```", '')

            answer = await execute_sql_query(sql_query)
            answer = answer[:20000] if len(answer) > 20000 else answer

        except Exception:
            answer = 'Details could not be retrieved. Please try again later.'
        return answer

    @kernel_function(name="ChatWithCallTranscripts",
                     description="Provides summaries or detailed explanations from the search index.")
    async def get_answers_from_calltranscripts(
            self,
            question: Annotated[str, "the question"]
    ):
        client = get_azure_openai_client()

        query = question
        system_message = '''You are an assistant who provides an analyst with helpful information about data.
        You have access to the call transcripts, call data, topics, sentiments, and key phrases.
        You can use this information to answer questions.
        If you cannot answer the question, always return - I cannot answer this question from the data available. Please rephrase or add more details.'''
        answer = ''
        try:
            completion = client.chat.completions.create(
                model=self.azure_openai_deployment_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_message
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                seed=42,
                temperature=0,
                max_tokens=800,
                extra_body={
                    "data_sources": [
                        {
                            "type": "azure_search",
                            "parameters": {
                                "endpoint": self.azure_ai_search_endpoint,
                                "index_name": self.azure_ai_search_index,
                                "semantic_configuration": "my-semantic-config",
                                "query_type": "vector_simple_hybrid",  # "vector_semantic_hybrid"
                                "fields_mapping": {
                                    "content_fields_separator": "\n",
                                    "content_fields": ["content"],
                                    "filepath_field": "chunk_id",
                                    "title_field": "sourceurl",  # null,
                                    "url_field": "sourceurl",
                                    "vector_fields": ["contentVector"]
                                },
                                "in_scope": "true",
                                # "vector_filter_mode": "preFilter", #VectorFilterMode.PRE_FILTER,
                                # "filter": f"client_id eq '{ClientId}'", #"", #null,
                                "strictness": 3,
                                "top_n_documents": 5,
                                "authentication": {
                                    "type": "api_key",
                                    "key": self.azure_ai_search_api_key
                                },
                                "embedding_dependency": {
                                    "type": "deployment_name",
                                    "deployment_name": "text-embedding-ada-002"
                                },

                            }
                        }
                    ]
                }
            )
            answer = completion.choices[0]

            # Limit the content inside citations to 300 characters to minimize load
            if hasattr(answer.message, 'context') and 'citations' in answer.message.context:
                for citation in answer.message.context.get('citations', []):
                    if isinstance(citation, dict) and 'content' in citation:
                        citation['content'] = citation['content'][:300] + '...' if len(citation['content']) > 300 else citation['content']
        except BaseException:
            answer = 'Details could not be retrieved. Please try again later.'
        return answer
