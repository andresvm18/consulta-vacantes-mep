"""An application object for the Qt tests, and a way to let its loop run.

QApplication rather than QCoreApplication. Several of these tests build the
window, and a QWidget created without a QApplication aborts the interpreter
instead of raising, so the whole run dies on the first one with nothing but a
C++ backtrace to show for it.

The fixture is session scoped and autouse. Qt allows one application object per
process, and a test that builds a widget should not have to remember to ask for
one: forgetting is not a failure, it is the end of the run.

The platform is offscreen, chosen here rather than in CI, so a developer's
machine and the runner behave the same and no window flashes up during a test.
setdefault, so a developer who wants to watch can still export another value.
It has to be set before QtWidgets is imported anywhere, which is why it sits at
module level above the import.
"""

import os
import time
from collections.abc import Callable, Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qt_app() -> Iterator[QApplication]:
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication([])
    yield app


@pytest.fixture
def drain(qt_app: QApplication) -> Callable[..., bool]:
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
