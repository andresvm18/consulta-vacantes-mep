"""Classification of Playwright failures."""

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from consulta_vacantes_mep.exceptions import (
    PermanentScrapingError,
    TransientScrapingError,
)
from consulta_vacantes_mep.scrapers.errors import classify


def test_timeout_is_transient() -> None:
    result = classify(PlaywrightTimeout("Timeout 8000ms exceeded"), "vacancy 1")
    assert isinstance(result, TransientScrapingError)


def test_missing_selector_is_permanent() -> None:
    result = classify(
        PlaywrightError("Element not found: #txtCedula"), "vacancy 1"
    )
    assert isinstance(result, PermanentScrapingError)


def test_unknown_error_defaults_to_transient() -> None:
    result = classify(ValueError("something odd"), "vacancy 1")
    assert isinstance(result, TransientScrapingError)


def test_no_connection_is_transient() -> None:
    """The message a machine without a connection produces. It contains
    "resolve", which the selector heuristic used to read as a changed page."""
    result = classify(
        PlaywrightError(
            "Page.goto: net::ERR_NAME_NOT_RESOLVED at https://apps.mep.go.cr/formulario"
        ),
        "vacancies page",
    )
    assert isinstance(result, TransientScrapingError)


def test_a_dropped_connection_is_transient() -> None:
    result = classify(
        PlaywrightError("Page.goto: net::ERR_CONNECTION_RESET at https://apps.mep.go.cr/"),
        "vacancy 1",
    )
    assert isinstance(result, TransientScrapingError)


def test_a_network_failure_is_described_as_one() -> None:
    """The log line is what a developer reads first. "page structure changed"
    sent the reader to the selectors for a machine that was offline."""
    result = classify(
        PlaywrightError("Page.goto: net::ERR_INTERNET_DISCONNECTED at https://x"),
        "vacancies page",
    )
    assert "network error" in str(result)
