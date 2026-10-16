"""Running a search somewhere other than the thread that draws the window.

The Session is a double throughout. What is under test is the thread and the
signals, not the scraping, and a real Session would need a browser to reach any
of it. One of the doubles blocks until a test lets it finish, which is how the
is_running cases are checked without a sleep deciding whether they pass.
"""

import threading
from collections.abc import Callable

import pytest
from PySide6.QtCore import Qt

from consulta_vacantes_mep.app.session import SearchResult
from consulta_vacantes_mep.exceptions import PermanentScrapingError
from consulta_vacantes_mep.gui.worker import SearchWorker
from consulta_vacantes_mep.models import Vacancy

Drain = Callable[..., bool]

PUBLISHED = [
    Vacancy(
        number="1548582",
        regional_office="Direc. Regional Educacion Cartago",
        position_class="Profesor de Enseñanza Media",
        specialty="Francés",
        institution="Liceo de Prueba",
        lessons="10",
        starts_on="01/10/2026",
        ends_on="12/11/2026",
    )
]


class FakeSession:
    """Records what it was asked for, and answers without a browser."""

    def __init__(
        self,
        *,
        raises: Exception | None = None,
        gate: threading.Event | None = None,
    ) -> None:
        self.search_calls: list[tuple[int, str | None]] = []
        self.vacancy_calls: list[tuple[str | None, bool]] = []
        self.threads: list[str] = []
        self._raises = raises
        self._gate = gate

    def _work(self) -> None:
        self.threads.append(threading.current_thread().name)

        if self._gate is not None:
            self._gate.wait(timeout=5)

        if self._raises is not None:
            raise self._raises

    def search(self, year: int, specialty: str | None = None) -> SearchResult:
        self.search_calls.append((year, specialty))
        self._work()
        return SearchResult(vacancies=PUBLISHED, queries=[])

    def vacancies(
        self, specialty: str | None = None, *, refresh: bool = False
    ) -> list[Vacancy]:
        self.vacancy_calls.append((specialty, refresh))
        self._work()
        return list(PUBLISHED)


def _worker(**kwargs: object) -> tuple[SearchWorker, FakeSession]:
    session = FakeSession(**kwargs)  # type: ignore[arg-type]
    return SearchWorker(session), session  # type: ignore[arg-type]


# ── The work happens elsewhere ────────────────────────────────────────────────
def test_the_search_does_not_run_on_the_calling_thread(drain: Drain) -> None:
    """The reason this module exists. A run takes about half a minute, and a
    window that spends it inside a function has stopped repainting."""
    worker, session = _worker()
    results: list[object] = []
    worker.searched.connect(results.append)

    worker.search(2026)

    assert drain(lambda: len(results) == 1)
    assert session.threads != [threading.current_thread().name]


def test_the_result_arrives_on_the_thread_that_connected(drain: Drain) -> None:
    """Which is where the widgets are. Qt decides this from the receiver."""
    worker, _ = _worker()
    threads: list[str] = []
    worker.searched.connect(lambda _r: threads.append(threading.current_thread().name))

    worker.search(2026)

    assert drain(lambda: len(threads) == 1)
    assert threads == [threading.current_thread().name]


def test_the_search_result_comes_back_whole(drain: Drain) -> None:
    worker, _ = _worker()
    results: list[SearchResult] = []
    worker.searched.connect(results.append)

    worker.search(2026)

    assert drain(lambda: len(results) == 1)
    assert results[0].vacancies == PUBLISHED


# ── What it asks the session ──────────────────────────────────────────────────
def test_the_year_and_specialty_are_passed_through(drain: Drain) -> None:
    worker, session = _worker()
    done: list[object] = []
    worker.searched.connect(done.append)

    worker.search(2025, "Matemática")

    assert drain(lambda: len(done) == 1)
    assert session.search_calls == [(2025, "Matemática")]


def test_no_specialty_means_every_vacancy(drain: Drain) -> None:
    worker, session = _worker()
    done: list[object] = []
    worker.searched.connect(done.append)

    worker.search(2026)

    assert drain(lambda: len(done) == 1)
    assert session.search_calls == [(2026, None)]


def test_a_refresh_asks_for_a_rescrape_of_everything(drain: Drain) -> None:
    """No specialty on a refresh. One that carried a filter would report the
    filtered count as the number of vacancies now cached."""
    worker, session = _worker()
    counts: list[int] = []
    worker.refreshed.connect(counts.append)

    worker.refresh()

    assert drain(lambda: len(counts) == 1)
    assert session.vacancy_calls == [(None, True)]
    assert counts == [len(PUBLISHED)]


def test_the_same_session_is_used_for_every_run(drain: Drain) -> None:
    """The vacancy cache lives in the Session, so a worker that built a new one
    per run would rescrape every time and make refreshing meaningless."""
    worker, session = _worker()
    done: list[object] = []
    worker.searched.connect(done.append)

    worker.search(2026)
    assert drain(lambda: len(done) == 1)

    worker.search(2026, "Francés")
    assert drain(lambda: len(done) == 2)

    assert session.search_calls == [(2026, None), (2026, "Francés")]


# ── When it goes wrong ────────────────────────────────────────────────────────
def test_a_failure_arrives_as_a_signal(drain: Drain) -> None:
    """Not as an exception on a thread nobody is watching. A window waiting for
    a result it will never get is the worse failure."""
    error = PermanentScrapingError("the page structure changed")
    worker, _ = _worker(raises=error)
    failures: list[object] = []
    worker.failed.connect(failures.append)

    worker.search(2026)

    assert drain(lambda: len(failures) == 1)
    assert failures[0] is error


