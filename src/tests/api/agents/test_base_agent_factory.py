import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from common.config.config import Config
from agents.agent_factory_base import BaseAgentFactory


class MockAgentFactory(BaseAgentFactory):
    """Concrete test class extending BaseAgentFactory for unit testing."""
    _created = False
    _deleted = False

    @classmethod
    async def create_agent(cls, config: Config):
        cls._created = True
        return {"agent": "mock-agent"}

    @classmethod
    async def _delete_agent_instance(cls, agent: object):
        cls._deleted = True


@pytest.fixture(autouse=True)
def reset_factory_state():
    MockAgentFactory._agent = None
    MockAgentFactory._created = False
    MockAgentFactory._deleted = False
    yield
    MockAgentFactory._agent = None


@pytest.mark.asyncio
async def test_get_agent_creates_singleton():
    # Agent should be None initially
    assert MockAgentFactory._agent is None

    result1 = await MockAgentFactory.get_agent()
    result2 = await MockAgentFactory.get_agent()

    # Should be the same object
    assert result1 is result2
    assert MockAgentFactory._created is True
    assert MockAgentFactory._agent == {"agent": "mock-agent"}


@pytest.mark.asyncio
async def test_delete_agent_removes_singleton():
    # Set initial agent
    await MockAgentFactory.get_agent()
    assert MockAgentFactory._agent is not None

    await MockAgentFactory.delete_agent()

    assert MockAgentFactory._agent is None
    assert MockAgentFactory._deleted is True


@pytest.mark.asyncio
async def test_delete_agent_does_nothing_if_none():
    # Agent is None
    await MockAgentFactory.delete_agent()

    assert MockAgentFactory._agent is None
    assert MockAgentFactory._deleted is False


@pytest.mark.asyncio
async def test_thread_safety_of_get_agent(monkeypatch):
    # Patch create_agent to delay and track calls
    call_count = 0

    async def slow_create_agent(config):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return {"agent": "thread-safe"}

    monkeypatch.setattr(MockAgentFactory, "create_agent", slow_create_agent)

    # Run get_agent concurrently
    results = await asyncio.gather(
        MockAgentFactory.get_agent(),
        MockAgentFactory.get_agent(),
        MockAgentFactory.get_agent()
    )

    # All should return the same instance
    assert all(result == {"agent": "thread-safe"} for result in results)
    assert call_count == 1  # Only one creation
