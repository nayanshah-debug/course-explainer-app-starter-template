"""Playwright E2E test fixtures."""
import subprocess
import time
import pytest
from playwright.sync_api import sync_playwright


BASE_URL = "http://localhost:5001"


@pytest.fixture(scope="session")
def flask_server():
    """Start a real Flask dev server for E2E tests."""
    proc = subprocess.Popen(
        ["python", "-m", "flask", "--app", "src/app.py", "run", "--port", "5001"],
        env={**__import__("os").environ, "DATA_PROVIDER": "mock", "FLASK_ENV": "testing"},
    )
    time.sleep(2)  # Wait for server to start
    yield BASE_URL
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="session")
def browser_context(flask_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        yield context, flask_server
        browser.close()


@pytest.fixture
def page(browser_context):
    context, base_url = browser_context
    p = context.new_page()
    yield p, base_url
    p.close()
