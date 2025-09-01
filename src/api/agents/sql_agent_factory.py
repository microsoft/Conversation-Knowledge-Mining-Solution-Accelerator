from azure.ai.projects import AIProjectClient

from agents.agent_factory_base import BaseAgentFactory

from helpers.azure_credential_utils import get_azure_credential


class SQLAgentFactory(BaseAgentFactory):
    """
    Factory class for creating SQL agents that generate T-SQL queries using Azure AI Project.
    """

    @classmethod
    async def create_agent(cls, config):
        """
        Asynchronously creates an AI agent configured to generate T-SQL queries
        based on a predefined schema and user instructions.

        Args:
            config: Configuration object containing AI project and model settings.

        Returns:
            dict: A dictionary containing the created 'agent' and its associated 'client'.
        """
        instructions = '''You are an assistant that helps generate valid T-SQL queries.
        Generate a valid T-SQL query for the user's request using these tables:
        1. Table: km_processed_data
            Columns: ConversationId, EndTime, StartTime, Content, summary, satisfied, sentiment, topic, keyphrases, complaint
        2. Table: processed_data_key_phrases
            Columns: ConversationId, key_phrase, sentiment
        Use accurate and semantically appropriate SQL expressions, data types, functions, aliases, and conversions based strictly on the column definitions and the explicit or implicit intent of the user query.
        Avoid assumptions or defaults not grounded in schema or context.
        Ensure all aggregations, filters, grouping logic, and time-based calculations are precise, logically consistent, and reflect the user's intent without ambiguity.
        **Always** return a valid T-SQL query. Only return the SQL query text—no explanations.'''

        project_client = AIProjectClient(
            endpoint=config.ai_project_endpoint,
            credential=get_azure_credential(client_id=config.azure_client_id),
            api_version=config.ai_project_api_version,
        )

        agent = project_client.agents.create_agent(
            model=config.azure_openai_deployment_model,
            name=f"KM-ChatWithSQLDatabaseAgent-{config.solution_name}",
            instructions=instructions,
        )

        return {
            "agent": agent,
            "client": project_client
        }

    @classmethod
    async def _delete_agent_instance(cls, agent_wrapper: dict):
        """
        Asynchronously deletes the specified SQL agent instance from the Azure AI project.

        Args:
            agent_wrapper (dict): Dictionary containing the 'agent' and 'client' to be removed.
        """
        agent_wrapper["client"].agents.delete_agent(agent_wrapper["agent"].id)
