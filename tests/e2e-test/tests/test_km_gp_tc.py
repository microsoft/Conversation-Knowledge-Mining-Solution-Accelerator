import time
import logging
import pytest
from pytest_check import check
from pages.HomePage import HomePage
from config.constants import *
import io

logger = logging.getLogger(__name__)

# Helper to validate the final response text
def _validate_response_text(page, question):
    response_text = page.locator("//p")
    last_response = response_text.nth(response_text.count() - 1).text_content()
    check.not_equal(
        "I cannot answer this question from the data available. Please rephrase or add more details.",
        last_response,
        f"Invalid response for: {question}"
    )
    check.not_equal(
        "Chart cannot be generated.",
        last_response,
        f"Invalid response for: {question}"
    )

# Helper to check and close citation if it exists
# def _check_and_close_citation(home):
#     if home.has_reference_link():
#         logger.info("Step: Reference link found. Opening citation.")
#         home.click_reference_link_in_response()
#         logger.info("Step: Closing citation.")
#         home.close_citation()

# Define test steps
test_steps = [
    ("Validate home page is loaded", lambda home: home.home_page_load()),
    ("Validate delete chat history", lambda home: home.delete_chat_history()),
]

# Add golden path question prompts
for i, q in enumerate(questions, start=1):
    def _question_step(home, q=q):  # q is default arg to avoid late binding
        home.enter_chat_question(q)
        home.click_send_button()
        home.validate_response_status(q)
        _validate_response_text(home.page, q)
        
        # Include citation check directly
        if home.has_reference_link():
            logger.info(f"[{q}] Reference link found. Opening citation.")
            home.click_reference_link_in_response()
            logger.info(f"[{q}] Closing citation.")
            home.close_citation()

    test_steps.append((f"Validate response for GP Prompt: {q}", _question_step))

# Final chat history validation
test_steps.extend([
    ("Validate chat history is saved", lambda home: home.show_chat_history()),
    ("Validate chat history is closed", lambda home: home.close_chat_history()),
])

# Test ID display for reporting
test_ids = [f"{i+1:02d}. {desc}" for i, (desc, _) in enumerate(test_steps)]

@pytest.mark.parametrize("description, step", test_steps, ids=test_ids)
def test_KM_Generic_Golden_Path(login_logout, description, step, request):
    request.node._nodeid = description

    page = login_logout
    home_page = HomePage(page)
    home_page.page = page

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger.addHandler(handler)

    logger.info(f"Running test step: {description}")
    start = time.time()

    try:
        step(home_page)
    finally:
        duration = time.time() - start
        logger.info(f"Execution Time for '{description}': {duration:.2f}s")
        logger.removeHandler(handler)

        # Attach logs
        request.node._report_sections.append((
            "call", "log", log_capture.getvalue()
        ))