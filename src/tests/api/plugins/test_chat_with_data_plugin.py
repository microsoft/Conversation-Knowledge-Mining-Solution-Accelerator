import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from plugins.chat_with_data_plugin import ChatWithDataPlugin


@pytest.fixture
def mock_config():
    config_mock = MagicMock()
    config_mock.azure_openai_deployment_model = "gpt-4"
    config_mock.azure_openai_endpoint = "https://test-openai.azure.com/"
    config_mock.azure_openai_api_version = "2024-02-15-preview"
    config_mock.azure_ai_search_endpoint = "https://search.test.azure.com/"
    config_mock.azure_ai_search_api_key = "search-api-key"
    config_mock.azure_ai_search_index = "test_index"
    config_mock.use_ai_project_client = False
    config_mock.azure_ai_project_conn_string = "test-connection-string"
    return config_mock


@pytest.fixture
def chat_plugin(mock_config):
    with patch("plugins.chat_with_data_plugin.Config", return_value=mock_config):
        plugin = ChatWithDataPlugin()
        return plugin


class TestChatWithDataPlugin:
    @patch("helpers.azure_openai_helper.Config")
    @patch("helpers.azure_openai_helper.get_bearer_token_provider")
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    @pytest.mark.asyncio
    async def test_greeting(self, mock_azure_openai, mock_token_provider, mock_config, chat_plugin):
        # Setup mock token provider
        mock_token_provider.return_value = lambda: "fake_token"
        
        # Setup mock client and completion response
        mock_config_instance = MagicMock()
        mock_config_instance.azure_openai_endpoint = "https://test-openai.azure.com/"
        mock_config_instance.azure_openai_api_version = "2024-02-15-preview"
        mock_config.return_value = mock_config_instance
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Hello, how can I help you?"
        mock_client.chat.completions.create.return_value = mock_completion
        mock_azure_openai.return_value = mock_client

        # Call the method
        result = await chat_plugin.greeting("Hello")

        # Assertions
        assert result == "Hello, how can I help you?"
        mock_azure_openai.assert_called_once_with(
            azure_endpoint="https://test-openai.azure.com/",
            azure_ad_token_provider=mock_token_provider.return_value,
            api_version="2024-02-15-preview"
        )
        mock_client.chat.completions.create.assert_called_once()
        args = mock_client.chat.completions.create.call_args[1]
        assert args["model"] == "gpt-4"
        assert args["temperature"] == 0
        assert len(args["messages"]) == 2
        assert args["messages"][0]["role"] == "system"
        assert args["messages"][1]["role"] == "user"
        assert args["messages"][1]["content"] == "Hello"

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.Config")
    @patch("plugins.chat_with_data_plugin.AIProjectClient")
    @patch("plugins.chat_with_data_plugin.DefaultAzureCredential")
    async def test_greeting_with_ai_project_client(self, mock_azure_credential, mock_ai_project_client, mock_config, chat_plugin):
        # Setup AIProjectClient
        chat_plugin.use_ai_project_client = True
        
        # Setup mock
        mock_config_instance = MagicMock()
        mock_config_instance.ai_project_endpoint = "https://test-openai.azure.com/"
        mock_config.return_value = mock_config_instance
        mock_credential_instance = MagicMock()
        mock_azure_credential.return_value = mock_credential_instance
        mock_project_instance = MagicMock()
        mock_ai_project_client.return_value = mock_project_instance
        mock_chat_client = MagicMock()
        mock_project_instance.inference.get_chat_completions_client.return_value = mock_chat_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Hello from AI Project Client"
        mock_chat_client.complete.return_value = mock_completion
        
        # Call the method
        result = await chat_plugin.greeting("Hello")
        
        # Assertions
        assert result == "Hello from AI Project Client"
        mock_ai_project_client.assert_called_once_with(
            endpoint=chat_plugin.ai_project_endpoint,
            credential=mock_credential_instance
        )
        mock_chat_client.complete.assert_called_once()
        args = mock_chat_client.complete.call_args[1]
        assert args["model"] == "gpt-4"
        assert args["temperature"] == 0
        assert len(args["messages"]) == 2
        assert args["messages"][0]["role"] == "system"
        assert args["messages"][1]["role"] == "user"
        assert args["messages"][1]["content"] == "Hello"

    @pytest.mark.asyncio
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    async def test_greeting_exception(self, mock_azure_openai, chat_plugin):
        # Setup mock to raise exception
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("Test error")
        
        # Call the method
        result = await chat_plugin.greeting("Hello")
        
        # Assertions
        assert result == "Details could not be retrieved. Please try again later."

    @pytest.mark.asyncio
    @patch("helpers.azure_openai_helper.Config")
    @patch("helpers.azure_openai_helper.get_bearer_token_provider")
    @patch("plugins.chat_with_data_plugin.execute_sql_query")
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    async def test_get_SQL_Response(self, mock_azure_openai, mock_execute_sql, mock_token_provider, mock_config, chat_plugin):

        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config_instance.azure_openai_endpoint = "https://test-openai.azure.com/"
        mock_config_instance.azure_openai_api_version = "2024-02-15-preview"
        mock_config.return_value = mock_config_instance
        mock_token_provider.return_value = lambda: "fake_token"
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "SELECT * FROM km_processed_data"
        mock_client.chat.completions.create.return_value = mock_completion
        
        mock_execute_sql.return_value = "Query results data"
        
        # Call the method
        result = await chat_plugin.get_SQL_Response("Show me all call data")
        
        # Assertions
        assert result == "Query results data"
        mock_azure_openai.assert_called_once_with(
            azure_endpoint="https://test-openai.azure.com/",
            azure_ad_token_provider=mock_token_provider.return_value,
            api_version="2024-02-15-preview"
        )
        mock_client.chat.completions.create.assert_called_once()
        mock_execute_sql.assert_called_once_with("SELECT * FROM km_processed_data")

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.Config")
    @patch("plugins.chat_with_data_plugin.execute_sql_query")
    @patch("plugins.chat_with_data_plugin.AIProjectClient")
    @patch("plugins.chat_with_data_plugin.DefaultAzureCredential")
    async def test_get_SQL_Response_with_ai_project_client(self, mock_azure_credential, mock_ai_project_client, mock_execute_sql, mock_config, chat_plugin):
        # Setup AIProjectClient
        chat_plugin.use_ai_project_client = True
        
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config_instance.ai_project_endpoint = "https://test-openai.azure.com/"
        mock_config.return_value = mock_config_instance
        mock_credential_instance = MagicMock()
        mock_azure_credential.return_value = mock_credential_instance
        mock_project_instance = MagicMock()
        mock_ai_project_client.return_value = mock_project_instance
        mock_client = MagicMock()
        mock_project_instance.inference.get_chat_completions_client.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "```sql\nSELECT * FROM km_processed_data\n```"
        mock_client.complete.return_value = mock_completion
        
        mock_execute_sql.return_value = "Query results data with AI Project Client"
        
        # Call the method
        result = await chat_plugin.get_SQL_Response("Show me call data")
        
        # Assertions
        assert result == "Query results data with AI Project Client"
        mock_ai_project_client.assert_called_once_with(
            endpoint=chat_plugin.ai_project_endpoint,
            credential=mock_credential_instance
        )
        mock_execute_sql.assert_called_once_with("\nSELECT * FROM km_processed_data\n")

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.execute_sql_query")
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    async def test_get_SQL_Response_exception(self, mock_azure_openai, mock_execute_sql, chat_plugin):
        # Setup mock to raise exception
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("Test error")
        
        # Call the method
        result = await chat_plugin.get_SQL_Response("Show me data")
        
        # Assertions
        assert result == "Details could not be retrieved. Please try again later."
        mock_execute_sql.assert_not_called()

    @pytest.mark.asyncio
    @patch("helpers.azure_openai_helper.Config")
    @patch("helpers.azure_openai_helper.get_bearer_token_provider")
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    async def test_get_answers_from_calltranscripts(self, mock_azure_openai, mock_token_provider, mock_config, chat_plugin):
        # Setup mock
        mock_token_provider.return_value = lambda: "fake_token"
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        mock_config_instance = MagicMock()
        mock_config_instance.azure_openai_endpoint = "https://test-openai.azure.com/"
        mock_config_instance.azure_openai_api_version = "2024-02-15-preview"
        mock_config.return_value = mock_config_instance
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message = MagicMock()
        mock_completion.choices[0].message.content = "Answer about transcripts"
        mock_client.chat.completions.create.return_value = mock_completion
        
        # Call the method
        result = await chat_plugin.get_answers_from_calltranscripts("Tell me about the call transcripts")
        
        # Assertions
        assert result.message.content == "Answer about transcripts"
        mock_azure_openai.assert_called_once_with(
            azure_endpoint="https://test-openai.azure.com/",
            azure_ad_token_provider=mock_token_provider.return_value,
            api_version="2024-02-15-preview"
        )
        mock_client.chat.completions.create.assert_called_once()
        args = mock_client.chat.completions.create.call_args[1]
        assert args["model"] == "gpt-4"
        assert args["temperature"] == 0
        assert len(args["messages"]) == 2
        assert args["messages"][0]["role"] == "system"
        assert args["messages"][1]["role"] == "user"
        assert args["messages"][1]["content"] == "Tell me about the call transcripts"
        assert "data_sources" in args["extra_body"]
        assert args["extra_body"]["data_sources"][0]["type"] == "azure_search"

    @pytest.mark.asyncio
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    async def test_get_answers_from_calltranscripts_with_citations(self, mock_azure_openai, chat_plugin):
        # Setup mock with citations in context
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_message = MagicMock()
        mock_message.content = "Answer with citations"
        
        mock_context = MagicMock()
        long_content = "This is a very long citation that should be truncated because it exceeds the 300 character limit. " * 10
        
        shared_citation_list = [{"content": long_content}]
        mock_context.get.return_value = shared_citation_list
        
        # Make 'in' operator work for checking 'citations' in context.
        mock_context.__contains__ = lambda _, key: key == 'citations'
        
        # Make the .citations attribute (used in assertions) point to the same shared list.
        mock_context.citations = shared_citation_list
        
        mock_message.context = mock_context
        mock_completion.choices[0].message = mock_message
        mock_client.chat.completions.create.return_value = mock_completion
        
        # Call the method
        result = await chat_plugin.get_answers_from_calltranscripts("Tell me about the call transcripts with citations")
        
        # Assertions
        assert result.message.content == "Answer with citations"
        assert len(result.message.context.citations[0]["content"]) <= 303  # 300 characters + "..."
        assert result.message.context.citations[0]["content"].endswith("...")

    @pytest.mark.asyncio
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    async def test_get_answers_from_calltranscripts_exception(self, mock_azure_openai, chat_plugin):
        # Setup mock to raise exception
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("Test error")
        
        # Call the method
        result = await chat_plugin.get_answers_from_calltranscripts("Question")
        
        # Assertions
        assert result == "Details could not be retrieved. Please try again later."
