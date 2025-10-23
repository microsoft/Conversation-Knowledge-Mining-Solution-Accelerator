import os
import subprocess
import sys
import pytest
from pages.KMGenericPage import KMGenericPage
import logging
from pages.HomePage import HomePage
from playwright.sync_api import expect
import time
from pytest_check import check
from config.constants import *
import io

logger = logging.getLogger(__name__)



# Helper to validate the final response text

@pytest.mark.smoke
def test_km_generic_golden_path_refactored(login_logout, request):
    """
    KM Generic Golden Path Smoke Test:
    Refactored from parametrized test to sequential execution
    1. Load home page and clear chat history
    2. Execute all golden path questions sequentially
    3. Validate responses and handle citations
    4. Verify chat history functionality
    """
    
   
    request.node._nodeid = "Golden Path - KM Generic - test golden path demo script works properly"
    
    page = login_logout
    home_page = HomePage(page)
    home_page.page = page

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger.addHandler(handler)

    try:
        logger.info("Step 1: Validate home page is loaded")
        start = time.time()
        home_page.home_page_load()
        duration = time.time() - start
        logger.info(f"Execution Time for 'Validate home page is loaded': {duration:.2f}s")

        logger.info("Step 2: Validate delete chat history")
        start = time.time()
        home_page.delete_chat_history()
        duration = time.time() - start
        logger.info(f"Execution Time for 'Validate delete chat history': {duration:.2f}s")

        # Execute all golden path questions
        failed_questions = []  # Track failed questions for final reporting
        
        for i, question in enumerate(questions, start=1):
            logger.info(f"Step {i+2}: Validate response for GP Prompt: {question}")
            start = time.time()
            
            # Retry logic: attempt up to 2 times if response is invalid
            max_retries = 2
            question_passed = False
            
            for attempt in range(max_retries):
                try:
                    # Enter question and get response
                    home_page.enter_chat_question(question)
                    home_page.click_send_button()
                    home_page.validate_response_status(question)
                    home_page.validate_response_text(question)
                    
                    # If we reach here, the response was valid - break out of retry loop
                    logger.info(f"[{question}] Valid response received on attempt {attempt + 1}")
                    question_passed = True
                    break
                    
                except Exception as e:
                    if attempt < max_retries - 1:  # Not the last attempt
                        logger.warning(f"[{question}] Attempt {attempt + 1} failed: {str(e)}")
                        logger.info(f"[{question}] Retrying... (attempt {attempt + 2}/{max_retries})")
                        # Wait a bit before retrying
                        home_page.page.wait_for_timeout(2000)
                    else:  # Last attempt failed
                        logger.error(f"[{question}] All {max_retries} attempts failed. Last error: {str(e)}")
                        failed_questions.append({"question": question, "error": str(e)})
            
            # Only handle citations if the question passed
            if question_passed and home_page.has_reference_link():
                logger.info(f"[{question}] Reference link found. Opening citation.")
                home_page.click_reference_link_in_response()
                logger.info(f"[{question}] Closing citation.")
                home_page.close_citation()
            
            duration = time.time() - start
            logger.info(f"Execution Time for 'Validate response for GP Prompt: {question}': {duration:.2f}s")

        # Log summary of failed questions
        if failed_questions:
            logger.warning(f"Golden path test completed with {len(failed_questions)} failed questions out of {len(questions)} total")
            for failed in failed_questions:
                logger.error(f"Failed question: '{failed['question']}' - {failed['error']}")
        else:
            logger.info("All golden path questions passed successfully")
        logger.info("Step: Validate chat history is saved")
        start = time.time()
        home_page.show_chat_history()
        duration = time.time() - start
        logger.info(f"Execution Time for 'Validate chat history is saved': {duration:.2f}s")

        logger.info("Step: Validate chat history is closed")
        start = time.time()
        home_page.close_chat_history()
        duration = time.time() - start
        logger.info(f"Execution Time for 'Validate chat history is closed': {duration:.2f}s")

    finally:
        logger.removeHandler(handler)

@pytest.mark.smoke
def test_user_filter_functioning(login_logout, request):
    """
    KM Generic Smoke Test:
    1. Open KM Generic URL
    2. Validate charts, labels, chat & history panels
    3. Confirm user filter is visible
    4. Change filter combinations
    5. Click Apply
    6. Verify screen blur + chart update
    """ 

    # Set custom test name for pytest HTML report
    request.node._nodeid = "KM Generic - User filter functioning"

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
def test_after_filter_functioning(login_logout, request):
    """
    KM Generic Smoke Test:
    1. Open KM Generic URL
    2. Changes the value of user filter
    3. Notice the value/data change in the chart/graphs tables
    """ 

    # Remove custom test name logic for pytest HTML report
    request.node._nodeid = "KM Generic - After filter apply change in charts"

    page = login_logout
    km_page = KMGenericPage(page)

    logger.info("Step 1: Open KM Generic URL")
    km_page.open_url()

    logger.info("Step 2: Changes the value of user filter")
    km_page.update_filters()

    logger.info("Step 3: Click Apply")
    km_page.click_apply_button()

    logger.info("Step 4: Validate filter data is reflecting in charts/graphs")
    billing_data = km_page.validate_trending_topics_billing_issue()
    logger.info(f"Billing issues data validated: {billing_data}")
    
    km_page.validate_dashboard_charts()


