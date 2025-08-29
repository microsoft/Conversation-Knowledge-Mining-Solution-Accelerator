from playwright.sync_api import expect
from base.base import BasePage
from config.constants import URL
import logging

logger = logging.getLogger(__name__)

class KMGenericPage(BasePage):
    def __init__(self, page):
        self.page = page

    def open_url(self):
        self.page.goto(URL, wait_until="domcontentloaded")
        # Wait for the login form to appear
        self.page.wait_for_timeout(60000)
        self.page.wait_for_load_state("networkidle")
    
    def validate_dashboard_ui(self):
        expect(self.page.locator("text=Satisfied")).to_be_visible()
        expect(self.page.locator("text=Total Calls")).to_be_visible()
        expect(self.page.locator("#AVG_HANDLING_TIME >> text=Average Handling Time")).to_be_visible()
        expect(self.page.locator("text=Topics Overview")).to_be_visible()
        expect(self.page.locator("text=Average Handling Time By Topic")).to_be_visible()
        expect(self.page.locator("text=Trending Topics")).to_be_visible()
        expect(self.page.locator("text=Key Phrases")).to_be_visible()
        expect(self.page.locator("text=Start Chatting")).to_be_visible()
        
    def validate_user_filter_visible(self):
        expect(self.page.locator("text=Year to Date")).to_be_visible()
        expect(self.page.locator("button.ms-Button:has-text('all')")).to_be_visible()
        expect(self.page.locator("button.ms-Button:has-text('Topics')")).to_be_visible()

    def update_filters(self):
        filter_buttons = self.page.locator(".filters-container button.ms-Button--hasMenu")
        count = filter_buttons.count()
        print(f"Found {count} filter buttons")

        for i in range(count):
            print(f"Clicking filter button {i}")
            filter_buttons.nth(i).click()

            try:
                # Wait for the menu to appear
                menu = self.page.locator("div[role='menu']")
                menu.wait_for(state="visible", timeout=5000)

                # Locate all menu item buttons inside this menu
                menu_items = menu.locator("ul[role='presentation'] > li > button[role='menuitemcheckbox']")
                options_count = menu_items.count()
                print(f"Found {options_count} menu items for filter {i}")

                if options_count > 0:
                    # Click the first menu item (index 0)
                    print(f"Selecting first option for filter {i}: '{menu_items.nth(1).inner_text()}'")
                    menu_items.nth(1).click()
                else:
                    print(f"No menu items found for filter {i} to select")

            except Exception as e:
                print(f"❌ Failed to interact with filter {i}: {e}")

            self.page.wait_for_timeout(1000)  # Wait to let UI stabilize

        self.page.wait_for_timeout(2000)  # Wait after all filters updated


        # Wait after all filters updated
        self.page.wait_for_timeout(2000)

    def click_apply_button(self):
        apply_button = self.page.locator("button:has-text('Apply')")
        expect(apply_button).to_be_enabled()
        apply_button.click()

    def verify_blur_and_chart_update(self):
        self.page.wait_for_timeout(2000)  # Wait for blur effect
        expect(self.page.locator("text=Topics Overview")).to_be_visible()

    def validate_filter_data(self):
        print("📊 Verifying if chart or data updated after filter change.")
        
        # Check Key Phrases section is visible and contains expected phrase
        expect(self.page.locator("#KEY_PHRASES span.chart-title:has-text('Key Phrases')")).to_be_visible()
        
        phrase_locator = self.page.locator("#wordcloud svg text", has_text="change plan")
        expect(phrase_locator).to_be_visible(timeout=5000)

        print("✅ Key phrase 'change plan' is visible.")

        # Verify sentiment is 'positive' in the table
        sentiment_locator = self.page.locator(
            "table.fui-Table tbody tr td:has-text('positive')"
        )
        expect(sentiment_locator).to_be_visible(timeout=5000)
        
        print("✅ Sentiment is 'positive' as expected.")
    
    def verify_hide_dashboard_and_chat_buttons(self):
        self.page.wait_for_timeout(2000) 
        header_right = self.page.locator("div.header-right-section")
        hide_dashboard_btn = header_right.get_by_role("button", name="Hide Dashboard")
        hide_chat_btn = header_right.get_by_role("button", name="Hide Chat")

        assert hide_dashboard_btn.is_visible(), "Hide Dashboard button is not visible"
        assert hide_chat_btn.is_visible(), "Hide Chat button is not visible"
        print("✅ Hide Dashboard and Hide Chat buttons are present")

        # Click Hide Dashboard and verify dashboard collapses/hides
        logger.info("Step 3: Try clicking on Hide dashboard button")
        hide_dashboard_btn.click()
        dashboard = self.page.locator("#dashboard")
        assert not dashboard.is_visible(), "Dashboard did not collapse/hide after clicking Hide Dashboard"
        print("✅ Dashboard collapsed/hid on clicking Hide Dashboard")

        # Click Hide Chat and verify chat section collapses/hides
        logger.info("Step 4: Try clicking on Hide chat button")
        hide_chat_btn.click()
        chat_section = self.page.locator("#chat-section")
        assert not chat_section.is_visible(), "Chat section did not collapse/hide after clicking Hide Chat"
        print("✅ Chat section collapsed/hid on clicking Hide Chat")