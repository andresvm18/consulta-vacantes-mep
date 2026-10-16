"""Getting from a double click to a window on screen.

The dialogs are replaced throughout. A modal QMessageBox under the offscreen
platform waits for a click that never arrives, and what is worth checking is
which message was chosen and when, not that Qt can draw a box.
"""

import pytest

from consulta_vacantes_mep.app import startup
from consulta_vacantes_mep.gui import entry as entry_module
from consulta_vacantes_mep.gui.entry import (
    CHROMIUM_MESSAGES,
    DOWNLOAD_MESSAGE,
    build_window,
    main,
    prepare_browser,
)
from consulta_vacantes_mep.gui.window import MainWindow
from consulta_vacantes_mep.utils.playwright_setup import ChromiumCheck, ChromiumStatus

Said = list[tuple[str, str]]


@pytest.fixture
def dialogs(monkeypatch: pytest.MonkeyPatch) -> tuple[Said, Said]:
    """What would have been shown, in the order it would have been shown."""
    told: Said = []
    complaints: Said = []

    monkeypatch.setattr(
        entry_module, "_tell", lambda title, text: told.append((title, text))
    )
    monkeypatch.setattr(
        entry_module, "_complain", lambda title, text: complaints.append((title, text))
    )

    return told, complaints


def _outcome(
    monkeypatch: pytest.MonkeyPatch, check: ChromiumCheck, *, present: bool = True
) -> list[str]:
    """Replace the startup sequence's two halves, recording the install."""
    installs: list[str] = []

    def _install() -> ChromiumCheck:
        installs.append("install")
        return check

    monkeypatch.setattr(startup, "chromium_is_available", lambda: present)
    monkeypatch.setattr(startup, "install_chromium", _install)

    return installs


# ── A browser that is ready ───────────────────────────────────────────────────
@pytest.mark.usefixtures("dialogs")
def test_a_ready_browser_lets_the_window_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _outcome(monkeypatch, ChromiumCheck(ChromiumStatus.INSTALLED))

    assert prepare_browser() is True


def test_a_ready_browser_is_not_worth_a_dialog(
    monkeypatch: pytest.MonkeyPatch, dialogs: tuple[Said, Said]
) -> None:
    """The common case shows nothing at all before the window appears."""
    told, complaints = dialogs
    _outcome(monkeypatch, ChromiumCheck(ChromiumStatus.INSTALLED))

    prepare_browser()

    assert told == []
    assert complaints == []


# ── A browser that has to be downloaded ───────────────────────────────────────
def test_a_download_is_announced_before_it_starts(
    monkeypatch: pytest.MonkeyPatch, dialogs: tuple[Said, Said]
) -> None:
    """A minute of nothing happening, with no window up yet to explain itself.
    The dialog is the only chance to say so, and it has to come first."""
    told, _ = dialogs
    installs = _outcome(
        monkeypatch, ChromiumCheck(ChromiumStatus.INSTALLED), present=False
    )

    def _record(title: str, text: str) -> None:
        told.append((title, text))
        installs.append("told")

    monkeypatch.setattr(entry_module, "_tell", _record)

    prepare_browser()

    assert installs == ["told", "install"]


def test_the_download_dialog_says_it_will_take_a_while(
    monkeypatch: pytest.MonkeyPatch, dialogs: tuple[Said, Said]
) -> None:
    told, _ = dialogs
    _outcome(monkeypatch, ChromiumCheck(ChromiumStatus.INSTALLED), present=False)

    prepare_browser()

    assert told == [(entry_module.DOWNLOAD_TITLE, DOWNLOAD_MESSAGE)]
    assert "un minuto" in DOWNLOAD_MESSAGE


# ── A browser that cannot be had ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "status", [ChromiumStatus.NOT_INSTALLABLE, ChromiumStatus.FAILED]
)
@pytest.mark.usefixtures("dialogs")
def test_a_browser_that_cannot_be_readied_stops_the_window(
    status: ChromiumStatus, monkeypatch: pytest.MonkeyPatch
) -> None:
    _outcome(monkeypatch, ChromiumCheck(status), present=False)

    assert prepare_browser() is False


@pytest.mark.parametrize(
    "status", [ChromiumStatus.NOT_INSTALLABLE, ChromiumStatus.FAILED]
)
def test_every_failing_status_has_something_to_say(
    status: ChromiumStatus, monkeypatch: pytest.MonkeyPatch, dialogs: tuple[Said, Said]
) -> None:
    """CHROMIUM_MESSAGES is indexed by status, so a value added to the enum
    without a message is a KeyError in the one path that runs before the window
    exists to report it."""
    _, complaints = dialogs
    _outcome(monkeypatch, ChromiumCheck(status), present=False)

    prepare_browser()

    assert complaints == [(entry_module.FAILURE_TITLE, CHROMIUM_MESSAGES[status])]


def test_the_english_detail_does_not_reach_the_dialog(
    monkeypatch: pytest.MonkeyPatch, dialogs: tuple[Said, Said]
) -> None:
    """It is in the log, with its traceback."""
    _, complaints = dialogs
    _outcome(
        monkeypatch,
        ChromiumCheck(ChromiumStatus.FAILED, "connection refused"),
        present=False,
    )

    prepare_browser()

    assert "connection refused" not in complaints[0][1]


# ── Assembling the window ─────────────────────────────────────────────────────
def test_a_window_is_built() -> None:
    assert isinstance(build_window(), MainWindow)


def test_the_window_is_wired_to_a_worker() -> None:
    """Built here rather than by the window, which takes what it is given so a
    test can hand it a double."""
    window = build_window()

    assert window.search_button.isEnabled() is True
    assert window.export_button.isEnabled() is False


# ── The glue ──────────────────────────────────────────────────────────────────
def test_a_missing_browser_means_no_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """And a non-zero exit, so a script that launched it can tell."""
    monkeypatch.setattr(entry_module, "prepare_browser", lambda: False)
    built: list[str] = []

    def _never() -> MainWindow:
        built.append("built")
        message = "the window was built with no browser to drive it"
        raise AssertionError(message)

    monkeypatch.setattr(entry_module, "build_window", _never)

    assert main() == 1
    assert built == []
