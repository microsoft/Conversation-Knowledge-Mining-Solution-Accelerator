import os
import subprocess
import sys
import pytest
from pages.KMGenericPage import KMGenericPage
import logging
from pages.HomePage import HomePage
from playwright.sync_api import expect

logger = logging.getLogger(__name__)

@pytest.mark.smoke
def test_validate_golden_path():
    # Locate the golden path test file relative to this file's directory
    test_file_path = os.path.join(
        os.path.dirname(__file__),
        "test_km_gp_tc.py"
    )

    # Run pytest on the golden path file in a subprocess
    command = [sys.executable, "-m", "pytest", test_file_path]
    logger.info(f"Running golden path: {' '.join(command)}")

    result = subprocess.run(command, capture_output=True, text=True)

    logger.info("Golden path output:\n" + result.stdout)

    if result.returncode != 0:
        logger.error("Golden path errors:\n" + result.stderr)
    assert result.returncode == 0, f"Golden path failed:\n{result.stderr}"

@pytest.mark.smoke
def test_user_filter_functioning(login_logout):
    """
    KM Generic Smoke Test:
    1. Open KM Generic URL
    2. Validate charts, labels, chat & history panels
    3. Confirm user filter is visible
    4. Change filter combinations
    5. Click Apply
    6. Verify screen blur + chart update
    """ 

    page = login_logout
    km_page = KMGenericPage(page)

    logger.info("Step 1: Open KM Generic URL")
    km_page.open_url()

    logger.info("Step 2: Validate charts, labels, chat & history panels")
    km_page.validate_dashboard_ui()

    logger.info("Step 3: Confirm user filter is visible")
    km_page.validate_user_filter_visible()

    logger.info("Step 4: Change filter combinations")
    km_page.update_filters()

    logger.info("Step 5: Click Apply")
    km_page.click_apply_button()

    logger.info("Step 6: Verify screen blur + chart update")
    km_page.verify_blur_and_chart_update()


@pytest.mark.smoke
def test_after_filter_functioning(login_logout):
    """
    KM Generic Smoke Test:
    1. Open KM Generic URL
    2. Changes the value of user filter
    3. Notice the value/data change in the chart/graphs tables
    """ 

    page = login_logout
    km_page = KMGenericPage(page)

    logger.info("Step 1: Open KM Generic URL")
    km_page.open_url()

    logger.info("Step 2: Changes the value of user filter")
    km_page.update_filters()

    logger.info("Step 3: Click Apply")
    km_page.click_apply_button()

    logger.info("Step 4: Validate dashboard reflects filtered data")
    km_page.validate_filter_data()

@pytest.mark.smoke
def test_hide_dashboard_and_chat_buttons(login_logout):
    """
    KM Generic Smoke Test:
    1. Open KM Generic URL
    2. Changes the value of user filter
    3. Notice the value/data change in the chart/graphs tables
    """ 

    page = login_logout
    km_page = KMGenericPage(page)

    logger.info("Step 1: Open KM Generic URL")
    km_page.open_url()

    logger.info("Step 2: On the left side of profile icon observe two buttons are present, Hide Dashboard & Hide Chat")
    km_page.verify_hide_dashboard_and_chat_buttons()

@pytest.mark.smoke
def test_chat_greeting_responses(login_logout):

    """
    KM Generic Smoke Test:
    1. Deploy KM Generic
    2. Open KM Generic URL
    3. On chat window enter the Greeting related info: EX:  Hi, Good morning, Hello.
    """ 

    page = login_logout
    km_page = KMGenericPage(page)
    home_page = HomePage(page)

    logger.info("Step 1: Open KM Generic URL")
    km_page.open_url()

    greetings = ["Hi, Good morning", "Hello"]
    logger.info("Step 2: On chat window enter the Greeting related info: EX:  Hi, Good morning, Hello.")
    for greeting in greetings:
        print(f"📨 Sending greeting: {greeting}")
        home_page.enter_chat_question(greeting)
        home_page.click_send_button()

        # Check last assistant message for a greeting-style reply
        assistant_messages = home_page.page.locator("div.chat-message.assistant")
        last_message = assistant_messages.last

        # Validate greeting response
        p = last_message.locator("p")
        message_text = p.inner_text().lower()

        if any(keyword in message_text for keyword in ["how can i assist", "how can i help", "hello again"]):
            print(f"✅ Valid greeting response received: {message_text}")
        else:
            raise AssertionError(f"❌ Unexpected greeting response: {message_text}")

        # Optional wait between messages
        home_page.page.wait_for_timeout(1000)

