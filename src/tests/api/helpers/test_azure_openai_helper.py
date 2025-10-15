from unittest.mock import patch, MagicMock
import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../api")))

import helpers.azure_openai_helper as azure_openai_helper

class TestAzureOpenAIHelper:
    @patch("helpers.azure_openai_helper.openai.AzureOpenAI")
    @patch("helpers.azure_openai_helper.get_bearer_token_provider")
    @patch("helpers.azure_openai_helper.get_azure_credential")
    @patch("helpers.azure_openai_helper.Config")
    def test_get_azure_openai_client(
        self, mock_config, mock_get_azure_credential, mock_token_provider, mock_azure_openai
    ):
        """Test that get_azure_openai_client returns a properly configured client."""
        # Arrange
        mock_config_instance = MagicMock()
        mock_config_instance.azure_openai_endpoint = "https://test-endpoint"
        mock_config_instance.azure_openai_api_version = "2024-01-01"
        mock_config.return_value = mock_config_instance

        mock_credential = MagicMock()
        mock_get_azure_credential.return_value = mock_credential

        mock_token = MagicMock()
        mock_token_provider.return_value = mock_token

        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client

        # Act
        client = azure_openai_helper.get_azure_openai_client()

        # Assert
        mock_config.assert_called_once()
        mock_get_azure_credential.assert_called_once()
        mock_token_provider.assert_called_once_with(
            mock_credential, "https://cognitiveservices.azure.com/.default"
        )
        mock_azure_openai.assert_called_once_with(
            azure_endpoint="https://test-endpoint",
            api_version="2024-01-01",
            azure_ad_token_provider=mock_token,
        )
        assert client == mock_client