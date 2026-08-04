"""Retry policy behavior."""

import pytest

from consulta_vacantes_mep.exceptions import (
    PermanentScrapingError,
    TransientScrapingError,
)
from consulta_vacantes_mep.retry import with_retry


def test_transient_failure_is_retried_until_it_succeeds() -> None:
    attempts = {"count": 0}

    @with_retry
    def flaky() -> str:
        attempts["count"] += 1

        if attempts["count"] < 3:
            raise TransientScrapingError("not yet")

        return "ok"

    assert flaky() == "ok"
    assert attempts["count"] == 3


def test_permanent_failure_is_not_retried() -> None:
    attempts = {"count": 0}

    @with_retry
    def broken() -> None:
        attempts["count"] += 1
        raise PermanentScrapingError("selector gone")

    with pytest.raises(PermanentScrapingError):
        broken()

    assert attempts["count"] == 1


def test_original_exception_propagates_when_attempts_run_out() -> None:
    @with_retry
    def always_fails() -> None:
        raise TransientScrapingError("still broken")

    with pytest.raises(TransientScrapingError, match="still broken"):
        always_fails()
