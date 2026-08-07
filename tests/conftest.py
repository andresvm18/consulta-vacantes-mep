"""Shared fixtures for the test suite."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    """One browser for the whole session; launching is the expensive part."""
    with sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    """A fresh page per test, so no test can leak state into another."""
    instance = browser.new_page()
    yield instance
    instance.close()


@pytest.fixture
def load_fixture(page: Page) -> Callable[[str], Page]:
    """Load a saved HTML fixture into the page and return it."""
    def _load(name: str) -> Page:
        html = (FIXTURE_DIR / name).read_text(encoding="utf-8")
        page.set_content(html)
        return page

    return _load
