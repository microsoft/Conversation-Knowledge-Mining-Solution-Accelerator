from base.base import BasePage
from playwright.sync_api import expect

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
        # self.page.wait_for_timeout(5000)
        # send_btn = self.page.locator("//button[@title='Send Question']")

        new_conv_btn = self.page.locator("//button[@title='Create new Conversation']")
        
        if new_conv_btn.is_enabled():
        # Type a question in the text area
            self.page.locator(self.TYPE_QUESTION_TEXT_AREA).fill(text)
            self.page.wait_for_timeout(5000)

    def click_send_button(self):
        # Click on send button in question area
        self.page.locator(self.SEND_BUTTON).click()
        self.page.wait_for_timeout(10000)
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