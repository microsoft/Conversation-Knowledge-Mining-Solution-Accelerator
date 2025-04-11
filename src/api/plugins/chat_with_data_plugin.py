from typing import Annotated

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AzureAISearchTool, ConnectionType
from azure.identity.aio import DefaultAzureCredential

from common.config.config import Config
from common.database.sqldb_service import execute_sql_query

from semantic_kernel.agents import AzureAIAgent, AzureAIAgentThread
from semantic_kernel.functions.kernel_function_decorator import kernel_function

import openai


class ChatWithDataPlugin:
    def __init__(self):
        config = Config()
        self.azure_openai_deployment_model = config.azure_openai_deployment_model
        self.azure_openai_endpoint = config.azure_openai_endpoint
        self.azure_openai_api_key = config.azure_openai_api_key
        self.azure_openai_api_version = config.azure_openai_api_version
        self.azure_ai_search_endpoint = config.azure_ai_search_endpoint
        self.azure_ai_search_api_key = config.azure_ai_search_api_key
        self.azure_ai_search_index = config.azure_ai_search_index
        self.use_ai_project_client = config.use_ai_project_client
        self.azure_ai_project_conn_string = config.azure_ai_project_conn_string

    @kernel_function(
        name="Greeting",
        description="Respond to any greeting or general questions"
    )
    async def greeting(
        self,
        input: Annotated[str, "the question"]
    ) -> Annotated[str, "The output is a string"]:
        query = input

        try:
            if self.use_ai_project_client:
                project = AIProjectClient.from_connection_string(
                    conn_str=self.azure_ai_project_conn_string,
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
                client = openai.AzureOpenAI(
                    azure_endpoint=self.azure_openai_endpoint,
                    api_key=self.azure_openai_api_key,
                    api_version=self.azure_openai_api_version
                )

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
        except Exception as e:
            # 'Information from database could not be retrieved. Please try again later.'
            answer = str(e)
        return answer

    @kernel_function(
        name="ChatWithSQLDatabase",
        description="Retrieve quantified results from the SQL database based on a given query."
    )
    async def get_SQL_Response(
        self,
        input: Annotated[str, "the question"]
    ):
        query = input

        sql_prompt = f'''A valid T-SQL query to find {query} for tables and columns provided below:
                1. Table: km_processed_data
                Columns: ConversationId,EndTime,StartTime,Content,summary,satisfied,sentiment,topic,keyphrases,complaint
                2. Table: processed_data_key_phrases
                Columns: ConversationId,key_phrase,sentiment
                Use ConversationId as the primary key as the primary key in tables for queries but not for any other operations.
                Only return the generated sql query. do not return anything else.'''

        try:
            if self.use_ai_project_client:
                project = AIProjectClient.from_connection_string(
                    conn_str=self.azure_ai_project_conn_string,
                    credential=DefaultAzureCredential()
                )
                client = project.inference.get_chat_completions_client()

                completion = client.complete(
                    model=self.azure_openai_deployment_model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": sql_prompt},
                    ],
                    temperature=0,
                )
                sql_query = completion.choices[0].message.content
                sql_query = sql_query.replace("```sql", '').replace("```", '')
            else:
                client = openai.AzureOpenAI(
                    azure_endpoint=self.azure_openai_endpoint,
                    api_key=self.azure_openai_api_key,
                    api_version=self.azure_openai_api_version
                )

                completion = client.chat.completions.create(
                    model=self.azure_openai_deployment_model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": sql_prompt},
                    ],
                    temperature=0,
                )
                sql_query = completion.choices[0].message.content
                sql_query = sql_query.replace("```sql", '').replace("```", '')
            answer = execute_sql_query(sql_query)

        except Exception as e:
            # 'Information from database could not be retrieved. Please try again later.'
            answer = str(e)
        return answer

