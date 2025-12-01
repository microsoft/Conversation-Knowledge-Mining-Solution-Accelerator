import logging

from azure.ai.projects import AIProjectClient

from agents.agent_factory_base import BaseAgentFactory

from helpers.azure_credential_utils import get_azure_credential

logger = logging.getLogger(__name__)

class SQLAgentFactory(BaseAgentFactory):
    """
    Factory class for creating SQL agents that generate T-SQL queries using Azure AI Project.
    """

    @classmethod
    async def create_agent(cls, config):
        """
        Asynchronously creates or retrieves an AI agent configured to generate T-SQL queries
        based on a predefined schema and user instructions.
        
        First checks if an agent with the expected name already exists and reuses it.
        Only creates a new agent if one doesn't exist.

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

        agent_name = f"KM-ChatWithSQLDatabaseAgent-{config.solution_name}"
        
        # Try to find an existing agent with the same name
        try:
            agents_list = project_client.agents.list_agents()
            for existing_agent in agents_list:
                if existing_agent.name == agent_name:
                    logger.info(f"Reusing existing agent: {agent_name} (ID: {existing_agent.id})")
                    return {
                        "agent": existing_agent,
                        "client": project_client
                    }
        except Exception as e:
            logger.warning(f"Could not list existing agents: {e}. Creating new agent.")

        # No existing agent found, create a new one
        agent = project_client.agents.create_agent(
            model=config.azure_openai_deployment_model,
            name=agent_name,
            instructions=instructions,
        )
        logger.info(f"Created new agent: {agent_name} (ID: {agent.id})")

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
