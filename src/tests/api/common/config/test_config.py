import os
import pytest
from unittest.mock import patch
from common.config.config import Config


@pytest.fixture
def mock_env_vars():
    return {
        "SQLDB_DATABASE": "test_db",
        "SQLDB_SERVER": "test_server",
        "SQLDB_USERNAME": "test_user",
        "SQLDB_USER_MID": "test_mid",
        "AZURE_OPENAI_ENDPOINT": "https://openai.test",
        "AZURE_OPENAI_DEPLOYMENT_MODEL": "gpt-4",
        "AZURE_OPENAI_API_VERSION": "2023-03-15-preview",
        "AZURE_OPENAI_RESOURCE": "test_resource",
        "AZURE_AI_SEARCH_ENDPOINT": "https://search.test",
        "AZURE_AI_SEARCH_API_KEY": "search_key",
        "AZURE_AI_SEARCH_INDEX": "test_index",
        "USE_AI_PROJECT_CLIENT": "true",
        "AZURE_AI_PROJECT_CONN_STRING": "Endpoint=sb://test/",
        "USE_CHAT_HISTORY_ENABLED": "TRUE",
        "AZURE_COSMOSDB_DATABASE": "cosmos_db",
        "AZURE_COSMOSDB_ACCOUNT": "cosmos_account",
        "AZURE_COSMOSDB_CONVERSATIONS_CONTAINER": "convo_container",
        "AZURE_COSMOSDB_ENABLE_FEEDBACK": "True"
    }


def test_config_initialization(mock_env_vars):
    with patch.dict(os.environ, mock_env_vars, clear=True):
        config = Config()

        # SQL DB config
        assert config.sqldb_database == "test_db"
        assert config.sqldb_server == "test_server"
        assert config.sqldb_username == "test_user"
        assert config.driver == "{ODBC Driver 17 for SQL Server}"
        assert config.mid_id == "test_mid"

        # Azure OpenAI config
        assert config.azure_openai_endpoint == "https://openai.test"
        assert config.azure_openai_deployment_model == "gpt-4"
        assert config.azure_openai_api_version == "2023-03-15-preview"
        assert config.azure_openai_resource == "test_resource"

        # Azure AI Search config
        assert config.azure_ai_search_endpoint == "https://search.test"
        assert config.azure_ai_search_api_key == "search_key"
        assert config.azure_ai_search_index == "test_index"

        # AI Project Client
        assert config.use_ai_project_client is True

        # Chat history config
        assert config.use_chat_history_enabled is True
        assert config.azure_cosmosdb_database == "cosmos_db"
        assert config.azure_cosmosdb_account == "cosmos_account"
        assert config.azure_cosmosdb_conversations_container == "convo_container"
        assert config.azure_cosmosdb_enable_feedback is True
