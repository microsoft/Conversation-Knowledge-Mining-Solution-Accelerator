from azure.ai.agents.models import AzureAISearchTool, AzureAISearchQueryType
from azure.ai.projects import AIProjectClient
from agents.agent_factory_base import BaseAgentFactory
from helpers.azure_credential_utils import get_azure_credential
# from agents.agent_factory_base import BaseAgentFactory
# from helpers.azure_credential_utils import get_azure_credential


class SearchAgentFactory(BaseAgentFactory):
    """Factory class for creating search agents with Azure AI Search integration."""

    @classmethod
    async def create_agent(cls, config):
        """
        Asynchronously creates a search agent using Azure AI Search and registers it
        with the provided project configuration.

        Args:
            config: Configuration object containing Azure project and search index settings.

        Returns:
            dict: A dictionary containing the created agent and the project client.
        """
        project_client = AIProjectClient(
            endpoint=config.ai_project_endpoint,
            credential=get_azure_credential(client_id=config.azure_client_id),
            api_version=config.ai_project_api_version,
        )

        field_mapping = {
            "contentFields": ["content"],
            "urlField": "sourceurl",
            "titleField": "chunk_id",
        }

        index_body = {
            "connectionName": config.azure_ai_search_connection_name,
            "indexName": config.azure_ai_search_index,
            "type": "AzureSearch",
            "fieldMapping": field_mapping
        }

        project_index = project_client.indexes.create_or_update(
            name=f"project-index-{config.azure_ai_search_connection_name}-{config.azure_ai_search_index}",
            version="1",
            body=index_body
        )

        ai_search = AzureAISearchTool(
            index_asset_id=f"{project_index.name}/versions/{project_index.version}",
            index_connection_id=None,
            index_name=None,
            query_type=AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,
            top_k=5,
            filter=""
        )

        agent = project_client.agents.create_agent(
            model=config.azure_openai_deployment_model,
            name=f"KM-ChatWithCallTranscriptsAgent-{config.solution_name}",
            instructions="You are a helpful agent. Use the tools provided and always cite your sources.",
            tools=ai_search.definitions,
            tool_resources=ai_search.resources,
        )

        return {
            "agent": agent,
            "client": project_client
        }

    @classmethod
    async def _delete_agent_instance(cls, agent_wrapper: dict):
        """
        Asynchronously deletes the specified agent instance from the Azure AI project.

        Args:
            agent_wrapper (dict): A dictionary containing the 'agent' and the corresponding 'client'.
        """
        agent_wrapper["client"].agents.delete_agent(agent_wrapper["agent"].id)
