from pages.HomePage import HomePage
from config.constants import *
from pytest_check import check
import logging

logger = logging.getLogger(__name__)

def test_KM_Generic_Golden_path_test(login_logout):

    """Validate Golden path test case for KM Generic Accelerator """
    page = login_logout
    home_page = HomePage(page)
    
    logger.info("Step 1: Validate home page is loaded.")
    home_page.home_page_load()

    logger.info("Step 2: Validate delete chat history.")
    home_page.delete_chat_history()

    logger.info("Step 3: Validate GP Prompts response.")
    for question in questions:
        #enter question
        home_page.enter_chat_question(question)
        # click on send button
        home_page.click_send_button()
        #validate the response status
        home_page.validate_response_status(question)
        #validate response text
        response_text = page.locator("//p")
        #assert response text
        check.not_equal("I cannot answer this question from the data available. Please rephrase or add more details.", response_text.nth(response_text.count() - 1).text_content(), f"Invalid response for : {question}")
        check.not_equal("Chart cannot be generated.", response_text.nth(response_text.count() - 1).text_content(), f"Invalid response for : {question}")
        
       
    logger.info("Step 4: Validate chat history.")
    home_page.show_chat_history()

    logger.info("Step 5: Validate close chat history.")
    home_page.close_chat_history()