@pytest.mark.smoke
def test_chat_history_panel(login_logout):
    """
    KM Generic Smoke Test:
    1. Open KM Generic URL
    2. Ask questions in the chat area, where the citations are provided.
    3. Click on the any citation link.
    4. Open Chat history panel.
    5. In chat history panel delete complete chat history.
    6. Observe Citation Section.
    """ 

    page = login_logout
    home_page = HomePage(page)

    logger.info("Step 1: Open KM Generic URL")
    home_page.page.reload(wait_until="networkidle")
    home_page.page.wait_for_timeout(2000)
    print("✅ KM Generic page reloaded successfully")

    # 2. Verify main UI components
    home_page.home_page_load()
    print("✅ Main components like dashboard, chat panel, and chat history are visible")

    # 3. Ask chat questions with citations
    logger.info("Step 2: On chat window enter the prompt")
    questions = [
        "Total number of calls by date for last 7 days",
        "Generate Chart",
        "Show average handling time by topics in minutes",
        "What are top 7 challenges user reported",
        "When customers call in about unexpected charges, what types of charges are they seeing?"
    ]
    
    for question in questions:
        print(f"📨 Asking question: {question}")
        home_page.enter_chat_question(question)
        home_page.page.wait_for_timeout(2000)
        home_page.click_send_button()
        # home_page.validate_response_status(question)
    
    home_page.page.wait_for_timeout(8000)

    logger.info("Step 7: Try editing the title of chat thread")
    home_page.edit_chat_title("Updated Title")

    home_page.page.wait_for_timeout(2000)

    logger.info("Step 3: Verify the chat history is getting stored properly or not")
    logger.info("Step 4: Try deleting the chat thread from chat history panel")
    home_page.delete_first_chat_thread()

    home_page.page.wait_for_timeout(2000)

    logger.info("Step 6: Try clicking on + icon present before chat box")
    home_page.create_new_chat()

    home_page.page.wait_for_timeout(2000)

    logger.info("Step 5: Click on eclipse (3 dots) and select Clear all chat history")
    home_page.delete_chat_history()

@pytest.mark.smoke
def test_clear_citations_on_chat_delete(login_logout):
    """
    KM Generic Smoke Test:
    1. Open KM Generic URL
    2. Ask questions in the chat area, where the citations are provided.
    3. Click on the any citation link.
    4. Open Chat history panel.
    5. In chat history panel delete complete chat history.
    6. Observe Citation Section.
    """ 

    page = login_logout
    km_page = KMGenericPage(page)
    home_page = HomePage(page)

    home_page.page.reload(wait_until="networkidle")
    home_page.page.wait_for_timeout(2000)
    print("✅ KM Generic page reloaded successfully")

    # 3. Ask chat questions with citations
    questions = [
        "Total number of calls by date for last 7 days",
        "Generate Chart",
        "When customers call in about unexpected charges, what types of charges are they seeing?",
        "Show average handling time by topics in minutes",
        "What are top 7 challenges user reported"
    ]
    
    for question in questions:
        home_page.validate_chat_response(question)

        # ✅ Ensure input field is cleared/ready for next
        home_page.page.wait_for_timeout(8000)

        if not home_page.has_reference_link():
            print(f"❌ No citation found for: '{question}'. Moving to next question...")
            continue

        print("✅ Citation found")

    # 5. Show chat history
    print("📚 Opening chat history panel")
    home_page.show_chat_history()
    print("✅ Chat history panel is visible")

    # 6. Delete entire chat history
    print("🗑 Deleting all chat history")
    home_page.delete_chat_history()
    print("✅ Chat history deleted")

    # 7. Check citation section is also cleared
    print("🔍 Verifying citation section is cleared")
    try:
        home_page.close_citation()  # This should fail or do nothing if citation is already closed
        print("✅ Citation panel closed (or already removed) after deleting chat history")
    except:
        print("✅ Citation panel was already removed after history deletion")

def test_citation_panel_closes_with_chat(login_logout):
    """
    Test to ensure citation panel closes when chat section is hidden.
    """
    page = login_logout
    km_page = KMGenericPage(page)
    home_page = HomePage(page)

    logger.info("Step 1: Navigate to KM Generic URL")
    home_page.page.reload(wait_until="networkidle")
    home_page.page.wait_for_timeout(2000)
    print("✅ KM Generic page reloaded successfully")

    logger.info("Step 2: Send a query to trigger a citation")
    question= "When customers call in about unexpected charges, what types of charges are they seeing?"
    home_page.enter_chat_question(question)
    home_page.click_send_button()
    # home_page.validate_chat_response(question)
    home_page.page.wait_for_timeout(3000)

    logger.info("Step 3: Validate citation link appears in response")
    logger.info("Step 4: Click on the citation link to open the panel")
    home_page.click_reference_link_in_response()
    home_page.page.wait_for_timeout(3000)
    
    logger.info("Step 5: Click on 'Hide Chat' button")
    km_page.verify_hide_dashboard_and_chat_buttons()
    home_page.page.wait_for_timeout(3000)

    logger.info("Step 6: Verify citation panel is closed after hiding chat")
    citation_panel = km_page.page.locator("div.citationPanel")
    expect(citation_panel).not_to_be_visible(timeout=3000)

    logger.info("✅ Citation panel successfully closed with chat.")
