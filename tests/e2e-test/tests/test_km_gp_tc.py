"""
KM Generic Golden Path Test Module
Tests the complete golden path workflow for KM Generic application
"""
import time
import logging
import pytest
from pages.HomePage import HomePage
from config.constants import questions

logger = logging.getLogger(__name__)

# Define test steps
test_steps = [
    ("Validate home page is loaded", lambda home: home.home_page_load()),
    ("Validate delete chat history", lambda home: home.delete_chat_history()),
]

# Add golden path question prompts
for i, question in enumerate(questions, start=1):
    def _question_step(home, q=question):  # q is default arg to avoid late binding
        home.enter_chat_question(q)
        home.click_send_button()
        home.validate_response_text(q)

        # Include citation check directly
        if home.has_reference_link():
            logger.info("[%s] Reference link found. Opening citation.", q)
            home.click_reference_link_in_response()
            logger.info("[%s] Closing citation.", q)
            home.close_citation()

    test_steps.append((f"Validate response for GP Prompt: {question}", _question_step))

# Final chat history validation
test_steps.extend([
    ("Validate chat history is saved", lambda home: home.show_chat_history()),
    ("Validate chat history is closed", lambda home: home.close_chat_history()),
])

# Test ID display for reporting
test_ids = [f"Step {i+1:02d}: {desc}" for i, (desc, _) in enumerate(test_steps)]

@pytest.mark.smoke
@pytest.mark.parametrize("description, step", test_steps, ids=test_ids)
def test_km_generic_golden_path(login_logout, description, step):
    """
    KM Generic Golden Path Smoke Test - Each step runs as a separate test in the HTML report
    """
    page = login_logout
    home_page = HomePage(page)
    home_page.page = page

    logger.info("Running test step: %s", description)
    start = time.time()

    # Execute the step with retry logic for question steps
    max_retries = 2

    for attempt in range(max_retries):
        try:
            step(home_page)
            logger.info("Step completed successfully on attempt %d", attempt + 1)
            break
        except Exception as exc:  # pylint: disable=broad-exception-caught
            if attempt < max_retries - 1 and "Validate response for GP Prompt" in description:
                logger.warning("Attempt %d failed: %s", attempt + 1, str(exc))
                logger.info("Retrying... (attempt %d/%d)", attempt + 2, max_retries)
                home_page.page.wait_for_timeout(2000)
            else:
                logger.error("Step failed after %d attempt(s): %s", attempt + 1, str(exc))
                raise

    duration = time.time() - start
    logger.info("Execution Time for '%s': %.2fs", description, duration)

