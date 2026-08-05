"""Tests for the bookkeeping around concurrent appointment lookups.

These cover the guarantee the caller depends on: one AppointmentQuery comes
back for every vacancy number handed in, whatever the worker threads did. None
of it touches a browser.
"""

import queue
import threading

from consulta_vacantes_mep.models import AppointmentQuery, QueryOutcome
from consulta_vacantes_mep.scrapers.appointments import _collect, _drain, _unanswered


def _query(number: str, outcome: QueryOutcome = QueryOutcome.EMPTY) -> AppointmentQuery:
    return AppointmentQuery(number, outcome, [])


def _dead_thread() -> threading.Thread:
    """A thread that has already finished, so is_alive() is False."""
    thread = threading.Thread(target=lambda: None)
    thread.start()
    thread.join()
    return thread


def test_drain_empties_the_queue() -> None:
    results: queue.Queue[AppointmentQuery] = queue.Queue()
    results.put(_query("1"))
    results.put(_query("2"))

    drained = _drain(results)

    assert [q.vacancy_number for q in drained] == ["1", "2"]
    assert results.empty()


def test_drain_of_an_empty_queue_returns_nothing() -> None:
    results: queue.Queue[AppointmentQuery] = queue.Queue()

    assert _drain(results) == []


def test_unanswered_marks_numbers_nobody_reported() -> None:
    unanswered = _unanswered(["1", "2", "3"], [_query("2")])

    assert [q.vacancy_number for q in unanswered] == ["1", "3"]
    assert all(q.outcome is QueryOutcome.FAILED for q in unanswered)
    assert all(q.error for q in unanswered)


def test_unanswered_is_empty_when_every_number_was_reported() -> None:
    collected = [_query("1"), _query("2")]

    assert _unanswered(["1", "2"], collected) == []


def test_collect_returns_every_result() -> None:
    results: queue.Queue[AppointmentQuery] = queue.Queue()

    for number in ("1", "2", "3"):
        results.put(_query(number))

    collected = _collect(results, [_dead_thread()], total=3)

    assert [q.vacancy_number for q in collected] == ["1", "2", "3"]


def test_collect_gives_up_when_no_worker_is_left() -> None:
    """A collector that blocked forever would hang the whole program."""
    results: queue.Queue[AppointmentQuery] = queue.Queue()
    results.put(_query("1"))

    collected = _collect(results, [_dead_thread()], total=3)

    assert [q.vacancy_number for q in collected] == ["1"]
