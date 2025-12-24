"""
HomePage Module
Contains page object methods for interacting with the KM Generic home page
"""
import logging
from playwright.sync_api import expect
from base.base import BasePage

logger = logging.getLogger(__name__)


class HomePage(BasePage):
    """Page object for the KM Generic Home Page"""
    TYPE_QUESTION_TEXT_AREA = "//textarea[@placeholder='Ask a question...']"
    SEND_BUTTON = "//button[@title='Send Question']"
    SHOW_CHAT_HISTORY_BUTTON = "//button[normalize-space()='Show Chat History']"
    HIDE_CHAT_HISTORY_BUTTON = "//button[normalize-space()='Hide Chat History']"
    CHAT_HISTORY_NAME = "//div[contains(@class, 'ChatHistoryListItemCell_chatTitle')]"
    CLEAR_CHAT_HISTORY_MENU = "//button[@id='moreButton']"
    CLEAR_CHAT_HISTORY = "//button[@role='menuitem']"
    REFERENCE_LINKS_IN_RESPONSE = "//span[@role='button' and contains(@class, 'citationContainer')]"
    CLOSE_BUTTON = "svg[role='button'][tabindex='0']"
    CLEAR_ALL_CHAT = "//span[contains(text(),'Clear All')]"
    GENERATING_ANSWER = "//span[contains(.,'Generating answer')]"
    TYPING_INDICATOR = "//div[@class='typing-indicator']"

    def __init__(self, page):
        """Initialize HomePage with page instance"""
        super().__init__(page)
        self.page = page

    def home_page_load(self):
        """Wait for home page to load by checking for Satisfied element"""
        self.page.locator("//span[normalize-space()='Satisfied']").wait_for(state="visible")

    def enter_chat_question(self, text):
        """Enter a question in the chat text area"""
        self.page.locator(self.TYPE_QUESTION_TEXT_AREA).fill(text)
        self.page.wait_for_timeout(4000)

    def click_send_button(self):
        """Click on send button and wait for response generation to complete"""
        # Click on send button in question area
        self.page.locator(self.SEND_BUTTON).click()

        # Wait for "Generating answer" to appear (response started)
        try:
            self.page.locator(self.GENERATING_ANSWER).wait_for(state="visible", timeout=10000)
            logger.info("Response generation started - 'Generating answer' appeared")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("'Generating answer' text did not appear: %s", str(exc))

        # Wait for typing indicator to appear (AI is typing)
        try:
            self.page.locator(self.TYPING_INDICATOR).wait_for(state="visible", timeout=10000)
            logger.info("Typing indicator appeared - AI is generating response")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Typing indicator did not appear: %s", str(exc))

        # Wait for typing indicator to disappear (typing completed)
        try:
            self.page.locator(self.TYPING_INDICATOR).wait_for(state="hidden", timeout=120000)
            logger.info("Typing indicator hidden - AI finished typing")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Typing indicator did not disappear within timeout: %s", str(exc))

        # Wait for "Generating answer" to disappear (response completed)
        try:
            self.page.locator(self.GENERATING_ANSWER).wait_for(state="hidden", timeout=120000)
            logger.info("Response generation completed - 'Generating answer' hidden")
        except Exception as exc:
            logger.error("'Generating answer' did not disappear within timeout: %s", str(exc))
            raise AssertionError(
                "Response generation timed out - 'Generating answer' still visible"
            ) from exc

        # Additional wait for network and UI to settle
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)

    def show_chat_history(self):
        """Show chat history and verify it's visible"""
        self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON).click()
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)
        try:
            expect(self.page.locator(self.CHAT_HISTORY_NAME)).to_be_visible(timeout=9000)
        except AssertionError as exc:
            raise AssertionError(
                "Chat history name was not visible on the page within the expected time."
            ) from exc

    def delete_chat_history(self):
        """Delete chat history if it exists"""
        self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON).click()
        chat_history = self.page.locator("//span[contains(text(),'No chat history.')]")
        if chat_history.is_visible():
            self.page.wait_for_load_state('networkidle')
            self.page.wait_for_timeout(2000)
            self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON).click()
        else:
            self.page.locator(self.CLEAR_CHAT_HISTORY_MENU).click()
            self.page.locator(self.CLEAR_CHAT_HISTORY).click()
            self.page.locator(self.CLEAR_ALL_CHAT).click()
            self.page.wait_for_timeout(10000)
            self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON).click()
            self.page.wait_for_load_state('networkidle')
            self.page.wait_for_timeout(2000)

    def close_chat_history(self):
        """Close the chat history panel"""
        self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON).click()
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)

    def click_reference_link_in_response(self):
        """Click on the reference/citation link in the response"""
        # Click on reference link response
        BasePage.scroll_into_view(self, self.page.locator(self.REFERENCE_LINKS_IN_RESPONSE))
        self.page.wait_for_timeout(2000)
        reference_links = self.page.locator(self.REFERENCE_LINKS_IN_RESPONSE)
        reference_links.nth(reference_links.count() - 1).click()
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)

    def close_citation(self):
        """Close the citation/reference panel"""
        self.page.wait_for_timeout(3000)

        close_btn = self.page.locator(self.CLOSE_BUTTON)
        close_btn.wait_for(state="attached", timeout=5000)
        # bring it into view just in case
        close_btn.scroll_into_view_if_needed()
        # force the click, bypassing the aria-hidden check
        close_btn.click(force=True)
        self.page.wait_for_timeout(5000)

    def has_reference_link(self):
        """Check if the last response has a reference/citation link"""
        # Get all assistant messages
        assistant_messages = self.page.locator("div.chat-message.assistant")
        last_assistant = assistant_messages.nth(assistant_messages.count() - 1)

        # Use XPath properly by prefixing with 'xpath='
        reference_links = last_assistant.locator(
            "xpath=.//span[@role='button' and contains(@class, 'citationContainer')]"
        )
        return reference_links.count() > 0

    def validate_response_text(self, question):
        """Validate that the response text is valid and not an error message"""
        logger.info("🔍 DEBUG: validate_response_text called for question: '%s'", question)
        try:
            response_text = self.page.locator("//p")
            response_count = response_text.count()
            logger.info("🔍 DEBUG: Found %d <p> elements on page", response_count)

            if response_count == 0:
                logger.info("⚠️ DEBUG: No <p> elements found on page")
                raise AssertionError(f"No response text found for question: {question}")

            last_response = response_text.nth(response_count - 1).text_content()
            logger.info("🔍 DEBUG: Last response text: '%s'", last_response)

            # Check for invalid responses
            invalid_response_1 = (
                "I cannot answer this question from the data available. "
                "Please rephrase or add more details."
            )
            invalid_response_2 = "Chart cannot be generated."
            invalid_response_3 = "An error occurred while processing the request."

            # Use regular assertions instead of pytest-check to trigger retry logic
            if invalid_response_1 in last_response:
                logger.info("❌ DEBUG: Found invalid response 1: '%s'", invalid_response_1)
                raise AssertionError(
                    f"Invalid response for question '{question}': {invalid_response_1}"
                )

            if invalid_response_2 in last_response:
                logger.info("❌ DEBUG: Found invalid response 2: '%s'", invalid_response_2)
                raise AssertionError(
                    f"Invalid response for question '{question}': {invalid_response_2}"
                )

            if invalid_response_3 in last_response:
                logger.info("❌ DEBUG: Found invalid response 3: '%s'", invalid_response_3)
                raise AssertionError(
                    f"Invalid response for question '{question}': {invalid_response_3}"
                )

            logger.info(
                "✅ DEBUG: Response validation completed successfully for question: '%s'",
                question
            )

        except Exception as exc:
            logger.info("❌ DEBUG: Exception in validate_response_text: %s", str(exc))
            raise exc
