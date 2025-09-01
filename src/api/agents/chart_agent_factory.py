from azure.ai.projects import AIProjectClient

from agents.agent_factory_base import BaseAgentFactory
from helpers.azure_credential_utils import get_azure_credential


class ChartAgentFactory(BaseAgentFactory):
    """
    Factory class for creating Chart agents that generate chart.js compatible JSON
    based on numerical and structured data from RAG responses.
    """

    @classmethod
    async def create_agent(cls, config):
        """
        Asynchronously creates an AI agent configured to convert structured data
        into chart.js-compatible JSON using Azure AI Project.

        Args:
            config: Configuration object containing AI project and model settings.

        Returns:
            dict: A dictionary containing the created 'agent' and its associated 'client'.
        """
        instructions = """You are an assistant that helps generate valid chart data to be shown using chart.js with version 4.4.4 compatible.
        Include chart type and chart options.
        Pick the best chart type for given data.
        Do not generate a chart unless the input contains some numbers. Otherwise return {"error": "Chart cannot be generated"}.
        Only return a valid JSON output and nothing else.
        Verify that the generated JSON can be parsed using json.loads.
        Do not include tooltip callbacks in JSON.
        Always make sure that the generated json can be rendered in chart.js.
        Always remove any extra trailing commas.
        Verify and refine that JSON should not have any syntax errors like extra closing brackets.
        Ensure Y-axis labels are fully visible by increasing **ticks.padding**, **ticks.maxWidth**, or enabling word wrapping where necessary.
        Ensure bars and data points are evenly spaced and not squished or cropped at **100%** resolution by maintaining appropriate **barPercentage** and **categoryPercentage** values."""

        project_client = AIProjectClient(
            endpoint=config.ai_project_endpoint,
            credential=get_azure_credential(client_id=config.azure_client_id),
            api_version=config.ai_project_api_version,
        )

        agent = project_client.agents.create_agent(
            model=config.azure_openai_deployment_model,
            name=f"KM-ChartAgent-{config.solution_name}",
            instructions=instructions,
        )

        return {
            "agent": agent,
            "client": project_client
        }

    @classmethod
    async def _delete_agent_instance(cls, agent_wrapper: dict):
        """
        Asynchronously deletes the specified chart agent instance from the Azure AI project.

        Args:
            agent_wrapper (dict): Dictionary containing the 'agent' and 'client' to be removed.
        """
        agent_wrapper["client"].agents.delete_agent(agent_wrapper["agent"].id)
