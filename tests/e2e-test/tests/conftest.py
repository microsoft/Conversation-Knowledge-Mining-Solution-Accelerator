from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
from config.constants import *
from slugify import slugify
from pages.loginPage import LoginPage
from dotenv import load_dotenv
import os
from py.xml import html # type: ignore


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
        page.wait_for_timeout(60000)
        #page.wait_for_load_state('networkidle')


        yield page
        # perform close the browser
        browser.close()


@pytest.hookimpl(tryfirst=True)
def pytest_html_report_title(report):
    report.title = "Automation_KM_Generic"


# Add a column for descriptions
def pytest_html_results_table_header(cells):
    cells.insert(1, html.th("Description"))

def pytest_html_results_table_row(report, cells):
    cells.insert(1, html.td(report.description if hasattr(report, "description") else ""))

# Add logs and docstring to report
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    report.description = str(item.function.__doc__)
    os.makedirs("logs", exist_ok=True)
    extra = getattr(report, 'extra', [])
    report.extra = extra
