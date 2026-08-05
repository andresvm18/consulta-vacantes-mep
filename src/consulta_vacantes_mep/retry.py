"""Retry policy shared by the scrapers.

Replaces the hand-rolled recursion in the scrapers, which nested a Playwright
context per attempt and retried immediately with no backoff.
"""

from collections.abc import Callable

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from consulta_vacantes_mep.exceptions import TransientScrapingError
from consulta_vacantes_mep.settings import SCRAPING
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)


def _log_retry(state: RetryCallState) -> None:
    """Record each retry with its cause and the delay before the next attempt.

    The message matters as much as the type. Playwright puts the operation that
    timed out and what it was waiting for in the message, and the elapsed time
    says whether the attempt ran out its timeout or failed immediately. Logging
    the exception class alone left a warning that named a failure without
    describing it.
    """
    exception = state.outcome.exception() if state.outcome else None

    logger.warning(
        "%s attempt %d/%d failed after %.1fs (%s: %s); retrying in %.1fs",
        getattr(state.fn, "__name__", "call"),
        state.attempt_number,
        SCRAPING.max_retries,
        state.seconds_since_start or 0.0,
        type(exception).__name__ if exception else "unknown",
        exception,
        state.idle_for,
    )


def with_retry[T](function: Callable[..., T]) -> Callable[..., T]:
    """Retry a scraping call on transient failures, with exponential backoff.

    Only TransientScrapingError triggers a retry. PermanentScrapingError
    propagates on the first occurrence: a selector that no longer exists will
    not start existing on the second try, and retrying it across every vacancy
    turns one failure into hundreds.
    """
    return retry(
        retry=retry_if_exception_type(TransientScrapingError),
        stop=stop_after_attempt(SCRAPING.max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before_sleep=_log_retry,
        reraise=True,
    )(function)
