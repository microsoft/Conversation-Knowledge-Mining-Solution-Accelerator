import logging
import uuid
from typing import Optional
from fastapi import HTTPException, status
from azure.ai.projects.aio import AIProjectClient
from common.config.config import Config
from common.database.cosmosdb_service import CosmosConversationClient
from helpers.azure_credential_utils import get_azure_credential, get_azure_credential_async

from agent_framework.azure import AzureAIProjectAgentProvider

logger = logging.getLogger(__name__)


class HistoryService:
    def __init__(self):
        config = Config()

        self.use_chat_history_enabled = config.use_chat_history_enabled
        self.azure_cosmosdb_database = config.azure_cosmosdb_database
        self.azure_cosmosdb_account = config.azure_cosmosdb_account
        self.azure_cosmosdb_conversations_container = config.azure_cosmosdb_conversations_container
        self.azure_cosmosdb_enable_feedback = config.azure_cosmosdb_enable_feedback
        self.chat_history_enabled = (
            self.use_chat_history_enabled
            and self.azure_cosmosdb_account
            and self.azure_cosmosdb_database
            and self.azure_cosmosdb_conversations_container
        )

        self.azure_client_id = config.azure_client_id
        self.title_agent_name = config.title_agent_name

        # AI Project configuration for Foundry SDK
        self.ai_project_endpoint = config.ai_project_endpoint
        self.ai_project_api_version = config.ai_project_api_version
        self.solution_name = config.solution_name

    def init_cosmosdb_client(self):
        if not self.chat_history_enabled:
            logger.debug("CosmosDB is not enabled in configuration")
            return None

        try:
            cosmos_endpoint = f"https://{self.azure_cosmosdb_account}.documents.azure.com:443/"

            return CosmosConversationClient(
                cosmosdb_endpoint=cosmos_endpoint,
                credential=get_azure_credential(client_id=self.azure_client_id),
                database_name=self.azure_cosmosdb_database,
                container_name=self.azure_cosmosdb_conversations_container,
                enable_message_feedback=self.azure_cosmosdb_enable_feedback,
            )
        except Exception:
            logger.exception("Failed to initialize CosmosDB client")
            raise

    async def generate_title(self, conversation_messages):
        # Filter user messages and prepare content
        user_messages = [{"role": msg["role"], "content": msg["content"]}
                         for msg in conversation_messages if msg["role"] == "user"]

        # Combine all user messages with the title prompt
        combined_content = "\n".join([msg["content"] for msg in user_messages])
        final_prompt = f"Generate a title for:\n{combined_content}"

        logger.info(
            "Generating title using agent '%s' for %d user message(s)",
            self.title_agent_name, len(user_messages)
        )
        try:
            async with (
                await get_azure_credential_async(client_id=self.azure_client_id) as credential,
                AIProjectClient(endpoint=self.ai_project_endpoint, credential=credential) as project_client,
            ):
                # Create provider for agent management
                provider = AzureAIProjectAgentProvider(project_client=project_client)

                # Get title agent using provider
                agent = await provider.get_agent(name=self.title_agent_name)

                # Generate title using agent
                result = await agent.run(final_prompt)
                title = str(result.text).strip() if result is not None else "New Conversation"
                logger.info("Title generated successfully: '%s'", title)
                return title

        except Exception as e:
            logger.exception("Error generating title: %s", str(e))
            # Fallback to user message or default
            if user_messages:
                return user_messages[-1]["content"][:50]
            return "New Conversation"

    async def update_conversation(self, user_id: str, request_json: dict):
        conversation_id = request_json.get("conversation_id")
        messages = request_json.get("messages", [])
        if not conversation_id:
            raise ValueError("No conversation_id found")
        logger.info("update_conversation called: conversation_id=%s, message_count=%d",
                    conversation_id, len(messages))
        cosmos_conversation_client = self.init_cosmosdb_client()
        # Retrieve or create conversation
        conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)
        if not conversation:
            logger.info("Conversation %s not found, creating new conversation", conversation_id)
            title = await self.generate_title(messages)
            conversation = await cosmos_conversation_client.create_conversation(
                user_id=user_id, conversation_id=conversation_id, title=title
            )
            conversation_id = conversation["id"]
            logger.info("New conversation created: id=%s, title='%s'", conversation_id, title)
        else:
            logger.info("Existing conversation found: id=%s, title='%s'", conversation_id, conversation.get("title"))

        # Format the incoming message object in the "chat/completions" messages format then write it to the
        # conversation history in cosmos
        messages = request_json["messages"]
        if len(messages) > 0 and messages[0]["role"] == "user":
            user_message = next(
                (
                    message
                    for message in reversed(messages)
                    if message["role"] == "user"
                ),
                None,
            )
            logger.info("Writing user message to CosmosDB for conversation %s", conversation_id)
            createdMessageValue = await cosmos_conversation_client.create_message(
                uuid=str(uuid.uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=user_message,
            )
            if createdMessageValue == "Conversation not found":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Conversation not found")
            logger.info("User message written to CosmosDB for conversation %s", conversation_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User message not found")

        # Format the incoming message object in the "chat/completions" messages format
        # then write it to the conversation history in cosmos
        messages = request_json["messages"]
        if len(messages) > 0 and messages[-1]["role"] == "assistant":
            if len(messages) > 1 and messages[-2].get("role", None) == "tool":
                # write the tool message first
                logger.info("Writing tool message to CosmosDB for conversation %s", conversation_id)
                await cosmos_conversation_client.create_message(
                    uuid=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    input_message=messages[-2],
                )
            # write the assistant message
            logger.info("Writing assistant message to CosmosDB for conversation %s", conversation_id)
            await cosmos_conversation_client.create_message(
                uuid=messages[-1]["id"],
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
        else:
            await cosmos_conversation_client.cosmosdb_client.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No assistant message found")
        await cosmos_conversation_client.cosmosdb_client.close()
        logger.info("update_conversation completed: conversation_id=%s, title='%s'",
                    conversation["id"], conversation.get("title"))
        return {
            "id": conversation["id"],
            "title": conversation["title"],
            "updatedAt": conversation.get("updatedAt")}

    async def rename_conversation(self, user_id: str, conversation_id, title):
        if not conversation_id:
            raise ValueError("No conversation_id found")

        logger.info("rename_conversation called: conversation_id=%s, new_title='%s'",
                    conversation_id, title)
        cosmos_conversation_client = self.init_cosmosdb_client()
        conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Conversation {conversation_id} was not found. "
                    "It either does not exist or the logged-in user does not have access to it."
                )
            )

        conversation["title"] = title
        updated_conversation = await cosmos_conversation_client.upsert_conversation(
            conversation
        )
        logger.info("Conversation %s renamed successfully to '%s'", conversation_id, title)
        return updated_conversation

    async def update_message_feedback(
            self,
            user_id: str,
            message_id: str,
            message_feedback: str) -> Optional[dict]:
        try:
            logger.info(
                "Updating feedback for message_id: %s by user: %s", message_id, user_id)
            cosmos_conversation_client = self.init_cosmosdb_client()
            updated_message = await cosmos_conversation_client.update_message_feedback(
                user_id, message_id, message_feedback
            )

            if updated_message:
                logger.info(
                    "Successfully updated message_id: %s with feedback: %s", message_id, message_feedback)
                return updated_message
            else:
                logger.warning("Message ID %s not found or access denied", message_id)
                return None
        except Exception:
            logger.exception(
                "Error updating message feedback for message_id: %s", message_id)
            raise

    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Deletes a conversation and its messages from the database if the user has access.

        Args:
            user_id (str): The ID of the authenticated user.
            conversation_id (str): The ID of the conversation to delete.

        Returns:
            bool: True if the conversation was deleted successfully, False otherwise.
        """
        try:
            cosmos_conversation_client = self.init_cosmosdb_client()

            # Fetch conversation to ensure it exists and belongs to the user
            conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)

            if not conversation:
                logger.warning("Conversation %s not found for delete operation", conversation_id)
                return False

            if conversation["userId"] != user_id:
                logger.warning(
                    "User %s does not have permission to delete conversation %s", user_id, conversation_id)
                return False

            # Delete associated messages first (if applicable)
            await cosmos_conversation_client.delete_messages(conversation_id, user_id)

            # Delete the conversation itself
            await cosmos_conversation_client.delete_conversation(user_id, conversation_id)

            logger.info("Successfully deleted conversation %s", conversation_id)
            return True

        except Exception:
            logger.exception("Error deleting conversation %s", conversation_id)
            return False

    async def get_conversations(self, user_id: str, offset: int, limit: int):
        """
        Retrieves a list of conversations for a given user.

        Args:
            user_id (str): The ID of the authenticated user.

        Returns:
            list: A list of conversation objects or an empty list if none exist.
        """
        try:
            logger.info("get_conversations called: offset=%d, limit=%d", offset, limit)
            cosmos_conversation_client = self.init_cosmosdb_client()
            if not cosmos_conversation_client:
                raise ValueError("CosmosDB is not configured or unavailable")

            conversations = await cosmos_conversation_client.get_conversations(user_id, offset=offset, limit=limit)
            count = len(conversations) if conversations else 0
            logger.info("Retrieved %d conversation(s)", count)
            return conversations or []
        except Exception:
            logger.exception("Error retrieving conversations")
            return []

    async def get_messages(self, user_id: str, conversation_id: str):
        """
        Retrieves all messages for a given conversation ID if the user has access.

        Args:
            user_id (str): The ID of the authenticated user.
            conversation_id (str): The ID of the conversation.

        Returns:
            list: A list of messages in the conversation.
        """
        try:
            logger.info("get_messages called: conversation_id=%s", conversation_id)
            cosmos_conversation_client = self.init_cosmosdb_client()
            if not cosmos_conversation_client:
                raise ValueError("CosmosDB is not configured or unavailable")

            # Fetch conversation to ensure it exists and belongs to the user
            conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)
            if not conversation:
                logger.warning("Conversation %s not found for get_messages operation", conversation_id)
                return []

            # Fetch messages associated with the conversation
            messages = await cosmos_conversation_client.get_messages(conversation_id)
            logger.info(
                "Retrieved %d message(s) for conversation %s",
                len(messages) if messages else 0, conversation_id
            )
            return messages

        except Exception:
            logger.exception(
                "Error retrieving messages for conversation %s", conversation_id)
            return []

    async def get_conversation_messages(self, user_id: str, conversation_id: str):
        """
        Retrieves a single conversation and its messages for a given user.

        Args:
            user_id (str): The ID of the authenticated user.
            conversation_id (str): The ID of the conversation to retrieve.

        Returns:
            dict: The conversation object with messages or None if not found.
        """
        try:
            cosmos_conversation_client = self.init_cosmosdb_client()
            if not cosmos_conversation_client:
                raise ValueError("CosmosDB is not configured or unavailable")

            logger.info("get_conversation_messages called: conversation_id=%s", conversation_id)
            # Fetch the conversation details
            conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)
            if not conversation:
                logger.warning(
                    "Conversation %s not found for user %s", conversation_id, user_id)
                return None

            # Get messages related to the conversation
            conversation_messages = await cosmos_conversation_client.get_messages(user_id, conversation_id)

            # Format messages for the frontend
            messages = [
                {
                    "id": msg["id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "createdAt": msg["createdAt"],
                    "feedback": msg.get("feedback"),
                }
                for msg in conversation_messages
            ]
            logger.info("Returning %d message(s) for conversation %s", len(messages), conversation_id)
            return messages
        except Exception:
            logger.exception(
                "Error retrieving conversation %s for user %s", conversation_id, user_id)
            return None

    async def clear_messages(self, user_id: str, conversation_id: str) -> bool:
        """
        Clears all messages in a conversation while keeping the conversation itself.

        Args:
            user_id (str): The ID of the authenticated user.
            conversation_id (str): The ID of the conversation.

        Returns:
            bool: True if messages were cleared successfully, False otherwise.
        """
        try:
            cosmos_conversation_client = self.init_cosmosdb_client()
            if not cosmos_conversation_client:
                raise ValueError("CosmosDB is not configured or unavailable")

            # Ensure the conversation exists and belongs to the user
            conversation = await cosmos_conversation_client.get_conversation(conversation_id)
            if not conversation:
                logger.warning("Conversation %s not found for clear messages operation", conversation_id)
                return False

            if conversation["user_id"] != user_id:
                logger.warning(
                    "User %s does not have permission to clear messages in conversation %s", user_id, conversation_id)
                return False

            # Delete all messages associated with the conversation
            await cosmos_conversation_client.delete_messages(conversation_id, user_id)

            logger.info(
                "Successfully cleared messages in conversation %s for user %s", conversation_id, user_id)
            return True

        except Exception:
            logger.exception(
                "Error clearing messages for conversation %s", conversation_id)
            return False

    async def ensure_cosmos(self):
        """
        Retrieves a list of conversations for a given user.

        Args:
            user_id (str): The ID of the authenticated user.

        Returns:
            list: A list of conversation objects or an empty list if none exist.
        """
        try:
            logger.info("ensure_cosmos called: verifying CosmosDB connectivity")
            cosmos_conversation_client = self.init_cosmosdb_client()
            success, err = await cosmos_conversation_client.ensure()
            if success:
                logger.info("CosmosDB connectivity check passed")
            else:
                logger.warning("CosmosDB connectivity check failed: %s", err)
            return success, err
        except Exception as e:
            logger.exception("Error ensuring CosmosDB configuration")
            return False, str(e)
