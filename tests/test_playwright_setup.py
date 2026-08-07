"""Making sure a usable Chromium is present, without installing one.

Nothing here launches a browser or runs an installer. Both are replaced by
doubles, which is the only way to reach the failure paths: on any machine
where the suite runs, Chromium is installed and the interesting branches are
unreachable.

Two of these tests exist for a build that does not exist yet. A frozen
executable with console=False has no stdout on Windows, and a subprocess
writing to it would fail. Those decisions are invisible in normal use and are
exactly what a refactor removes without noticing.
"""

import subprocess
import sys
from types import TracebackType

import pytest

from consulta_vacantes_mep.utils import playwright_setup
from consulta_vacantes_mep.utils.playwright_setup import (
    ChromiumCheck,
    ChromiumStatus,
    chromium_is_available,
    install_chromium,
)


class FakeBrowser:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser, error: Exception | None = None) -> None:
        self._browser = browser
        self._error = error
        self.launches = 0

    def launch(self, _headless: bool = True) -> FakeBrowser:
        self.launches += 1

        if self._error is not None:
            raise self._error

        return self._browser


class FakePlaywright:
    def __init__(self, chromium: FakeChromium) -> None:
        self.chromium = chromium


class FakeSyncPlaywright:
    """Stands in for the context manager sync_playwright() returns."""

    def __init__(self, chromium: FakeChromium) -> None:
        self._playwright = FakePlaywright(chromium)
        self.exited = False

    def __call__(self) -> "FakeSyncPlaywright":
        return self

    def __enter__(self) -> FakePlaywright:
        return self._playwright

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exited = True


class FakeRun:
    """Stands in for subprocess.run and records what it was asked to do."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls = 0
        self.command: list[str] = []
        self.kwargs: dict[str, object] = {}

    def __call__(self, command: list[str], **kwargs: object) -> object:
        self.calls += 1
        self.command = command
        self.kwargs = kwargs

        if self._error is not None:
            raise self._error

        # install_chromium never inspects the result, only whether it raised.
        return object()


def _install_chromium_with(
    monkeypatch: pytest.MonkeyPatch, error: Exception | None = None
) -> FakeRun:
    run = FakeRun(error)
    monkeypatch.setattr(playwright_setup.subprocess, "run", run)
    return run


# ── Checking ──────────────────────────────────────────────────────────────────
def test_a_browser_that_launches_means_chromium_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chromium = FakeChromium(FakeBrowser())
    monkeypatch.setattr(playwright_setup, "sync_playwright", FakeSyncPlaywright(chromium))

    assert chromium_is_available() is True
    assert chromium.launches == 1


def test_the_check_closes_the_browser_it_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The check proves more than reading a path, and costs the same. It must
    not also leave a browser running for the rest of the session."""
    browser = FakeBrowser()
    monkeypatch.setattr(
        playwright_setup, "sync_playwright", FakeSyncPlaywright(FakeChromium(browser))
    )

    chromium_is_available()

    assert browser.closed is True


def test_a_browser_that_will_not_launch_is_reported_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The caller decides what to say about it, so this returns rather than
    raising into an entry point that has nothing to catch it with."""
    chromium = FakeChromium(FakeBrowser(), error=RuntimeError("no executable"))
    monkeypatch.setattr(playwright_setup, "sync_playwright", FakeSyncPlaywright(chromium))

    assert chromium_is_available() is False


# ── Installing ────────────────────────────────────────────────────────────────
def test_a_frozen_build_reports_a_packaging_defect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The executable is expected to ship the browser inside it."""
    # sys has no frozen attribute outside a frozen build, hence raising=False.
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    result = install_chromium()

    assert result.status is ChromiumStatus.NOT_INSTALLABLE
    assert result.ok is False
    assert result.detail


def test_a_frozen_build_downloads_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A download into a temporary extraction directory is lost on restart."""
    run = _install_chromium_with(monkeypatch)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    install_chromium()

    assert run.calls == 0


def test_a_successful_download_reports_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_chromium_with(monkeypatch)

    result = install_chromium()

    assert result.status is ChromiumStatus.INSTALLED
    assert result.ok is True


def test_a_failed_download_keeps_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The detail is English and goes to the log; the caller writes the Spanish."""
    error = subprocess.CalledProcessError(
        returncode=1, cmd=["playwright"], stderr="connection refused"
    )
    _install_chromium_with(monkeypatch, error)

    result = install_chromium()

    assert result.status is ChromiumStatus.FAILED
    assert result.detail is not None
    assert "connection refused" in result.detail


def test_an_unexpected_failure_is_still_reported_as_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing interpreter raises OSError, not CalledProcessError."""
    _install_chromium_with(monkeypatch, OSError("no such file"))

    result = install_chromium()

    assert result.status is ChromiumStatus.FAILED
    assert result.detail is not None
    assert "no such file" in result.detail


def test_the_installer_runs_under_the_running_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anything else would install the browser into a different environment."""
    run = _install_chromium_with(monkeypatch)

    install_chromium()

    assert run.command[0] == sys.executable
    assert run.command[-1] == "chromium"
    assert run.kwargs["check"] is True


def test_the_installer_writes_to_no_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A windowed build has no stdout on Windows, and a subprocess inheriting
    it would fail on the first line the installer prints. Captured output goes
    to the log instead."""
    run = _install_chromium_with(monkeypatch)

    install_chromium()

    assert run.kwargs["capture_output"] is True


def test_the_installer_flashes_no_console_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compared against the module constant rather than the Windows value: it
    is zero elsewhere, and a literal would pass locally and fail on CI."""
    run = _install_chromium_with(monkeypatch)

    install_chromium()

    assert run.kwargs["creationflags"] == playwright_setup._NO_WINDOW


# ── The result ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ChromiumStatus.INSTALLED, True),
        (ChromiumStatus.NOT_INSTALLABLE, False),
        (ChromiumStatus.FAILED, False),
    ],
)
def test_only_an_installed_check_is_ok(
    status: ChromiumStatus, expected: bool
) -> None:
    assert ChromiumCheck(status).ok is expected
