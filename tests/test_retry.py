"""Retry policy behavior."""

import pytest

from consulta_vacantes_mep import retry as retry_module
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


class RecordingLogger:
    """Stands in for the module's logger, keeping the arguments of each call."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def warning(self, _message: str, *args: object) -> None:
        self.calls.append(args)


def test_each_retry_logs_the_delay_about_to_be_slept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not the total slept so far, which is what the warning used to show: one
    second, then three, for waits of one and two."""
    recorder = RecordingLogger()
    monkeypatch.setattr(retry_module, "logger", recorder)

    @with_retry
    def always_fails() -> None:
        raise TransientScrapingError("still broken")

    with pytest.raises(TransientScrapingError):
        always_fails()

    delays = [call[-1] for call in recorder.calls]

    assert delays == [1.0, 2.0]
