"""Azure Queue Storage service for reliable document processing."""

import json
import logging
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.storage.queue import QueueClient, QueueServiceClient

from src.api.config import get_settings

logger = logging.getLogger(__name__)

# Two-stage pipeline queues
EXTRACTION_QUEUE = "document-extraction"
ENRICHMENT_QUEUE = "document-enrichment"


class QueueService:
    """Manages Azure Queue Storage for async document processing with named queues."""

    def __init__(self):
        self._clients: dict[str, QueueClient] = {}
        self._credential = None
        self._available: Optional[bool] = None

    def _get_credential(self):
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        return self._credential

    def _get_client(self, queue_name: str) -> QueueClient:
        if queue_name not in self._clients:
            settings = get_settings()
            account_url = f"https://{settings.azure_storage_account}.queue.core.windows.net"
            client = QueueClient(
                account_url=account_url,
                queue_name=queue_name,
                credential=self._get_credential(),
            )
            try:
                client.create_queue()
            except Exception:
                pass  # Already exists
            self._clients[queue_name] = client
        return self._clients[queue_name]

    @property
    def available(self) -> bool:
        """Check if queue storage is configured and reachable."""
        if self._available is not None:
            return self._available
        settings = get_settings()
        if not settings.azure_storage_account:
            self._available = False
            return False
        try:
            self._get_client(EXTRACTION_QUEUE)
            self._get_client(ENRICHMENT_QUEUE)
            self._available = True
        except Exception as e:
            logger.warning(f"Queue storage not available: {e}")
            self._available = False
        return self._available

    def enqueue(self, queue_name: str, message: dict, visibility_timeout: int = 0) -> bool:
        """Add a processing message to the specified queue."""
        try:
            client = self._get_client(queue_name)
            client.send_message(
                json.dumps(message),
                visibility_timeout=visibility_timeout,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue to {queue_name}: {e}")
            return False

    def receive(self, queue_name: str, max_messages: int = 1, visibility_timeout: int = 300):
        """Receive messages from the specified queue."""
        try:
            client = self._get_client(queue_name)
            return client.receive_messages(
                max_messages=max_messages,
                visibility_timeout=visibility_timeout,
            )
        except Exception as e:
            logger.error(f"Failed to receive from {queue_name}: {e}")
            return []

    def delete(self, queue_name: str, message) -> bool:
        """Delete a message after successful processing."""
        try:
            client = self._get_client(queue_name)
            client.delete_message(message)
            return True
        except Exception as e:
            logger.error(f"Failed to delete from {queue_name}: {e}")
            return False


queue_service = QueueService()
