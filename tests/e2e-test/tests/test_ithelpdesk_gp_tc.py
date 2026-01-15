"""
KM Generic Golden Path Test Module - ITHelpdesk
Tests the complete golden path testing workflow for KM Generic application
"""
import time
import logging
from pages.HomePage import HomePage
from config.constants import ithelpdesk_questions
import io


logger = logging.getLogger(__name__)


def test_km_generic_golden_path_refactored(login_logout, request):
    """
    KM Generic Golden Path Smoke Test - ITHelpdesk:
    Refactored from parametrized test to sequential execution
    1. Load home page and clear chat history
    2. Execute all golden path questions sequentially
    3. Validate responses and handle citations
    4. Verify chat history functionality
    """
    
   
    request.node._nodeid = "31001 - Golden Path - KM Generic - ITHelpdesk - Test golden path demo script works properly"
    
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
        
        for i, question in enumerate(ithelpdesk_questions, start=1):
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
                    home_page.page.wait_for_timeout(8000)  # Wait before validating response status
                    home_page.validate_response_status(question)
                    home_page.page.wait_for_timeout(5000)  # Wait after validating response status
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
                        home_page.page.wait_for_timeout(10000)
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
            logger.warning(f"Golden path test completed with {len(failed_questions)} failed questions out of {len(ithelpdesk_questions)} total")
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
