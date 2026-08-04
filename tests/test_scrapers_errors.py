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
