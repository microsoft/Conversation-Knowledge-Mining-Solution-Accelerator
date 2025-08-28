import json
import time
import uuid
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../api")))

from helpers.chat_helper import process_rag_response, complete_chat_request


class TestChatHelper:
    @patch("helpers.chat_helper.Config")
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    def test_process_rag_response_success(self, mock_azure_openai, mock_config):
        # Mock the Azure OpenAI client and its response
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Mock the completion response
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"type": "bar", "data": {"labels": ["A", "B"], "datasets": [{"data": [1, 2]}]}}'
        mock_client.chat.completions.create.return_value = mock_completion
        
        # Mock the config
        mock_config.return_value.azure_openai_endpoint = "https://test-endpoint"
        mock_config.return_value.azure_openai_api_version = "2023-05-15"
        mock_config.return_value.azure_openai_deployment_model = "gpt-4"
        
        # Test the function
        result = process_rag_response("Sample RAG response with numbers: 10, 20", "Generate a chart")
        
        # Assert the result is as expected
        expected = {"type": "bar", "data": {"labels": ["A", "B"], "datasets": [{"data": [1, 2]}]}}
        assert result == expected
        
        # Verify that the client was called correctly
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args[1]
        assert call_args["model"] == "gpt-4"
        assert call_args["temperature"] == 0
        assert len(call_args["messages"]) == 2
        assert call_args["messages"][0]["role"] == "system"
        assert call_args["messages"][1]["role"] == "user"

    @patch("helpers.chat_helper.Config")
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    def test_process_rag_response_with_code_blocks(self, mock_azure_openai, mock_config):
        # Mock the Azure OpenAI client and its response
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Mock the completion response - test handling of code blocks
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '```json\n{"type": "line", "data": {"labels": ["X", "Y"], "datasets": [{"data": [5, 10]}]}}\n```'
        mock_client.chat.completions.create.return_value = mock_completion
        
        # Mock the config
        mock_config.return_value.azure_openai_endpoint = "https://test-endpoint"
        mock_config.return_value.azure_openai_api_version = "2023-05-15"
        mock_config.return_value.azure_openai_deployment_model = "gpt-4"
        
        # Test the function
        result = process_rag_response("Sample RAG response with data", "Create a line chart")
        
        # Assert the result is as expected (code blocks removed)
        expected = {"type": "line", "data": {"labels": ["X", "Y"], "datasets": [{"data": [5, 10]}]}}
        assert result == expected

    @patch("helpers.chat_helper.Config")
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    def test_process_rag_response_error(self, mock_azure_openai, mock_config):
        # Mock the Azure OpenAI client
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Make the client raise an exception
        mock_client.chat.completions.create.side_effect = Exception("Test error")
        
        # Mock the config
        mock_config.return_value.azure_openai_endpoint = "https://test-endpoint"
        mock_config.return_value.azure_openai_api_version = "2023-05-15"
        
        # Test the function
        result = process_rag_response("Sample RAG response", "Generate a chart")
        
        # Assert error handling works
        assert "error" in result
        assert result["error"] == "Chart could not be generated from this data. Please ask a different question."

    @patch("helpers.chat_helper.Config")
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    def test_process_rag_response_invalid_json(self, mock_azure_openai, mock_config):
        # Mock the Azure OpenAI client
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Return invalid JSON
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"type": "bar", "invalid": json}'
        mock_client.chat.completions.create.return_value = mock_completion
        
        # Mock the config
        mock_config.return_value.azure_openai_endpoint = "https://test-endpoint"
        mock_config.return_value.azure_openai_api_version = "2023-05-15"
        
        # Test the function
        result = process_rag_response("Sample RAG response", "Generate a chart")
        
        # Assert JSON parsing error is handled
        assert "error" in result
        assert result["error"] == "Chart could not be generated from this data. Please ask a different question."

    @pytest.mark.asyncio
    @patch("helpers.chat_helper.process_rag_response")
    @patch("helpers.chat_helper.time.time")
    @patch("helpers.chat_helper.uuid.uuid4")
    async def test_complete_chat_request_success(self, mock_uuid4, mock_time, mock_process_rag):
        # Setup mocks
        mock_uuid4.return_value = "test-uuid"
        mock_time.return_value = 1234567890
        
        # Mock successful chart data generation
        chart_data = {"type": "bar", "data": {"labels": ["A", "B"], "datasets": [{"data": [1, 2]}]}}
        mock_process_rag.return_value = chart_data
        
        # Test the function
        result = await complete_chat_request("Create a chart", "Sample RAG response")
        
        # Assert the result is as expected
        expected = {
            "id": "test-uuid",
            "model": "azure-openai",
            "created": 1234567890,
            "object": chart_data
        }
        assert result == expected
        
        # Verify process_rag_response was called with correct arguments
        mock_process_rag.assert_called_once_with("Sample RAG response", "Create a chart")

    @pytest.mark.asyncio
    async def test_complete_chat_request_no_rag_response(self):
        # Test with no RAG response
        result = await complete_chat_request("Create a chart", None)
        
        # Assert proper error handling
        assert "error" in result
        assert result["error"] == "A previous RAG response is required to generate a chart."

    @pytest.mark.asyncio
    @patch("helpers.chat_helper.process_rag_response")
    async def test_complete_chat_request_process_error(self, mock_process_rag):
        # Mock process_rag_response to return an error
        mock_process_rag.return_value = {"error": "Some processing error"}
        
        # Test the function
        result = await complete_chat_request("Create a chart", "Sample RAG response")
        
        # Assert error is passed through correctly
        assert "error" in result
        assert result["error"] == "Chart could not be generated from this data. Please ask a different question."
        assert "error_desc" in result
        assert result["error_desc"] == "{'error': 'Some processing error'}"

    @pytest.mark.asyncio
    @patch("helpers.chat_helper.process_rag_response")
    async def test_complete_chat_request_empty_result(self, mock_process_rag):
        # Mock process_rag_response to return None
        mock_process_rag.return_value = None
        
        # Test the function
        result = await complete_chat_request("Create a chart", "Sample RAG response")
        
        # Assert error handling for empty results
        assert "error" in result
        assert result["error"] == "Chart could not be generated from this data. Please ask a different question."