from unittest.mock import patch, MagicMock
import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../api")))

import helpers.azure_credential_utils as azure_credential_utils

@pytest.fixture
def mock_env_vars():
    return {
        "APP_ENV": "dev"
    }

class TestAzureCredentialUtils:
    @patch.dict(os.environ, {}, clear=True)
    @patch("helpers.azure_credential_utils.AzureCliCredential")
    @patch("helpers.azure_credential_utils.ManagedIdentityCredential")
    def test_get_azure_credential_dev_env(self, mock_managed_identity_credential, mock_azure_cli_credential, mock_env_vars):
        """Test get_azure_credential in dev environment."""
        # Arrange
        os.environ.update(mock_env_vars)
        mock_credential_instance = MagicMock()
        mock_azure_cli_credential.return_value = mock_credential_instance

        # Act
        credential = azure_credential_utils.get_azure_credential()

        # Assert
        mock_azure_cli_credential.assert_called_once()
        mock_managed_identity_credential.assert_not_called()
        assert credential == mock_credential_instance


    @patch.dict(os.environ, {}, clear=True)
    @patch("helpers.azure_credential_utils.AzureCliCredential")
    @patch("helpers.azure_credential_utils.ManagedIdentityCredential")
    def test_get_azure_credential_non_dev_env(self, mock_managed_identity_credential, mock_azure_cli_credential, mock_env_vars):
        """Test get_azure_credential in non-dev environment."""
        # Arrange
        mock_env_vars["APP_ENV"] = "prod"
        os.environ.update(mock_env_vars)
        mock_managed_credential = MagicMock()
        mock_managed_identity_credential.return_value = mock_managed_credential

        # Act
        credential = azure_credential_utils.get_azure_credential(client_id="test-client-id")

        # Assert
        mock_managed_identity_credential.assert_called_once_with(client_id="test-client-id")
        mock_azure_cli_credential.assert_not_called()
        assert credential == mock_managed_credential

    @pytest.mark.asyncio
    @patch.dict(os.environ, {}, clear=True)
    @patch("helpers.azure_credential_utils.AioAzureCliCredential")
    @patch("helpers.azure_credential_utils.AioManagedIdentityCredential")
    async def test_get_azure_credential_async_dev_env(self, mock_aio_managed_identity_credential, mock_aio_azure_cli_credential, mock_env_vars):
        """Test get_azure_credential_async in dev environment."""
        # Arrange
        os.environ.update(mock_env_vars)
        mock_credential_instance = MagicMock()
        mock_aio_azure_cli_credential.return_value = mock_credential_instance

        # Act
        credential = await azure_credential_utils.get_azure_credential_async()

        # Assert
        mock_aio_azure_cli_credential.assert_called_once()
        mock_aio_managed_identity_credential.assert_not_called()
        assert credential == mock_credential_instance

    @pytest.mark.asyncio
    @patch.dict(os.environ, {}, clear=True)
    @patch("helpers.azure_credential_utils.AioAzureCliCredential")
    @patch("helpers.azure_credential_utils.AioManagedIdentityCredential")
    async def test_get_azure_credential_async_non_dev_env(self, mock_aio_managed_identity_credential, mock_aio_azure_cli_credential, mock_env_vars):
        """Test get_azure_credential_async in non-dev environment."""
        # Arrange
        mock_env_vars["APP_ENV"] = "prod"
        os.environ.update(mock_env_vars)
        mock_aio_managed_credential = MagicMock()
        mock_aio_managed_identity_credential.return_value = mock_aio_managed_credential

        # Act
        credential = await azure_credential_utils.get_azure_credential_async(client_id="test-client-id")

        # Assert
        mock_aio_managed_identity_credential.assert_called_once_with(client_id="test-client-id")
        mock_aio_azure_cli_credential.assert_not_called()
        assert credential == mock_aio_managed_credential