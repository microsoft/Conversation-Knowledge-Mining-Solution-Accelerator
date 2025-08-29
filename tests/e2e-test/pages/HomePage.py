from base.base import BasePage
from playwright.sync_api import expect
import logging
from pytest_check import check

logger = logging.getLogger(__name__)

class HomePage(BasePage):
    TYPE_QUESTION_TEXT_AREA = "//textarea[@placeholder='Ask a question...']"
    SEND_BUTTON = "//button[@title='Send Question']"
    SHOW_CHAT_HISTORY_BUTTON = "//button[normalize-space()='Show Chat History']"
    HIDE_CHAT_HISTORY_BUTTON = "//button[normalize-space()='Hide Chat History']"
    CHAT_HISTORY_NAME = "//div[contains(@class, 'ChatHistoryListItemCell_chatTitle')]"
    CLEAR_CHAT_HISTORY_MENU = "//button[@id='moreButton']"
    CLEAR_CHAT_HISTORY = "//button[@role='menuitem']"
    REFERENCE_LINKS_IN_RESPONSE = "//span[@role='button' and contains(@class, 'citationContainer')]"
    CLOSE_BUTTON = "svg[role='button'][tabindex='0']"



    def __init__(self, page):
        self.page = page

    def home_page_load(self):
        self.page.locator("//span[normalize-space()='Satisfied']").wait_for(state="visible")

    def enter_chat_question(self,text):
        # self.page.locator(self.TYPE_QUESTION_TEXT_AREA).fill(text)
        # send_btn = self.page.locator("//button[@title='Send Question']")

        new_conv_btn = self.page.locator("//button[@title='Create new Conversation']")

        if not new_conv_btn.is_enabled():
            self.page.wait_for_timeout(16000)

        if new_conv_btn.is_enabled():
        # Type a question in the text area
            self.page.locator(self.TYPE_QUESTION_TEXT_AREA).fill(text)
            self.page.wait_for_timeout(5000)

    def click_send_button(self):
        # Click on send button in question area
        self.page.locator(self.SEND_BUTTON).click()
        self.page.wait_for_timeout(12000)
        self.page.wait_for_load_state('networkidle')

    
    def show_chat_history(self):
        self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON).click()
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)
        try:
            expect(self.page.locator(self.CHAT_HISTORY_NAME)).to_be_visible(timeout=9000)
        except AssertionError:
            raise AssertionError("Chat history name was not visible on the page within the expected time.")

    def delete_chat_history(self):
        self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON).click()
        chat_history = self.page.locator("//span[contains(text(),'No chat history.')]")
        if chat_history.is_visible():
            self.page.wait_for_load_state('networkidle')
            self.page.wait_for_timeout(2000)
            self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON).click()


        else:
            self.page.locator(self.CLEAR_CHAT_HISTORY_MENU).click()
            self.page.locator(self.CLEAR_CHAT_HISTORY).click()
            self.page.get_by_role("button", name="Clear All").click()
            self.page.wait_for_timeout(10000)
            self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON).click()
            self.page.wait_for_load_state('networkidle')
            self.page.wait_for_timeout(2000)

    def close_chat_history(self):
        self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON).click()
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)
    
    def click_reference_link_in_response(self):
        # Click on reference link response
        BasePage.scroll_into_view(self, self.page.locator(self.REFERENCE_LINKS_IN_RESPONSE))
        self.page.wait_for_timeout(2000)
        reference_links = self.page.locator(self.REFERENCE_LINKS_IN_RESPONSE)
        reference_links.nth(reference_links.count() - 1).click()
        # self.page.locator(self.REFERENCE_LINKS_IN_RESPONSE).click()
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)
 
 
    def close_citation(self):
        self.page.wait_for_timeout(3000)
        
        close_btn = self.page.locator(self.CLOSE_BUTTON)
        close_btn.wait_for(state="attached", timeout=5000)
        # bring it into view just in case
        close_btn.scroll_into_view_if_needed()
        # force the click, bypassing the aria-hidden check
        close_btn.click(force=True)
        self.page.wait_for_timeout(5000)

    def has_reference_link(self):
        # Get all assistant messages
        assistant_messages = self.page.locator("div.chat-message.assistant")
        last_assistant = assistant_messages.nth(assistant_messages.count() - 1)

        # Use XPath properly by prefixing with 'xpath='
        reference_links = last_assistant.locator("xpath=.//span[@role='button' and contains(@class, 'citationContainer')]")
        return reference_links.count() > 0

    def validate_chat_response(self, question: str, expect_chart: bool = False):
        logger.info(f"💬 Sending question: {question}")
        self.enter_chat_question(question)

        # Wait for send button to be enabled and click it
        self.click_send_button()

        # Backend validation
        self.validate_response_status(question)

        # Wait for assistant message
        assistant_response = self.page.locator("div.chat-message.assistant").last
        expect(assistant_response).to_be_visible(timeout=10000)

        # If not expecting chart, validate the text response
        if not expect_chart:
            try:
                p_tag = assistant_response.locator("p")
                expect(p_tag).to_be_visible(timeout=5000)
                response_text = p_tag.inner_text().strip().lower()
                logger.info(f"📥 Assistant response: {response_text}")

                with check:
                    assert "i cannot answer this question" not in response_text, \
                        f"❌ Fallback response for: {question}"
                    assert "chart cannot be generated" not in response_text, \
                        f"❌ Chart failure response for: {question}"
            except Exception as e:
                logger.warning(f"⚠️ No <p> tag found in assistant response for: {question} — skipping text validation. Error: {str(e)}")

        # Validate chart if expected
        if expect_chart:
            logger.info("📊 Validating chart presence...")
            chart_canvas = assistant_response.locator("canvas")
            expect(chart_canvas).to_be_visible(timeout=10000)
            logger.info("✅ Chart canvas found in assistant response.")

        # Optional citation check
        if self.has_reference_link():
            logger.info("🔗 Reference link found. Opening and closing citation.")
            self.click_reference_link_in_response()
            self.close_citation()

    def delete_first_chat_thread(self):

        # self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON).click()
        # self.page.wait_for_load_state('networkidle')
        # self.page.wait_for_timeout(2000)

        # Step 2: Locate the 0th chat history item
        first_thread = self.page.locator("div[data-list-index='0']")

        # Step 3: Locate and click the delete button inside the 0th item
        delete_button = first_thread.locator("button[title='Delete']")
        delete_button.click()

        # Step 4: Confirm deletion (if a confirmation modal appears)
        try:
            confirm_button = self.page.locator("button:has-text('Delete')")  # or 'Yes' based on actual text
            if confirm_button.is_visible():
                confirm_button.click()
        except:
            pass  # No confirmation modal present

        self.page.wait_for_timeout(1000)  # Optional: wait for UI update

    def edit_chat_title(self, new_title: str, index: int = 0):
        # Step 1: Open chat history panel
        self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON).click()
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)

        # Step 2: Locate the chat item by index (use nth(0) to avoid strict mode issues)
        chat_item = self.page.locator(f"div[data-list-index='{index}']").nth(0)
        expect(chat_item).to_be_visible(timeout=5000)

        # Step 3: Click the Edit button inside the chat item
        edit_button = chat_item.locator("button[title='Edit']")
        expect(edit_button).to_be_visible(timeout=3000)
        edit_button.click()

        # Step 4: Fill the new title
        title_input = chat_item.locator("input[type='text']")
        expect(title_input).to_be_visible(timeout=3000)
        title_input.fill(new_title)

        save_button = self.page.locator('button[aria-label="confirm new title"]')
        try:
            expect(save_button).to_be_visible(timeout=3000)
            save_button.click()
        except AssertionError:
            self.page.screenshot(path="save_button_not_found.png", full_page=True)
            raise AssertionError("❌ 'Save' icon button not found or not visible. Screenshot saved to 'save_button_not_found.png'.")



        # Optional wait for UI to reflect the update
        self.page.wait_for_timeout(1000)

        # Step 6: Verify the updated title
        updated_chat_item = self.page.locator(f"div[data-list-index='{index}']").first
        updated_title_locator = updated_chat_item.locator(".ChatHistoryListItemCell_chatTitle__areVC")

        try:
            expect(updated_title_locator).to_be_visible(timeout=3000)
            updated_title = updated_title_locator.text_content(timeout=3000).strip()
        except:
            self.page.screenshot(path="updated_title_not_found.png", full_page=True)
            raise AssertionError("❌ Updated title element not found or not visible. Screenshot saved.")

        assert new_title.lower() in updated_title.lower(), \
            f"❌ Chat title not updated. Expected: {new_title}, Found: {updated_title}"

        logger.info(f"✅ Chat title successfully updated to: {updated_title}")

    def create_new_chat(self):
    # Click the "Create new Conversation" (+) button
        create_button = self.page.locator("button[title='Create new Conversation']")
        expect(create_button).to_be_visible()
        create_button.click()

        # Optional: Wait and check if new chat panel is cleared
        textarea = self.page.locator("textarea[placeholder='Ask a question...']")
        expect(textarea).to_have_value("", timeout=3000)

        logger.info("✅ New chat conversation started successfully.")
    
    # def verify_chat_response_generation(self):
    #     self.page.reload(wait_until="networkidle")
    #     logger.info("Step 1: On chat window enter the prompt which provides chat info: EX:  Average handling time by topic")
    #     self.enter_chat_question("Average handling time by topic")
    #     self.click_send_button()

    #     # Wait and verify some assistant response appears
    #     self.page.wait_for_timeout(2000)

    #     assistant_messages = self.page.locator("div.chat-message.assistant")
    #     last_message = assistant_messages.last

    #     # Validate greeting response
    #     p = last_message.locator("p")
    #     message_text = p.inner_text().lower()

    #     # Wait and verify some assistant response appears
    #     response = self.page.locator("div.chat-message.assistant")
    #     expect(response).to_be_visible(timeout=10000)
    #     print("✅ Response received for 'Average handling time by topic'")

    #     logger.info("Step 2: On chat window enter the prompt which provides chat info: EX:  Generate chart")
    #     self.enter_chat_question("Generate chart")
    #     self.click_send_button()

    #     # Check that a chart is present in response
    #     chart_svg = self.page.locator("div.chat-message.assistant svg")
    #     expect(chart_svg).to_be_visible(timeout=10000)
    #     print("✅ Chart is generated in response to 'Generate chart'")