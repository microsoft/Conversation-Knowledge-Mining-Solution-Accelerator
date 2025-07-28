from unittest.mock import patch, MagicMock
import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../api")))

import helpers.azure_credential_utils as azure_credential_utils

class TestAzureCredentialUtils:
    @patch("helpers.azure_credential_utils.Config")
    @patch("helpers.azure_credential_utils.DefaultAzureCredential")
    @patch("helpers.azure_credential_utils.ManagedIdentityCredential")
    def test_get_azure_credential_local_env(self, mock_managed_identity_credential, mock_default_azure_credential, mock_config):
        """Test get_azure_credential in local environment."""
        # Arrange
        mock_config_instance = MagicMock()
        mock_config_instance.app_env = "local"
        mock_config.return_value = mock_config_instance

        mock_default_credential = MagicMock()
        mock_default_azure_credential.return_value = mock_default_credential

        # Act
        credential = azure_credential_utils.get_azure_credential()

        # Assert
        mock_config.assert_called_once()
        mock_default_azure_credential.assert_called_once()
        mock_managed_identity_credential.assert_not_called()
        assert credential == mock_default_credential

    @patch("helpers.azure_credential_utils.Config")
    @patch("helpers.azure_credential_utils.DefaultAzureCredential")
    @patch("helpers.azure_credential_utils.ManagedIdentityCredential")
    def test_get_azure_credential_non_local_env(self, mock_managed_identity_credential, mock_default_azure_credential, mock_config):
        """Test get_azure_credential in non-local environment."""
        # Arrange
        mock_config_instance = MagicMock()
        mock_config_instance.app_env = "Prod"
        mock_config.return_value = mock_config_instance

        mock_managed_credential = MagicMock()
        mock_managed_identity_credential.return_value = mock_managed_credential

        # Act
        credential = azure_credential_utils.get_azure_credential(client_id="test-client-id")

        # Assert
        mock_config.assert_called_once()
        mock_managed_identity_credential.assert_called_once_with(client_id="test-client-id")
        mock_default_azure_credential.assert_not_called()
        assert credential == mock_managed_credential

    @pytest.mark.asyncio
    @patch("helpers.azure_credential_utils.Config")
    @patch("helpers.azure_credential_utils.AioDefaultAzureCredential")
    @patch("helpers.azure_credential_utils.AioManagedIdentityCredential")
    async def test_get_azure_credential_async_local_env(self, mock_aio_managed_identity_credential, mock_aio_default_azure_credential, mock_config):
        """Test get_azure_credential_async in local environment."""
        # Arrange
        mock_config_instance = MagicMock()
        mock_config_instance.app_env = "local"
        mock_config.return_value = mock_config_instance

        mock_aio_default_credential = MagicMock()
        mock_aio_default_azure_credential.return_value = mock_aio_default_credential

        # Act
        credential = await azure_credential_utils.get_azure_credential_async()

        # Assert
        mock_config.assert_called_once()
        mock_aio_default_azure_credential.assert_called_once()
        mock_aio_managed_identity_credential.assert_not_called()
        assert credential == mock_aio_default_credential

    @pytest.mark.asyncio
    @patch("helpers.azure_credential_utils.Config")
    @patch("helpers.azure_credential_utils.AioDefaultAzureCredential")
    @patch("helpers.azure_credential_utils.AioManagedIdentityCredential")
    async def test_get_azure_credential_async_non_local_env(self, mock_aio_managed_identity_credential, mock_aio_default_azure_credential, mock_config):
        """Test get_azure_credential_async in non-local environment."""
        # Arrange
        mock_config_instance = MagicMock()
        mock_config_instance.app_env = "Prod"
        mock_config.return_value = mock_config_instance

        mock_aio_managed_credential = MagicMock()
        mock_aio_managed_identity_credential.return_value = mock_aio_managed_credential

        # Act
        credential = await azure_credential_utils.get_azure_credential_async(client_id="test-client-id")

        # Assert
        mock_config.assert_called_once()
        mock_aio_managed_identity_credential.assert_called_once_with(client_id="test-client-id")
        mock_aio_default_azure_credential.assert_not_called()
        assert credential == mock_aio_managed_credential