"""
Pytest configuration and fixtures for KM Generic Golden Path tests
"""
import pytest
from playwright.sync_api import sync_playwright
from config.constants import *
import os
import io
import logging
from bs4 import BeautifulSoup
import atexit
from datetime import datetime

# Create screenshots directory if it doesn't exist
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
print(f"Screenshots will be saved to: {SCREENSHOTS_DIR}")  # Debug line

@pytest.fixture(scope="session")
def login_logout():
    # perform login and browser close once in a session
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        context.set_default_timeout(150000)
        page = context.new_page()
        # Navigate to the login URL
        page.goto(URL, wait_until="domcontentloaded")
        # Wait for the login form to appear
        page.wait_for_timeout(5000)
        #page.wait_for_load_state('networkidle')


        yield page
        # perform close the browser
        browser.close()

log_streams = {}

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    # Prepare StringIO for capturing logs
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)

    logger = logging.getLogger()
    logger.addHandler(handler)

    # Save handler and stream
    log_streams[item.nodeid] = (handler, stream)

@pytest.hookimpl(tryfirst=True)
def pytest_html_report_title(report):
    report.title = "KM_Generic_Smoke_testing_Report"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Generate test report with logs, subtest details, and screenshots on failure"""
    outcome = yield
    report = outcome.get_result()

    # Capture screenshot on failure
    if report.when == "call" and report.failed:
        # Get the page fixture if it exists
        if "login_logout" in item.fixturenames:
            page = item.funcargs.get("login_logout")
            if page:
                try:
                    # Generate screenshot filename with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    test_name = item.name.replace(" ", "_").replace("/", "_")
                    screenshot_name = f"screenshot_{test_name}_{timestamp}.png"
                    screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_name)

                    # Take screenshot
                    page.screenshot(path=screenshot_path)

                    # Add screenshot link to report
                    if not hasattr(report, 'extra'):
                        report.extra = []

                    # Add screenshot as a link in the Links column
                    # Use relative path from report.html location
                    relative_path = os.path.relpath(
                        screenshot_path,
                        os.path.dirname(os.path.abspath("report.html"))
                    )

                    # pytest-html expects this format for extras
                    from pytest_html import extras
                    report.extra.append(extras.url(relative_path, name='Screenshot'))

                    logging.info("Screenshot saved: %s", screenshot_path)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logging.error("Failed to capture screenshot: %s", str(exc))

    handler, stream = log_streams.get(item.nodeid, (None, None))

    if handler and stream:
        # Make sure logs are flushed
        handler.flush()
        log_output = stream.getvalue()

        # Only remove the handler, don't close the stream yet
        logger = logging.getLogger()
        logger.removeHandler(handler)

        # Store the log output on the report object for HTML reporting
        report.description = f"<pre>{log_output.strip()}</pre>"

        # Clean up references
        log_streams.pop(item.nodeid, None)
    else:
        report.description = ""

def pytest_collection_modifyitems(items):
    for item in items:
        if hasattr(item, 'callspec'):
            prompt = item.callspec.params.get("prompt")
            if prompt:
                item._nodeid = prompt  # This controls how the test name appears in the report

def rename_duration_column():
    report_path = os.path.abspath("report.html")  # or your report filename
    if not os.path.exists(report_path):
        print("Report file not found, skipping column rename.")
        return

    with open(report_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # Find and rename the header
    headers = soup.select('table#results-table thead th')
    for th in headers:
        if th.text.strip() == 'Duration':
            th.string = 'Execution Time'
            #print("Renamed 'Duration' to 'Execution Time'")
            break
    else:
        print("'Duration' column not found in report.")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))

# Register this function to run after everything is done
atexit.register(rename_duration_column)