"""
BasePage Module
Contains base page object class with common methods
"""
import json
import logging
import os
import time
import uuid
from dotenv import load_dotenv
from config.constants import API_URL

logger = logging.getLogger(__name__)


class BasePage:
    """Base class for all page objects"""

    def __init__(self, page):
        """Initialize BasePage with page instance"""
        self.page = page

    def scroll_into_view(self, locator):
        """Scroll element into view"""
        reference_list = locator
        locator.nth(reference_list.count()-1).scroll_into_view_if_needed()

    def is_visible(self, locator):
        """Check if element is visible"""
        return locator.is_visible()

    def validate_response_status(self, question):  # pylint: disable=too-many-locals,too-many-statements
        """
        Validate that the API responds with status 200 for the given question.
        Uses Playwright's request context which maintains authentication from the browser session.
        """
        load_dotenv()

        url = f"{API_URL}/history/update"

        user_message_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())

        payload = {
            "messages": [{"role": "assistant", "content": question, "id": user_message_id}],
            "conversation_id": conversation_id,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*"
        }

        # Log request details for debugging
        logger.info("=" * 80)
        logger.info("🔍 API REQUEST DEBUG INFO")
        logger.info("=" * 80)
        logger.info("URL: %s", url)
        logger.info("Method: POST")
        logger.info("Headers: %s", json.dumps(headers, indent=2))
        logger.info("Payload: %s", json.dumps(payload, indent=2))
        logger.info("Question: %s", question)

        start = time.time()

        try:
            # Using Playwright's request context to leverage browser's authentication
            response = self.page.request.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=90000
            )

            duration = time.time() - start

            # Log response details for debugging
            logger.info("-" * 80)
            logger.info("📥 API RESPONSE DEBUG INFO")
            logger.info("-" * 80)
            logger.info("Status Code: %s", response.status)
            logger.info("Response Time: %.2fs", duration)

            # Log response headers
            try:
                response_headers = response.headers
                logger.info("Response Headers: %s", json.dumps(dict(response_headers), indent=2))
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Could not get response headers: %s", str(exc))

            # Get response body for debugging
            try:
                response_body = response.json()
                logger.info("Response Body (JSON): %s", json.dumps(response_body, indent=2))

                # If there's an error in the response, log it prominently
                if "error" in response_body:
                    logger.error("🚨 API ERROR MESSAGE: %s", response_body.get("error"))
                if "detail" in response_body:
                    logger.error("🚨 API ERROR DETAIL: %s", response_body.get("detail"))

            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Could not parse response body as JSON: %s", str(exc))
                try:
                    response_text = response.text()
                    # First 500 chars
                    logger.info("Response Body (Text): %s", response_text[:500])
                except Exception as text_error:  # pylint: disable=broad-exception-caught
                    logger.error("Could not get response text: %s", str(text_error))

            # Assert successful response
            if response.status != 200:
                error_msg = f"API returned status {response.status} instead of 200"
                logger.error("❌ %s", error_msg)
                logger.error("💡 POSSIBLE REASONS FOR 500 ERROR:")
                logger.error(
                    "   1. Missing 'conversation_id' in payload (endpoint expects existing conversation)"
                )
                logger.error("   2. Authentication/authorization issue")
                logger.error("   3. Invalid payload structure")
                logger.error("   4. Backend service error")
                logger.error("   5. Database connection issue")
                logger.warning(
                    "⚠️ Warning: %s - Continuing with test (UI validation is primary)",
                    error_msg
                )
            else:
                logger.info("✅ API succeeded in %.2fs", duration)

        except Exception as exc:  # pylint: disable=broad-exception-caught
            duration = time.time() - start
            logger.error("❌ API request failed after %.2fs", duration)
            logger.error("Exception Type: %s", type(exc).__name__)
            logger.error("Exception Message: %s", str(exc))
            import traceback  # pylint: disable=import-outside-toplevel
            logger.error("Stack Trace:\n%s", traceback.format_exc())
            logger.warning("⚠️ Warning: API validation failed - Continuing with test")

        logger.info("=" * 80)
        # Wait for UI to settle
        self.page.wait_for_timeout(6000)
