"""Getting a scraping event from a worker thread into Qt.

The whole point of this module is the thread hop, so most of these run the
events through real threads rather than calling emit on the main one. Four of
them, because that is what SCRAPING.max_concurrency puts on the appointments
phase and a single-threaded test would prove nothing about the case that exists.
"""

import threading
from collections.abc import Callable

import pytest
from PySide6.QtCore import QCoreApplication, QObject

from consulta_vacantes_mep.events import (
    Event,
    ItemCompleted,
    Phase,
    PhaseFinished,
    PhaseStarted,
    Reporter,
)
from consulta_vacantes_mep.gui.reporter import QtReporter

Drain = Callable[..., bool]


def _started() -> PhaseStarted:
    return PhaseStarted(Phase.VACANCIES, 19)


def _item(index: int, label: str = "Cartago") -> ItemCompleted:
    return ItemCompleted(Phase.VACANCIES, index, 19, label, 3)


# ── It is a reporter, and it is not a QObject ─────────────────────────────────
def test_it_satisfies_the_reporter_protocol() -> None:
    """Checked by mypy on this annotation rather than at runtime: the protocol
    is not runtime_checkable, and the scrapers accept it structurally."""
    reporter: Reporter = QtReporter()

    assert reporter is not None


def test_it_is_not_a_qobject() -> None:
    """Deliberate. QObject has its own emit, bound to C++, and calling that one
    with arguments meant for this one aborts the interpreter instead of raising.
    A reporter that inherited QObject would answer to both contracts under one
    name.
    """
    assert not isinstance(QtReporter(), QObject)


# ── Events arrive ─────────────────────────────────────────────────────────────
def test_an_event_reaches_a_connected_slot(qt_app: QCoreApplication) -> None:
    reporter = QtReporter()
    received: list[Event] = []
    reporter.progressed.connect(received.append)

    reporter.emit(_started())
    qt_app.processEvents()

    assert received == [_started()]


def test_every_event_type_crosses_unchanged(qt_app: QCoreApplication) -> None:
    """The events are frozen slotted dataclasses and go through the signal as
    objects, so what a slot gets is the record the scraper built, not a copy
    flattened into primitives."""
    reporter = QtReporter()
    received: list[Event] = []
    reporter.progressed.connect(received.append)

    sent: list[Event] = [
        PhaseStarted(Phase.APPOINTMENTS, 45, concurrency=4),
        ItemCompleted(Phase.APPOINTMENTS, 7, 45, "1548639", None),
        PhaseFinished(Phase.APPOINTMENTS, 45, failed=2),
    ]

    for event in sent:
        reporter.emit(event)

    qt_app.processEvents()

    assert received == sent


def test_the_order_of_events_is_kept(qt_app: QCoreApplication) -> None:
    """A progress bar that advances out of order jumps backwards on screen."""
    reporter = QtReporter()
    received: list[Event] = []
    reporter.progressed.connect(received.append)

    for index in range(5):
        reporter.emit(_item(index))

    qt_app.processEvents()

    indexes = [e.index for e in received if isinstance(e, ItemCompleted)]

    assert indexes == [0, 1, 2, 3, 4]


# ── Across threads, which is the reason this exists ───────────────────────────
def test_an_event_from_another_thread_arrives(drain: Drain) -> None:
    reporter = QtReporter()
    received: list[Event] = []
    reporter.progressed.connect(received.append)

    worker = threading.Thread(target=lambda: reporter.emit(_started()))
    worker.start()
    worker.join()

    assert drain(lambda: len(received) == 1)
    assert received == [_started()]


def test_a_slot_runs_on_the_thread_that_connected_it(drain: Drain) -> None:
    """The guarantee the window depends on. A slot that ran on the worker thread
    would be touching widgets from the wrong thread, which Qt does not allow and
    does not reliably refuse either.
    """
    reporter = QtReporter()
    threads: list[str] = []
    reporter.progressed.connect(
        lambda _event: threads.append(threading.current_thread().name)
    )

    worker = threading.Thread(target=lambda: reporter.emit(_started()), name="scraper")
    worker.start()
    worker.join()

    assert drain(lambda: len(threads) == 1)
    assert threads == [threading.current_thread().name]


def test_four_workers_all_get_through(drain: Drain) -> None:
    """The appointments phase runs four browsers at once, each reporting as it
    finishes a vacancy number. Nothing may be dropped on the way in."""
    reporter = QtReporter()
    received: list[Event] = []
    reporter.progressed.connect(received.append)

    def work(worker: int) -> None:
        for index in range(5):
            reporter.emit(_item(worker * 5 + index, f"worker-{worker}"))

    workers = [
        threading.Thread(target=work, args=(number,), name=f"scraper-{number}")
        for number in range(4)
    ]

    for thread in workers:
        thread.start()

    for thread in workers:
        thread.join()

    assert drain(lambda: len(received) == 20)
    indexes = sorted(e.index for e in received if isinstance(e, ItemCompleted))

    assert indexes == list(range(20))


def test_slots_from_four_workers_still_run_on_one_thread(drain: Drain) -> None:
    """Twenty events from four threads, all delivered somewhere a widget can be
    touched from."""
    reporter = QtReporter()
    threads: list[str] = []
    reporter.progressed.connect(
        lambda _event: threads.append(threading.current_thread().name)
    )

    def work(worker: int) -> None:
        for index in range(5):
            reporter.emit(_item(index, f"worker-{worker}"))

    workers = [
        threading.Thread(target=work, args=(number,), name=f"scraper-{number}")
        for number in range(4)
    ]

    for thread in workers:
        thread.start()

    for thread in workers:
        thread.join()

    assert drain(lambda: len(threads) == 20)
    assert set(threads) == {threading.current_thread().name}


# ── Nobody listening ──────────────────────────────────────────────────────────
def test_emitting_with_nothing_connected_is_harmless(
    qt_app: QCoreApplication,
) -> None:
    """A run started before the window finished wiring itself up, or after it
    closed, must not take the scrapers down with it."""
    reporter = QtReporter()

    reporter.emit(_started())
    qt_app.processEvents()


@pytest.mark.parametrize("count", [1, 2])
def test_several_consumers_each_get_the_event(
    count: int, qt_app: QCoreApplication
) -> None:
    """A window and a log view can watch the same run."""
    reporter = QtReporter()
    received: list[list[Event]] = [[] for _ in range(count)]

    for bucket in received:
        reporter.progressed.connect(bucket.append)

    reporter.emit(_started())
    qt_app.processEvents()

    assert all(bucket == [_started()] for bucket in received)
