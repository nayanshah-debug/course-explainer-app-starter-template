"""E2E tests for the main scan flow using Playwright."""
import pytest


def test_page_loads(page):
    pg, base_url = page
    pg.goto(base_url)
    assert "TradingScan" in pg.title() or pg.locator(".logo-text").is_visible()


def test_universe_selector(page):
    pg, base_url = page
    pg.goto(base_url)
    # Click NASDAQ
    pg.locator(".seg-btn", has_text="NASDAQ").click()
    assert pg.locator("#universe-val").input_value() == "nasdaq"


def test_add_filter_row(page):
    pg, base_url = page
    pg.goto(base_url)
    pg.wait_for_selector("#add-filter-btn:not([disabled])", timeout=5000)
    pg.click("#add-filter-btn")
    assert pg.locator(".filter-row").count() == 1


def test_remove_filter_row(page):
    pg, base_url = page
    pg.goto(base_url)
    pg.wait_for_selector("#add-filter-btn:not([disabled])", timeout=5000)
    pg.click("#add-filter-btn")
    pg.locator(".remove-filter-btn").click()
    pg.wait_for_timeout(400)
    assert pg.locator(".filter-row").count() == 0


def test_run_scan_dow(page):
    pg, base_url = page
    pg.goto(base_url)
    pg.wait_for_selector("#add-filter-btn:not([disabled])", timeout=5000)

    # Select DOW universe
    pg.locator(".seg-btn", has_text="DOW 30").click()

    # Click Run Scan
    pg.click("#run-btn")

    # Wait for results or empty state
    pg.wait_for_selector("#results-table-wrap, #results-empty", timeout=30000)

    # Stats bar should be visible
    assert pg.locator("#stats-bar").is_visible()


def test_filter_params_render(page):
    pg, base_url = page
    pg.goto(base_url)
    pg.wait_for_selector("#add-filter-btn:not([disabled])", timeout=5000)
    pg.click("#add-filter-btn")

    # Select ema_crossover — should render fast/slow inputs
    pg.locator(".filter-select").select_option("ema_crossover")
    pg.wait_for_timeout(100)
    assert pg.locator(".param-input").count() >= 1