def test_a_failure_carries_the_exception_rather_than_a_sentence(
    drain: Drain,
) -> None:
    """The message is English and goes to the log. What the user reads is the
    window's decision."""
    worker, _ = _worker(raises=PermanentScrapingError("the page structure changed"))
    failures: list[object] = []
    worker.failed.connect(failures.append)

    worker.search(2026)

    assert drain(lambda: len(failures) == 1)
    assert isinstance(failures[0], PermanentScrapingError)


def test_a_failed_run_does_not_emit_a_result(drain: Drain) -> None:
    worker, _ = _worker(raises=PermanentScrapingError("nope"))
    results: list[object] = []
    failures: list[object] = []
    worker.searched.connect(results.append)
    worker.failed.connect(failures.append)

    worker.search(2026)

    assert drain(lambda: len(failures) == 1)
    assert results == []


def test_a_failure_leaves_the_worker_usable(drain: Drain) -> None:
    """A run that could not be completed is normal: the site goes down, a
    postback times out. The window has to be able to try again."""
    worker, _ = _worker(raises=PermanentScrapingError("nope"))
    failures: list[object] = []
    worker.failed.connect(failures.append)

    worker.search(2026)

    assert drain(lambda: len(failures) == 1)
    assert worker.is_running is False
    assert worker.wait(timeout=5) is True


# ── One at a time ─────────────────────────────────────────────────────────────
def test_nothing_is_running_to_begin_with() -> None:
    worker, _ = _worker()

    assert worker.is_running is False


def test_a_run_in_progress_is_visible() -> None:
    """What a window reads to decide whether to disable its buttons."""
    gate = threading.Event()
    worker, _ = _worker(gate=gate)

    worker.search(2026)

    try:
        assert worker.is_running is True
    finally:
        gate.set()
        worker.wait(timeout=5)


def test_a_second_run_is_refused_while_one_is_going() -> None:
    """Refused rather than ignored. A window is expected to prevent this, and
    silently dropping the request would leave the first run's result arriving
    against a window that believes it asked for the second."""
    gate = threading.Event()
    worker, _ = _worker(gate=gate)

    worker.search(2026)

    try:
        with pytest.raises(RuntimeError, match="already in progress"):
            worker.search(2026)
    finally:
        gate.set()
        worker.wait(timeout=5)


def test_a_refresh_is_refused_during_a_search() -> None:
    """The guard is about the thread, not about which operation it was."""
    gate = threading.Event()
    worker, _ = _worker(gate=gate)

    worker.search(2026)

    try:
        with pytest.raises(RuntimeError, match="already in progress"):
            worker.refresh()
    finally:
        gate.set()
        worker.wait(timeout=5)


def test_the_worker_is_free_before_anything_is_emitted() -> None:
    """Found by this suite failing only when run with its neighbours.

    A direct connection rather than the queued one a window would use, on
    purpose: it runs the slot inside emit, on the worker thread, so the thread is
    certainly still alive while the assertion runs. Through a queued connection
    the thread has usually exited by then, which is what made the original
    failure look intermittent.

    A worker that answered is_running from whether its thread was alive would
    report a run in progress when all that remained of it was the delivery, and
    the obvious thing for a window to do with a result is decide what to run
    next.
    """
    worker, _ = _worker()
    busy: list[bool] = []
    worker.searched.connect(
        lambda _r: busy.append(worker.is_running),
        Qt.ConnectionType.DirectConnection,
    )

    worker.search(2026)
    worker.wait(timeout=5)

    assert busy == [False]


def test_a_slot_can_start_the_next_run(drain: Drain) -> None:
    """What the flag buys. A window that chains one operation onto another, or a
    user who clicks again the moment results appear, must not be refused."""
    worker, session = _worker()
    second: list[object] = []

    def _on_result(_result: object) -> None:
        if not second:
            second.append("asked")
            worker.refresh()

    worker.searched.connect(_on_result)
    worker.search(2026)

    assert drain(lambda: session.vacancy_calls == [(None, True)])


def test_another_run_is_allowed_once_the_first_is_done(drain: Drain) -> None:
    worker, session = _worker()
    done: list[object] = []
    worker.searched.connect(done.append)

    worker.search(2026)
    assert drain(lambda: len(done) == 1)

    worker.refresh()

    assert drain(lambda: session.vacancy_calls == [(None, True)])


# ── Waiting ───────────────────────────────────────────────────────────────────
def test_waiting_on_nothing_returns_at_once() -> None:
    worker, _ = _worker()

    assert worker.wait(timeout=0) is True


def test_waiting_reports_a_run_that_has_not_finished() -> None:
    """What lets a window decide whether to close now or ask."""
    gate = threading.Event()
    worker, _ = _worker(gate=gate)

    worker.search(2026)

    try:
        assert worker.wait(timeout=0.05) is False
    finally:
        gate.set()
        worker.wait(timeout=5)


def test_waiting_returns_once_the_run_ends() -> None:
    gate = threading.Event()
    worker, _ = _worker(gate=gate)

    worker.search(2026)
    gate.set()

    assert worker.wait(timeout=5) is True
    assert worker.is_running is False
