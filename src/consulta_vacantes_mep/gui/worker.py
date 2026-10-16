"""Running a search without freezing the window.

A full run takes about half a minute. Calling Session.search from the thread
that draws the window would stop it repainting for that whole time, which on
Windows means the title bar greys out and the system offers to kill the
application.

So the call happens on a thread of its own and its result comes back as a
signal, which Qt delivers on the thread that connected to it. The same crossing
the reporter uses, for the same reason.

The worker knows nothing about progress. The reporter lives inside the Session
it was given, so what reaches the window during a run and what reaches it at the
end arrive by separate paths that neither has to know about.

Nothing here can cancel a run. The scrapers have no point at which they ask
whether they should stop, so a cancel would amount to abandoning a thread with a
browser open in it. What a window does when it is closed mid-run is a decision
for the window, and wait() is what it has to make that decision with.
"""

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, SignalInstance

from consulta_vacantes_mep.app.session import Session
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)

# What one operation produces: the signal that should carry it, and what it
# carries. Pairing them keeps _run from having to know which operation ran.
Outcome = tuple[SignalInstance, object]
Work = Callable[[], Outcome]


class _Signals(QObject):
    """The signals, in the one object that has to be a QObject.

    SearchWorker is not a QObject for the same reason QtReporter is not: see
    gui/reporter.py. Here there is no name collision, but a worker that was half
    a QObject and half not would be the harder thing to reason about.
    """

    searched = Signal(object)
    refreshed = Signal(int)
    failed = Signal(object)


class SearchWorker:
    """Runs one operation at a time against a Session, off the caller's thread.

    The Session is held rather than built, and held for the life of the worker,
    because the vacancy cache lives in it. That is what makes a second search
    cheap and what gives refreshing a meaning.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._signals = _Signals()
        self._thread: threading.Thread | None = None
        self._running = False

    # ── What a window connects to ────────────────────────────────────────────
    @property
    def searched(self) -> SignalInstance:
        """Carries the SearchResult a finished search produced."""
        return self._signals.searched

    @property
    def refreshed(self) -> SignalInstance:
        """Carries how many vacancies are cached after a refresh."""
        return self._signals.refreshed

    @property
    def failed(self) -> SignalInstance:
        """Carries the exception that ended a run.

        The exception, not a sentence. Its message is English and belongs in the
        log; what the user reads is the window's decision, the same split the
        Chromium check makes.
        """
        return self._signals.failed

    # ── State ────────────────────────────────────────────────────────────────
    @property
    def is_running(self) -> bool:
        """Whether this worker considers itself busy.

        A flag rather than whether the thread is alive. The thread is still
        alive while it emits the result, so a window acting on that result would
        be told a run was in progress when the only thing left of it was the
        delivery. The flag is cleared before anything is emitted, which is what
        lets a slot start the next run.

        Written by the worker thread and read by the window's; a bool assignment
        needs no lock to be seen whole.
        """
        return self._running

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the current run ends. True if nothing is running after.

        For a window deciding what to do about a run still going when it is
        closed. A timeout of None waits as long as it takes.
        """
        if self._thread is not None:
            self._thread.join(timeout)

        return not self.is_running

    # ── What a window asks for ───────────────────────────────────────────────
    def search(self, year: int, specialty: str | None = None) -> None:
        """Look up the vacancies and the appointments made against them.

        An empty specialty means every vacancy, which is the only thing the two
        search options differ on.
        """

        def _work() -> Outcome:
            return self._signals.searched, self._session.search(year, specialty)

        self._start(_work)

    def refresh(self) -> None:
        """Scrape the vacancies again, without querying appointments."""

        def _work() -> Outcome:
            return self._signals.refreshed, len(self._session.vacancies(refresh=True))

        self._start(_work)

    # ── The thread ───────────────────────────────────────────────────────────
    def _start(self, work: Work) -> None:
        """Run work on a thread, refusing to run two at once.

        Raising rather than ignoring: a window is expected to disable whatever
        starts a run while one is going, and a second request means that did not
        happen. Swallowing it would leave the first run's result arriving against
        a window that believes it is showing the second.
        """
        if self.is_running:
            message = "a run is already in progress"
            raise RuntimeError(message)

        self._running = True
        self._thread = threading.Thread(target=self._run, args=(work,), name="search")
        self._thread.start()

    def _run(self, work: Work) -> None:
        """Carry out one operation, then say what came of it.

        The two halves are separate so that the worker is no longer busy by the
        time anything hears about the result. Emitting first would hand a window
        a result while still answering yes to is_running, and the obvious thing
        to do with a result is decide what to run next.

        The catch is broad on purpose. An exception that escaped here would end
        the thread with nothing said, and a window would wait for a result that
        is never coming.
        """
        signal: SignalInstance
        payload: object

        try:
            signal, payload = work()
        except Exception as error:
            logger.exception("The run did not finish")
            signal, payload = self._signals.failed, error

        self._running = False
        signal.emit(payload)
