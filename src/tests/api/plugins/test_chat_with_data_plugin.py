import pytest
from unittest.mock import patch, MagicMock, AsyncMock, Mock
from plugins.chat_with_data_plugin import ChatWithDataPlugin
from azure.ai.agents.models import (RunStepToolCallDetails, MessageRole, ListSortOrder)


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
    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.execute_sql_query", new_callable=AsyncMock)
    @patch("plugins.chat_with_data_plugin.SQLAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_get_database_metrics_with_sql_agent(self, mock_get_agent, mock_execute_sql, chat_plugin):
        # Mocks
        mock_agent = MagicMock()
        mock_agent.id = "agent-id"
        mock_client = MagicMock()

        # Set return value for get_agent
        mock_get_agent.return_value = {"agent": mock_agent, "client": mock_client}

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.id = "thread-id"
        mock_client.agents.threads.create.return_value = mock_thread

        # Mock message creation: no return needed

        # Mock run creation and success status
        mock_run = MagicMock()
        mock_run.status = "succeeded"
        mock_client.agents.runs.create_and_process.return_value = mock_run

        # Mock response message with SQL text
        mock_agent_msg = MagicMock()
        mock_agent_msg.role = MessageRole.AGENT
        mock_agent_msg.text_messages = [MagicMock(text=MagicMock(value="```sql\nSELECT CAST(StartTime AS DATE) AS date, COUNT(*) AS total_calls FROM km_processed_data WHERE StartTime >= DATEADD(DAY, -7, GETDATE()) GROUP BY CAST(StartTime AS DATE) ORDER BY date ASC;\n```"))]
        mock_client.agents.messages.list.return_value = [mock_agent_msg]

        # Mock final SQL execution
        mock_execute_sql.return_value = "(datetime.date(2025, 6, 27), 11)(datetime.date(2025, 6, 28), 20)(datetime.date(2025, 6, 29), 29)(datetime.date(2025, 6, 30), 17)(datetime.date(2025, 7, 1), 19)(datetime.date(2025, 7, 2), 16)"

        # Mock thread deletion
        mock_client.agents.threads.delete.return_value = None

        # Act
        result = await chat_plugin.get_database_metrics("Total number of calls by date for last 7 days")

        # Assert
        assert result == "(datetime.date(2025, 6, 27), 11)(datetime.date(2025, 6, 28), 20)(datetime.date(2025, 6, 29), 29)(datetime.date(2025, 6, 30), 17)(datetime.date(2025, 7, 1), 19)(datetime.date(2025, 7, 2), 16)"
        mock_execute_sql.assert_called_once_with("SELECT CAST(StartTime AS DATE) AS date, COUNT(*) AS total_calls FROM km_processed_data WHERE StartTime >= DATEADD(DAY, -7, GETDATE()) GROUP BY CAST(StartTime AS DATE) ORDER BY date ASC;")
        mock_client.agents.threads.create.assert_called_once()
        mock_client.agents.messages.create.assert_called_once()
        mock_client.agents.runs.create_and_process.assert_called_once()
        mock_client.agents.messages.list.assert_called_once_with(thread_id="thread-id", order=ListSortOrder.ASCENDING)
        mock_client.agents.threads.delete.assert_called_once_with(thread_id="thread-id")

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.execute_sql_query")
    @patch("plugins.chat_with_data_plugin.SQLAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_get_database_metrics_exception(self, mock_get_agent, mock_execute_sql, chat_plugin):
        # Setup mock to raise exception
        mock_get_agent.side_effect = Exception("Test error")
        
        # Call the method
        result = await chat_plugin.get_database_metrics("Show me data")
        
        # Assertions
        assert result == "Details could not be retrieved. Please try again later."
        mock_execute_sql.assert_not_called()


    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.SearchAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_get_call_insights_success(self, mock_get_agent, chat_plugin):
        # Use the fixture passed by pytest
        self.chat_plugin = chat_plugin  # or just use `chat_plugin` directly

        # Mock agent and client setup
        mock_agent = MagicMock()
        mock_agent.id = "mock-agent-id"
        mock_client = MagicMock()
        mock_get_agent.return_value = {"agent": mock_agent, "client": mock_client}

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.id = "thread-id"
        mock_client.agents.threads.create.return_value = mock_thread

        # Mock run creation
        mock_run = MagicMock()
        mock_run.status = "succeeded"
        mock_run.id = "run-id"
        mock_client.agents.runs.create_and_process.return_value = mock_run

        # Mock run steps
        mock_run_step = MagicMock()
        mock_run_step.step_details = RunStepToolCallDetails(tool_calls=[
            {
                "azure_ai_search": {
                    "output": str({
                        "metadata": {
                            "get_urls": ["https://example.com/doc1"],
                            "titles": ["Document Title 1"]
                        }
                    })
                }
            }
        ])
        mock_client.agents.run_steps.list.return_value = [mock_run_step]

        # Mock agent message with answer
        mock_agent_msg = MagicMock()
        mock_agent_msg.role = MessageRole.AGENT
        mock_agent_msg.text_messages = [MagicMock(text=MagicMock(value="This is a test answer with citation 【3:0†source】"))]
        mock_client.agents.messages.list.return_value = [mock_agent_msg]

        # Mock thread deletion
        mock_client.agents.threads.delete.return_value = None

        # Call the method
        result = await chat_plugin.get_call_insights("What is the summary?")

        # Assert
        assert isinstance(result, dict)
        assert result["answer"] == "This is a test answer with citation [1]"
        assert result["citations"] == [{"url": "https://example.com/doc1", "title": "Document Title 1"}]

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.SearchAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_get_call_insights_exception(self, mock_get_agent, chat_plugin):
        # Setup the mock to raise an exception
        mock_get_agent.side_effect = Exception("Test error")

        # Call the method
        result = await chat_plugin.get_call_insights("Sample question")

        # Assertions
        assert result == "Details could not be retrieved. Please try again later."

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.ChartAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_generate_chart_data_success(self, mock_get_agent, chat_plugin):
        # Mock agent and client setup
        mock_agent = MagicMock()
        mock_agent.id = "chart-agent-id"
        mock_client = MagicMock()
        mock_get_agent.return_value = {"agent": mock_agent, "client": mock_client}

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.id = "thread-id"
        mock_client.agents.threads.create.return_value = mock_thread

        # Mock run creation and success status
        mock_run = MagicMock()
        mock_run.status = "succeeded"
        mock_client.agents.runs.create_and_process.return_value = mock_run

        # Mock Chart.js compatible JSON response
        chart_json = '{"type": "bar", "data": {"labels": ["2025-06-27", "2025-06-28"], "datasets": [{"label": "Total Calls", "data": [11, 20]}]}}'
        mock_agent_msg = MagicMock()
        mock_agent_msg.role = MessageRole.AGENT
        mock_agent_msg.text_messages = [MagicMock(text=MagicMock(value=chart_json))]
        mock_client.agents.messages.list.return_value = [mock_agent_msg]

        # Mock thread deletion
        mock_client.agents.threads.delete.return_value = None

        # Call the method with combined input
        result = await chat_plugin.generate_chart_data(
            "Create a bar chart. Total calls by date: 2025-06-27: 11, 2025-06-28: 20"
        )

        # Assert
        assert result == chart_json
        mock_client.agents.threads.create.assert_called_once()
        mock_client.agents.messages.create.assert_called_once_with(
            thread_id="thread-id",
            role=MessageRole.USER,
            content="Create a bar chart. Total calls by date: 2025-06-27: 11, 2025-06-28: 20"
        )
        mock_client.agents.runs.create_and_process.assert_called_once_with(
            thread_id="thread-id",
            agent_id="chart-agent-id"
        )
        mock_client.agents.messages.list.assert_called_once_with(thread_id="thread-id", order=ListSortOrder.ASCENDING)
        mock_client.agents.threads.delete.assert_called_once_with(thread_id="thread-id")

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.ChartAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_generate_chart_data_failed_run(self, mock_get_agent, chat_plugin):
        # Mock agent and client setup
        mock_agent = MagicMock()
        mock_agent.id = "chart-agent-id"
        mock_client = MagicMock()
        mock_get_agent.return_value = {"agent": mock_agent, "client": mock_client}

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.id = "thread-id"
        mock_client.agents.threads.create.return_value = mock_thread

        # Mock run creation with failed status
        mock_run = MagicMock()
        mock_run.status = "failed"
        mock_run.last_error = "Chart generation failed"
        mock_client.agents.runs.create_and_process.return_value = mock_run

        # Call the method with single input parameter
        result = await chat_plugin.generate_chart_data("Create a chart with some data")

        # Assert
        assert result == "Details could not be retrieved. Please try again later."
        mock_client.agents.threads.create.assert_called_once()
        mock_client.agents.messages.create.assert_called_once()
        mock_client.agents.runs.create_and_process.assert_called_once()
        # Should not call messages.list or threads.delete when run fails
        mock_client.agents.messages.list.assert_not_called()
        mock_client.agents.threads.delete.assert_not_called()

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.ChartAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_generate_chart_data_exception(self, mock_get_agent, chat_plugin):
        # Setup mock to raise exception
        mock_get_agent.side_effect = Exception("Chart agent error")

        # Call the method with single input parameter
        result = await chat_plugin.generate_chart_data("Create a chart with some data")

        # Assert
        assert result == "Details could not be retrieved. Please try again later."

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.ChartAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_generate_chart_data_empty_response(self, mock_get_agent, chat_plugin):
        # Mock agent and client setup
        mock_agent = MagicMock()
        mock_agent.id = "chart-agent-id"
        mock_client = MagicMock()
        mock_get_agent.return_value = {"agent": mock_agent, "client": mock_client}

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.id = "thread-id"
        mock_client.agents.threads.create.return_value = mock_thread

        # Mock run creation and success status
        mock_run = MagicMock()
        mock_run.status = "succeeded"
        mock_client.agents.runs.create_and_process.return_value = mock_run

        # Mock empty messages list
        mock_client.agents.messages.list.return_value = []

        # Mock thread deletion
        mock_client.agents.threads.delete.return_value = None

        # Call the method with single input parameter
        result = await chat_plugin.generate_chart_data("Create a chart with some data")

        # Assert - should return empty string when no agent messages found
        assert result == ""
        mock_client.agents.threads.delete.assert_called_once_with(thread_id="thread-id")

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.SearchAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_chat_with_multiple_citations_out_of_order(self, mock_get_agent, chat_plugin):
        """Test citation mapping with multiple citations appearing out-of-order in the answer"""
        # Mock agent and client setup
        mock_agent = MagicMock()
        mock_agent.id = "search-agent-id"
        mock_client = MagicMock()
        mock_get_agent.return_value = {"agent": mock_agent, "client": mock_client}

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.id = "thread-id"
        mock_client.agents.threads.create.return_value = mock_thread

        # Mock run creation and success status
        mock_run = MagicMock()
        mock_run.status = "succeeded"
        mock_client.agents.runs.create_and_process.return_value = mock_run

        # Mock run steps with multiple citations (indices 0, 1, 2, 3)
        mock_step = MagicMock()
        mock_step.step_details = RunStepToolCallDetails(tool_calls=[
            {
                'azure_ai_search': {
                    'output': str({
                        "metadata": {
                            "get_urls": [
                                "https://example.com/doc0",
                                "https://example.com/doc1", 
                                "https://example.com/doc2",
                                "https://example.com/doc3"
                            ],
                            "titles": ["Doc 0", "Doc 1", "Doc 2", "Doc 3"]
                        }
                    })
                }
            }
        ])
        mock_client.agents.run_steps.list.return_value = [mock_step]

        # Mock messages with out-of-order citation markers: [2], [0], [3], [1]
        mock_message = MagicMock()
        mock_message.role = MessageRole.AGENT
        mock_text = MagicMock()
        mock_text.text = MagicMock()
        mock_text.text.value = "First point【0:2†source】, second【0:0†source】, third【0:3†source】, fourth【0:1†source】."
        mock_message.text_messages = [mock_text]
        mock_client.agents.messages.list.return_value = [mock_message]

        # Mock thread deletion
        mock_client.agents.threads.delete.return_value = None

        # Call the method
        result = await chat_plugin.get_call_insights("Test query")

        # Assert - markers should be renumbered to [1], [2], [3], [4] in order of appearance
        # and citations should be reordered to match
        assert result["answer"] == "First point[1], second[2], third[3], fourth[4]."
        assert len(result["citations"]) == 4
        # Citations should be reordered: [2, 0, 3, 1] → positions in result
        assert result["citations"][0]["url"] == "https://example.com/doc2"
        assert result["citations"][0]["title"] == "Doc 2"
        assert result["citations"][1]["url"] == "https://example.com/doc0"
        assert result["citations"][1]["title"] == "Doc 0"
        assert result["citations"][2]["url"] == "https://example.com/doc3"
        assert result["citations"][2]["title"] == "Doc 3"
        assert result["citations"][3]["url"] == "https://example.com/doc1"
        assert result["citations"][3]["title"] == "Doc 1"

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.SearchAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_chat_with_out_of_range_citation_markers(self, mock_get_agent, chat_plugin):
        """Test citation mapping with gaps and out-of-range marker indices"""
        # Mock agent and client setup
        mock_agent = MagicMock()
        mock_agent.id = "search-agent-id"
        mock_client = MagicMock()
        mock_get_agent.return_value = {"agent": mock_agent, "client": mock_client}

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.id = "thread-id"
        mock_client.agents.threads.create.return_value = mock_thread

        # Mock run creation and success status
        mock_run = MagicMock()
        mock_run.status = "succeeded"
        mock_client.agents.runs.create_and_process.return_value = mock_run

        # Mock run steps with only 2 citations (indices 0, 1)
        mock_step = MagicMock()
        mock_step.step_details = RunStepToolCallDetails(tool_calls=[
            {
                'azure_ai_search': {
                    'output': str({
                        "metadata": {
                            "get_urls": [
                                "https://example.com/valid1",
                                "https://example.com/valid2"
                            ],
                            "titles": ["Valid Doc 1", "Valid Doc 2"]
                        }
                    })
                }
            }
        ])
        mock_client.agents.run_steps.list.return_value = [mock_step]

        # Mock messages with valid and out-of-range markers: [1] (valid), [5] (invalid), [0] (valid), [10] (invalid)
        mock_message = MagicMock()
        mock_message.role = MessageRole.AGENT
        mock_text = MagicMock()
        mock_text.text = MagicMock()
        mock_text.text.value = "Valid【0:1†source】, invalid【0:5†source】, another valid【0:0†source】, invalid again【0:10†source】."
        mock_message.text_messages = [mock_text]
        mock_client.agents.messages.list.return_value = [mock_message]

        # Mock thread deletion
        mock_client.agents.threads.delete.return_value = None

        # Call the method
        result = await chat_plugin.get_call_insights("Test query")

        # Assert - out-of-range markers should be removed, valid ones renumbered
        assert result["answer"] == "Valid[1], invalid, another valid[2], invalid again."
        assert len(result["citations"]) == 2
        # Only valid citations should be included, in order of appearance: [1, 0]
        assert result["citations"][0]["url"] == "https://example.com/valid2"
        assert result["citations"][0]["title"] == "Valid Doc 2"
        assert result["citations"][1]["url"] == "https://example.com/valid1"
        assert result["citations"][1]["title"] == "Valid Doc 1"

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.SearchAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_chat_with_unused_citations(self, mock_get_agent, chat_plugin):
        """Test that unused citations are filtered out"""
        # Mock agent and client setup
        mock_agent = MagicMock()
        mock_agent.id = "search-agent-id"
        mock_client = MagicMock()
        mock_get_agent.return_value = {"agent": mock_agent, "client": mock_client}

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.id = "thread-id"
        mock_client.agents.threads.create.return_value = mock_thread

        # Mock run creation and success status
        mock_run = MagicMock()
        mock_run.status = "succeeded"
        mock_client.agents.runs.create_and_process.return_value = mock_run

        # Mock run steps with 5 citations but only 3 will be used
        mock_step = MagicMock()
        mock_step.step_details = RunStepToolCallDetails(tool_calls=[
            {
                'azure_ai_search': {
                    'output': str({
                        "metadata": {
                            "get_urls": [
                                "https://example.com/doc0",
                                "https://example.com/doc1",
                                "https://example.com/doc2",  # unused
                                "https://example.com/doc3",
                                "https://example.com/doc4"   # unused
                            ],
                            "titles": ["Doc 0", "Doc 1", "Doc 2", "Doc 3", "Doc 4"]
                        }
                    })
                }
            }
        ])
        mock_client.agents.run_steps.list.return_value = [mock_step]

        # Mock messages with only citations to indices 1, 3, 0
        mock_message = MagicMock()
        mock_message.role = MessageRole.AGENT
        mock_text = MagicMock()
        mock_text.text = MagicMock()
        mock_text.text.value = "First【0:1†source】, second【0:3†source】, third【0:0†source】."
        mock_message.text_messages = [mock_text]
        mock_client.agents.messages.list.return_value = [mock_message]

        # Mock thread deletion
        mock_client.agents.threads.delete.return_value = None

        # Call the method
        result = await chat_plugin.get_call_insights("Test query")

        # Assert - only cited documents should be in citations list
        assert result["answer"] == "First[1], second[2], third[3]."
        assert len(result["citations"]) == 3
        # Citations should only include the used ones: [1, 3, 0]
        assert result["citations"][0]["url"] == "https://example.com/doc1"
        assert result["citations"][1]["url"] == "https://example.com/doc3"
        assert result["citations"][2]["url"] == "https://example.com/doc0"

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.SearchAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_chat_with_all_out_of_range_citations_clears_list(self, mock_get_agent, chat_plugin):
        """Test that citations list is cleared when all markers are out-of-range"""
        # Mock agent and client setup
        mock_agent = MagicMock()
        mock_agent.id = "search-agent-id"
        mock_client = MagicMock()
        mock_get_agent.return_value = {"agent": mock_agent, "client": mock_client}

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.id = "thread-id"
        mock_client.agents.threads.create.return_value = mock_thread

        # Mock run creation and success status
        mock_run = MagicMock()
        mock_run.status = "succeeded"
        mock_client.agents.runs.create_and_process.return_value = mock_run

        # Mock run steps with 2 citations
        mock_step = MagicMock()
        mock_step.step_details = RunStepToolCallDetails(tool_calls=[
            {
                'azure_ai_search': {
                    'output': str({
                        "metadata": {
                            "get_urls": [
                                "https://example.com/doc0",
                                "https://example.com/doc1"
                            ],
                            "titles": ["Doc 0", "Doc 1"]
                        }
                    })
                }
            }
        ])
        mock_client.agents.run_steps.list.return_value = [mock_step]

        # Mock messages with only out-of-range markers
        mock_message = MagicMock()
        mock_message.role = MessageRole.AGENT
        mock_text = MagicMock()
        mock_text.text = MagicMock()
        mock_text.text.value = "Invalid【0:5†source】 and another【0:10†source】."
        mock_message.text_messages = [mock_text]
        mock_client.agents.messages.list.return_value = [mock_message]

        # Mock thread deletion
        mock_client.agents.threads.delete.return_value = None

        # Call the method
        result = await chat_plugin.get_call_insights("Test query")

        # Assert - all markers removed and citations list should be empty
        assert result["answer"] == "Invalid and another."
        assert len(result["citations"]) == 0

    @pytest.mark.asyncio
    @patch("plugins.chat_with_data_plugin.SearchAgentFactory.get_agent", new_callable=AsyncMock)
    async def test_chat_with_repeated_citation_markers(self, mock_get_agent, chat_plugin):
        """Test that repeated/duplicate markers map to the same new index"""
        # Mock agent and client setup
        mock_agent = MagicMock()
        mock_agent.id = "search-agent-id"
        mock_client = MagicMock()
        mock_get_agent.return_value = {"agent": mock_agent, "client": mock_client}

        # Mock thread creation
        mock_thread = MagicMock()
        mock_thread.id = "thread-id"
        mock_client.agents.threads.create.return_value = mock_thread

        # Mock run creation and success status
        mock_run = MagicMock()
        mock_run.status = "succeeded"
        mock_client.agents.runs.create_and_process.return_value = mock_run

        # Mock run steps with 3 citations
        mock_step = MagicMock()
        mock_step.step_details = RunStepToolCallDetails(tool_calls=[
            {
                'azure_ai_search': {
                    'output': str({
                        "metadata": {
                            "get_urls": [
                                "https://example.com/doc0",
                                "https://example.com/doc1",
                                "https://example.com/doc2"
                            ],
                            "titles": ["Doc 0", "Doc 1", "Doc 2"]
                        }
                    })
                }
            }
        ])
        mock_client.agents.run_steps.list.return_value = [mock_step]

        # Mock messages with repeated markers: [1], [2], [1] again, [0], [1] again
        mock_message = MagicMock()
        mock_message.role = MessageRole.AGENT
        mock_text = MagicMock()
        mock_text.text = MagicMock()
        mock_text.text.value = "First【0:1†source】, second【0:2†source】, repeat first【0:1†source】, third【0:0†source】, and again【0:1†source】."
        mock_message.text_messages = [mock_text]
        mock_client.agents.messages.list.return_value = [mock_message]

        # Mock thread deletion
        mock_client.agents.threads.delete.return_value = None

        # Call the method
        result = await chat_plugin.get_call_insights("Test query")

        # Assert - repeated markers should use the same new index
        # Order of first appearance: [1], [2], [0] → renumbered to [1], [2], [3]
        # All references to original [1] should become [1]
        assert result["answer"] == "First[1], second[2], repeat first[1], third[3], and again[1]."
        assert len(result["citations"]) == 3
        # Citations should be ordered by first appearance: [1, 2, 0]
        assert result["citations"][0]["url"] == "https://example.com/doc1"
        assert result["citations"][0]["title"] == "Doc 1"
        assert result["citations"][1]["url"] == "https://example.com/doc2"
        assert result["citations"][1]["title"] == "Doc 2"
        assert result["citations"][2]["url"] == "https://example.com/doc0"
        assert result["citations"][2]["title"] == "Doc 0"