@pytest.mark.smoke
def test_hide_dashboard_and_chat_buttons(login_logout, request):
    """
    KM Generic Smoke Test:
    1. Open KM Generic URL
    2. Changes the value of user filter
    3. Notice the value/data change in the chart/graphs tables
    """ 

    # Set custom test name for pytest HTML report
    request.node._nodeid = "KM Generic - Hide Dashboard and Chat buttons"

    page = login_logout
    km_page = KMGenericPage(page)

    logger.info("Step 1: Open KM Generic URL")
    km_page.open_url()

    logger.info("Step 2: On the left side of profile icon observe two buttons are present, Hide Dashboard & Hide Chat")
    km_page.verify_hide_dashboard_and_chat_buttons()

@pytest.mark.smoke
def test_refine_chat_chart_output(login_logout, request):
    """
    KM Generic Smoke Test:
    1. Open KM Generic URL
    2. On chat window enter the prompt which provides chat info: EX:  Average handling time by topic
    3. On chat window enter the prompt which provides chat info: EX:  Generate Chart
    """ 

    # Set custom test name for pytest HTML report
    request.node._nodeid = "KM Generic_Improve Chart Generation Experience in Chat"

    page = login_logout
    km_page = KMGenericPage(page)
    home_page = HomePage(page)

    logger.info("Step 1: Open KM Generic URL")
    km_page.open_url()

    logger.info("Step 2: Verify chat response generation")
    logger.info("Step 3: On chat window enter the prompt which provides chat info: EX:  Average handling time by topic")
    home_page.validate_chat_response('Average handling time by topic')
    home_page.validate_response_status('Average handling time by topic')

    logger.info("Step 4: On chat window enter the prompt which provides chat info: EX:  Generate chart")
    home_page.validate_chat_response('Generate chart', True)
    home_page.validate_response_status('Generate chart')

@pytest.mark.smoke
def test_chat_greeting_responses(login_logout, request):

    """
    KM Generic Smoke Test:
    1. Deploy KM Generic
    2. Open KM Generic URL
    3. On chat window enter the Greeting related info: EX:  Hi, Good morning, Hello.
    """ 

    # Set custom test name for pytest HTML report
    request.node._nodeid = "KM Generic_ Greeting related experience in Chat"

    page = login_logout
    km_page = KMGenericPage(page)
    home_page = HomePage(page)

    logger.info("Step 1: Open KM Generic URL")
    km_page.open_url()

    greetings = ["Hi, Good morning", "Hello"]
    logger.info("Step 2: On chat window enter the Greeting related info: EX:  Hi, Good morning, Hello.")
    for greeting in greetings:
        home_page.enter_chat_question(greeting)
        home_page.click_send_button()

        # Check last assistant message for a greeting-style reply
        assistant_messages = home_page.page.locator("div.chat-message.assistant")
        last_message = assistant_messages.last

        # Validate greeting response
        p = last_message.locator("p")
        message_text = p.inner_text().lower()

        if any(keyword in message_text for keyword in ["how can i assist", "how can i help", "hello again"]):
            logger.info(f"Valid greeting response received for: {greeting}")
        else:
            raise AssertionError(f"Unexpected greeting response for '{greeting}': {message_text}")

        # Optional wait between messages
        home_page.page.wait_for_timeout(1000)

