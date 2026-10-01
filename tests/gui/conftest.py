"""An event loop for the Qt tests, and a way to let it run.

QCoreApplication rather than QApplication: nothing under test here draws, so
there is no need for a platform plugin, a display, or the system graphics
libraries one would pull in. Qt allows one application object per process, so it
is session scoped.
"""

import time
from collections.abc import Callable, Iterator

import pytest
from PySide6.QtCore import QCoreApplication


@pytest.fixture(scope="session")
def qt_app() -> Iterator[QCoreApplication]:
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture
def drain(qt_app: QCoreApplication) -> Callable[..., bool]:
    """Run the event loop until a condition holds, or give up.

    A queued signal is delivered by the receiving thread's event loop, which in
    a test is only running while something spins it. Waiting on a condition
    rather than sleeping a fixed time keeps the suite from being slow when it
    passes and flaky when the machine is busy.
    """

    def _drain(until: Callable[[], bool], *, timeout_ms: int = 2000) -> bool:
        deadline = time.monotonic() + timeout_ms / 1000

        while time.monotonic() < deadline:
            qt_app.processEvents()

            if until():
                return True

            time.sleep(0.001)

        return until()

    return _drain
