"""Foundry enrichment agent lifecycle — created before file processing, deleted after.

A single Foundry agent (created via AIProjectClient) is used for batch enrichment
(entities, relationships, metadata, filter schema) instead of raw chat completions.
"""

import asyncio
import logging
import os
import threading

from src.api.config import get_settings

logger = logging.getLogger(__name__)

_suffix = get_settings().solution_suffix
ENRICHMENT_AGENT_NAME = f"EnrichmentAgent-{_suffix}" if _suffix else "EnrichmentAgent"

_INSTRUCTIONS = (
    "You are a data preparation system. For each document, extract entities, "
    "relationships, topics and grounded metadata, and generate a normalized filter "
    "schema across the dataset. Be domain-agnostic. Output strictly valid JSON only."
)


class EnrichmentAgentManager:
    """Create, run, and delete a single Foundry agent used for batch enrichment."""

    def __init__(self):
        self._name: str | None = None
        self._lock = threading.Lock()

    def _endpoint(self) -> str:
        settings = get_settings()
        return (os.getenv("AZURE_AI_AGENT_ENDPOINT") or settings.azure_ai_agent_endpoint or "").strip()

    def create(self) -> str | None:
        """Create the enrichment agent if not already created. Idempotent per process."""
        with self._lock:
            if self._name:
                return self._name
            endpoint = self._endpoint()
            if not endpoint:
                logger.warning("Enrichment agent: AZURE_AI_AGENT_ENDPOINT not set — enrichment disabled")
                return None
            settings = get_settings()
            try:
                async def _create():
                    from azure.identity.aio import DefaultAzureCredential as AsyncCred
                    from azure.ai.projects.aio import AIProjectClient
                    from azure.ai.projects.models import PromptAgentDefinition
                    async with AsyncCred() as cred, AIProjectClient(endpoint=endpoint, credential=cred) as pc:
                        # Reuse the agent if it already exists; otherwise create it.
                        try:
                            if await pc.agents.get(ENRICHMENT_AGENT_NAME):
                                return False
                        except Exception:
                            pass  # Not found — create below
                        await pc.agents.create_version(
                            agent_name=ENRICHMENT_AGENT_NAME,
                            definition=PromptAgentDefinition(
                                model=settings.azure_openai_chat_deployment,
                                instructions=_INSTRUCTIONS,
                            ),
                        )
                        return True
                created = asyncio.run(_create())
                self._name = ENRICHMENT_AGENT_NAME
                logger.info(
                    f"{'Created' if created else 'Reusing existing'} enrichment agent '{ENRICHMENT_AGENT_NAME}'"
                )
                return self._name
            except Exception as e:
                logger.warning(f"Enrichment agent create failed: {e}")
                return None

    def run(self, prompt: str) -> str:
        """Run a prompt against the enrichment agent and return its text."""
        name = self.create()
        if not name:
            raise RuntimeError("Enrichment agent unavailable")
        endpoint = self._endpoint()

        async def _run() -> str:
            from azure.identity.aio import DefaultAzureCredential as AsyncCred
            from azure.ai.projects.aio import AIProjectClient
            from agent_framework_foundry import FoundryAgent
            async with AsyncCred() as cred, AIProjectClient(endpoint=endpoint, credential=cred) as pc:
                agent = FoundryAgent(project_client=pc, agent_name=name)
                # Create a fresh conversation, use it, then delete it.
                openai_client = pc.get_openai_client()
                try:
                    conversation = await openai_client.conversations.create()
                    conversation_id = conversation.id
                    try:
                        result = await agent.run(prompt, options={"conversation_id": conversation_id})
                        return str(result.text) if result and result.text else ""
                    finally:
                        try:
                            await openai_client.conversations.delete(conversation_id=conversation_id)
                        except Exception:
                            pass
                finally:
                    try:
                        await openai_client.close()
                    except Exception:
                        pass

        return asyncio.run(_run())

    def delete(self):
        """Delete the enrichment agent if it exists. Called after all files are processed."""
        with self._lock:
            if not self._name:
                return
            name = self._name
            endpoint = self._endpoint()
            self._name = None
        try:
            async def _delete():
                from azure.identity.aio import DefaultAzureCredential as AsyncCred
                from azure.ai.projects.aio import AIProjectClient
                async with AsyncCred() as cred, AIProjectClient(endpoint=endpoint, credential=cred) as pc:
                    await pc.agents.delete(name)
            asyncio.run(_delete())
            logger.info(f"Deleted enrichment agent '{name}'")
        except Exception as e:
            logger.warning(f"Enrichment agent delete failed: {e}")


enrichment_agent_manager = EnrichmentAgentManager()
