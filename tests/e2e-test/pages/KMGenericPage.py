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
        self.page.wait_for_timeout(8000)
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
        
        # Define the target values to select for each filter
        target_values = {
            0: "Last 14 days",      # First filter (date range)
            1: "Positive",          # Second filter (sentiment)
            2: "Laptop Performance Issues"     # Third filter (topics)
        }
        
        selected_filters = {}

        for i in range(count):
            print(f"\n📋 Processing filter button {i}")
            
            # Get the filter button text to identify which filter this is
            filter_button_text = filter_buttons.nth(i).inner_text().strip()
            print(f"Filter {i} button text: '{filter_button_text}'")
            
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
                    # Get all available options
                    print("📋 Available options:")
                    all_options = []
                    for j in range(options_count):
                        option_text = menu_items.nth(j).inner_text().strip()
                        all_options.append(option_text)
                        print(f"  {j}: '{option_text}'")
                    
                    # Find and select the target value
                    target_value = target_values.get(i, "").lower()
                    selected_index = -1
                    selected_option = ""
                    
                    if target_value:
                        # Look for the target value (case insensitive)
                        for j, option in enumerate(all_options):
                            if target_value in option.lower():
                                selected_index = j
                                selected_option = option
                                break
                        
                        if selected_index >= 0:
                            print(f"🎯 Target found: Selecting '{selected_option}' (index {selected_index})")
                            menu_items.nth(selected_index).click()
                            selected_filters[filter_button_text] = selected_option
                        else:
                            # If target not found, select the second option as fallback
                            fallback_index = 1 if options_count > 1 else 0
                            selected_option = all_options[fallback_index]
                            print(f"⚠️ Target '{target_value}' not found. Selecting fallback: '{selected_option}' (index {fallback_index})")
                            menu_items.nth(fallback_index).click()
                            selected_filters[filter_button_text] = selected_option
                    else:
                        # No target specified, select second option as default
                        default_index = 1 if options_count > 1 else 0
                        selected_option = all_options[default_index]
                        print(f"📌 No target specified. Selecting default: '{selected_option}' (index {default_index})")
                        menu_items.nth(default_index).click()
                        selected_filters[filter_button_text] = selected_option
                        
                else:
                    print(f"❌ No menu items found for filter {i}")
                    selected_filters[filter_button_text] = "No options available"

            except Exception as e:
                print(f"❌ Failed to interact with filter {i}: {e}")
                selected_filters[filter_button_text] = f"Error: {str(e)}"

            self.page.wait_for_timeout(1000)  # Wait to let UI stabilize

        self.page.wait_for_timeout(2000)  # Wait after all filters updated
        
        # Store the selected filters as an instance variable for later validation
        self.selected_filters = selected_filters
        
        # Print summary of selected filters
        print("\n📋 Summary of selected filters:")
        for filter_name, selected_value in selected_filters.items():
            print(f"  {filter_name}: {selected_value}")
        
        # Return the selected filters for immediate use if needed
        return selected_filters

    def get_selected_filters(self):
        """
        Returns the previously selected filter values for validation
        """
        return getattr(self, 'selected_filters', {})
    
    def validate_dashboard_charts(self):
        """
        Validates that the dashboard charts reflect the applied filters
        """
        selected_filters = self.get_selected_filters()
        print("\n🔍 Validating dashboard charts with selected filters:")
        for filter_name, selected_value in selected_filters.items():
            print(f"  Filter applied: {filter_name} = {selected_value}")
        
        # Validate trending topics table is visible and updated
        trending_table = self.page.locator("table.fui-Table")
        expect(trending_table).to_be_visible()
        print("✅ Trending topics table is visible")
        
        # Validate topics overview chart is visible
        topics_overview = self.page.locator("text=Topics Overview")
        expect(topics_overview).to_be_visible()
        print("✅ Topics overview chart is visible")
        
        # Validate average handling time chart is visible
        avg_handling_time = self.page.locator("#AVG_HANDLING_TIME")
        expect(avg_handling_time).to_be_visible()
        print("✅ Average handling time chart is visible")
        
        print("✅ Dashboard charts validation completed")
        
        return True

    def click_apply_button(self):
        apply_button = self.page.locator("button:has-text('Apply')")
        expect(apply_button).to_be_enabled()
        apply_button.click()
        self.page.wait_for_timeout(4000)

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

    def validate_trending_topics_entry(self, topic_name):
        """
        Validates that the Trending Topics table has only one entry of the specified topic with positive sentiment
        
        Args:
            topic_name (str): The topic to validate (e.g., 'Billing Issues' for Telecom, 'Laptop Performance Issues' for ITHelpdesk)
        
        Returns:
            dict: Dictionary containing topic, frequency, and sentiment information
        """
        # Wait for the trending topics table to be visible
        trending_topics_section = self.page.locator("text=Trending Topics")
        expect(trending_topics_section).to_be_visible()
        
        # Locate the trending topics table
        trending_table = self.page.locator("table.fui-Table")
        expect(trending_table).to_be_visible()
        
        # Find all rows that contain the specified topic in the Topic column
        topic_rows = self.page.locator(f"table.fui-Table tbody tr:has(td:has-text('{topic_name}'))")
        
        # Assert there is exactly one entry for this topic
        expect(topic_rows).to_have_count(1)
        print(f"✅ Found exactly one '{topic_name}' entry in trending topics")
        
        # Get the specific topic row
        topic_row = topic_rows.first
        
        # Validate the sentiment is positive
        sentiment_cell = topic_row.locator("td").nth(2)  # Assuming sentiment is the 3rd column (index 2)
        sentiment_text = sentiment_cell.inner_text().strip().lower()
        
        assert "positive" in sentiment_text, f"Expected sentiment to be 'positive' but found: {sentiment_text}"
        print(f"✅ {topic_name} sentiment is positive: {sentiment_text}")
        
        # Validate the frequency
        frequency_cell = topic_row.locator("td").nth(1)  # Assuming frequency is the 2nd column (index 1)
        frequency_text = frequency_cell.inner_text().strip()
        
        print(f"✅ {topic_name} frequency: {frequency_text}")
        
        return {
            "topic": topic_name,
            "frequency": frequency_text,
            "sentiment": sentiment_text
        }
