"""Opening the vacancies page, and what a run does when it cannot.

A run against the live site died on its first wait: the page took longer than
three seconds to render, the error was logged, and an empty list came back. The
terminal then said no vacancies had been found, which was not true; nobody had
looked. These pin both halves of the fix: the first load gets more patience and
a retry, and a run that still cannot read the site says so by raising.

No browser here. The page and the Playwright entry point are replaced by
doubles, since what is under test is the decision made around them.
"""

from typing import cast

import pytest
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from consulta_vacantes_mep.exceptions import ScrapingError, TransientScrapingError
from consulta_vacantes_mep.scrapers import vacancies as vacancies_module
from consulta_vacantes_mep.scrapers.vacancies import (
    RegionalOffice,
    scrape_all_vacancies,
)
from consulta_vacantes_mep.settings import SCRAPING


# ── Opening the page ──────────────────────────────────────────────────────────
class FakePage:
    """A page whose first few loads never finish rendering."""

    def __init__(self, slow_loads: int = 0) -> None:
        self.slow_loads = slow_loads
        self.loads = 0
        self.wait_timeouts: list[object] = []

    def goto(self, _url: str, **_: object) -> None:
        self.loads += 1

    def wait_for_function(self, _expression: str, **kwargs: object) -> None:
        timeout = kwargs.get("timeout")
        self.wait_timeouts.append(timeout)

        if self.loads <= self.slow_loads:
            message = f"Timeout {timeout}ms exceeded."
            raise PlaywrightTimeout(message)


def test_a_slow_first_load_is_tried_again() -> None:
    """What ended the run on the live site. A second load is what a person
    would do, and the retry policy already knows how."""
    page = FakePage(slow_loads=1)

    vacancies_module._open_vacancies_page_with_retry(cast(Page, page))

    assert page.loads == 2


def test_a_load_that_never_renders_is_reported_as_transient() -> None:
    """Classified like every other timeout, so the retry policy can act on it."""
    page = FakePage(slow_loads=1)

    with pytest.raises(TransientScrapingError):
        vacancies_module._open_vacancies_page(cast(Page, page))


def test_the_first_load_gets_more_time_than_the_grid() -> None:
    """The two waits shared three seconds, which suits a grid that settles in
    under one and not a page loading for the first time."""
    page = FakePage()

    vacancies_module._open_vacancies_page(cast(Page, page))

    assert page.wait_timeouts == [SCRAPING.page_ready_timeout_ms]
    assert SCRAPING.page_ready_timeout_ms > SCRAPING.grid_timeout_ms


# ── What a run does with a failure ────────────────────────────────────────────
class FakeBrowser:
    def __init__(self) -> None:
        self.closed = False

    def new_page(self) -> object:
        return object()

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self._browser = browser

    def launch(self, **_: object) -> FakeBrowser:
        return self._browser


class FakePlaywright:
    """Stands in for the context manager sync_playwright() returns."""

    def __init__(self, browser: FakeBrowser) -> None:
        self.chromium = FakeChromium(browser)

    def __enter__(self) -> "FakePlaywright":
        return self

    def __exit__(self, *_: object) -> None:
        return None


@pytest.fixture
def fake_browser(monkeypatch: pytest.MonkeyPatch) -> FakeBrowser:
    instance = FakeBrowser()
    monkeypatch.setattr(vacancies_module, "sync_playwright", lambda: FakePlaywright(instance))
    return instance


def _page_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vacancies_module, "_open_vacancies_page_with_retry", lambda _page: None)


def test_a_page_that_never_loads_raises_instead_of_finding_nothing(
    fake_browser: FakeBrowser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bug itself. An empty list here is what made the terminal say there
    were no vacancies."""

    def _never_loads(_page: object) -> None:
        message = "vacancies page: timed out"
        raise TransientScrapingError(message)

    monkeypatch.setattr(vacancies_module, "_open_vacancies_page_with_retry", _never_loads)

    with pytest.raises(ScrapingError):
        scrape_all_vacancies()

    assert fake_browser.closed


def test_an_unexpected_failure_raises_too(
    fake_browser: FakeBrowser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wrapped in the application's own type, so an interface has one thing to
    catch. The original stays attached for the log."""
    _page_loads(monkeypatch)

    def _broken(_page: object) -> list[RegionalOffice]:
        message = "something odd"
        raise ValueError(message)

    monkeypatch.setattr(vacancies_module, "_get_regional_offices", _broken)

    with pytest.raises(ScrapingError) as raised:
        scrape_all_vacancies()

    assert isinstance(raised.value.__cause__, ValueError)
    assert fake_browser.closed


def test_a_site_with_nothing_published_still_comes_back_empty(
    fake_browser: FakeBrowser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other side of the line. No offices listed is an answer, not a
    failure, and raising on it would be the opposite mistake."""
    _page_loads(monkeypatch)
    monkeypatch.setattr(vacancies_module, "_get_regional_offices", lambda _page: [])

    assert scrape_all_vacancies() == []
    assert fake_browser.closed