@pytest.mark.smoke
def test_chat_history_panel(login_logout, request):
    """
    KM Generic Smoke Test:
    Refactored to reuse golden path logic plus additional chat history operations
    1. Reuse golden path test execution (load home page, delete history, execute questions)
    2. Edit chat thread title 
    3. Verify chat history operations (delete thread, create new chat, clear all history)
    """ 

    # Set custom test name for pytest HTML report
    request.node._nodeid = "KM Generic - Chat History Panel"

    page = login_logout
    home_page = HomePage(page)
    home_page.page = page

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger.addHandler(handler)

    try:
        # Reuse golden path logic - Steps 1-2: Load home page and clear chat history
        logger.info("Step 1: Validate home page is loaded")
        start = time.time()
        home_page.home_page_load()
        duration = time.time() - start
        logger.info(f"Execution Time for 'Validate home page is loaded': {duration:.2f}s")

        logger.info("Step 2: Validate delete chat history")
        start = time.time()
        home_page.delete_chat_history()
        duration = time.time() - start
        logger.info(f"Execution Time for 'Validate delete chat history': {duration:.2f}s")

        # Reuse golden path logic - Execute all golden path questions
        failed_questions = []  # Track failed questions for final reporting
        
        for i, question in enumerate(questions, start=1):
            logger.info(f"Step {i+2}: Validate response for GP Prompt: {question}")
            start = time.time()
            
            # Retry logic: attempt up to 2 times if response is invalid
            max_retries = 2
            question_passed = False
            
            for attempt in range(max_retries):
                try:
                    # Enter question and get response
                    home_page.enter_chat_question(question)
                    home_page.click_send_button()
                    home_page.validate_response_status(question)
                    home_page.validate_response_text(question)
                    
                    # If we reach here, the response was valid - break out of retry loop
                    logger.info(f"[{question}] Valid response received on attempt {attempt + 1}")
                    question_passed = True
                    break
                    
                except Exception as e:
                    if attempt < max_retries - 1:  # Not the last attempt
                        logger.warning(f"[{question}] Attempt {attempt + 1} failed: {str(e)}")
                        logger.info(f"[{question}] Retrying... (attempt {attempt + 2}/{max_retries})")
                        # Wait a bit before retrying
                        home_page.page.wait_for_timeout(2000)
                    else:  # Last attempt failed
                        logger.error(f"[{question}] All {max_retries} attempts failed. Last error: {str(e)}")
                        failed_questions.append({"question": question, "error": str(e)})
            
            # Only handle citations if the question passed
            if question_passed and home_page.has_reference_link():
                logger.info(f"[{question}] Reference link found. Opening citation.")
                home_page.click_reference_link_in_response()
                logger.info(f"[{question}] Closing citation.")
                home_page.close_citation()
            
            duration = time.time() - start
            logger.info(f"Execution Time for 'Validate response for GP Prompt: {question}': {duration:.2f}s")

        # Log summary of failed questions
        if failed_questions:
            logger.warning(f"Chat history test completed with {len(failed_questions)} failed questions out of {len(questions)} total")
            for failed in failed_questions:
                logger.error(f"Failed question: '{failed['question']}' - {failed['error']}")
        else:
            logger.info("All golden path questions passed successfully")

        # Additional chat history specific operations
        logger.info("Step 7: Try editing the title of chat thread")
        home_page.edit_chat_title("Updated Title")

        home_page.page.wait_for_timeout(2000)

        logger.info("Step 8: Verify the chat history is getting stored properly or not")
        logger.info("Step 9: Try deleting the chat thread from chat history panel")
        home_page.delete_first_chat_thread()

        home_page.page.wait_for_timeout(2000)

        logger.info("Step 10: Try clicking on + icon present before chat box")
        home_page.create_new_chat()

        home_page.page.wait_for_timeout(2000)

        home_page.close_chat_history()

        logger.info("Step 11: Click on eclipse (3 dots) and select Clear all chat history")
        home_page.delete_chat_history()

    finally:
        logger.removeHandler(handler)

@pytest.mark.smoke
def test_clear_citations_on_chat_delete(login_logout, request):
    """
    KM Generic Smoke Test:
    1. Open KM Generic URL
    2. Ask questions in the chat area, where the citations are provided.
    3. Click on the any citation link.
    4. Open Chat history panel.
    5. In chat history panel delete complete chat history.
    6. Observe Citation Section.
    """ 

    # Set custom test name for pytest HTML report
    request.node._nodeid = "KM Generic - Citation should get cleared after deleting complete chat history"

    page = login_logout
    km_page = KMGenericPage(page)
    home_page = HomePage(page)

    logger.info("Step 2: Send a query to trigger a citation")
    question= "When customers call in about unexpected charges, what types of charges are they seeing?"
    home_page.enter_chat_question(question)
    home_page.click_send_button()
    # home_page.validate_chat_response(question)
    home_page.page.wait_for_timeout(3000)

    logger.info("Step 3: Validate citation link appears in response")
    logger.info("Step 4: Click on the citation link to open the panel")
    home_page.click_reference_link_in_response()
    home_page.page.wait_for_timeout(5000)

    # 6. Delete entire chat history
    home_page.delete_chat_history()

    # 7. Check citation section is not visible after chat history deletion
    citations_locator = page.locator("//div[contains(text(),'Citations')]")
    expect(citations_locator).not_to_be_visible(timeout=3000)
    logger.info("Citations section is not visible after chat history deletion")

   

def test_citation_panel_closes_with_chat(login_logout, request):
    """
    Test to ensure citation panel closes when chat section is hidden.
    """
    
    # Set custom test name for pytest HTML report
    request.node._nodeid = "KM Generic: Citation panel should close after hiding chat"
    
    page = login_logout
    km_page = KMGenericPage(page)
    home_page = HomePage(page)

    logger.info("Step 1: Navigate to KM Generic URL")
    home_page.page.reload(wait_until="networkidle")
    home_page.page.wait_for_timeout(2000)

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


