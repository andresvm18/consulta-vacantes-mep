"""The sequence that gets a browser ready, without the console it used to print to.

The interesting guarantee is ordering. The download takes about a minute, so an
interface has to be able to say so before it starts, and a sequence that called
back afterwards would be useless in exactly the case it exists for.
"""

import pytest

from consulta_vacantes_mep.app import startup
from consulta_vacantes_mep.app.startup import ensure_chromium
from consulta_vacantes_mep.utils.playwright_setup import ChromiumCheck, ChromiumStatus


def _present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(startup, "chromium_is_available", lambda: True)


def _missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(startup, "chromium_is_available", lambda: False)


def _installs(monkeypatch: pytest.MonkeyPatch, check: ChromiumCheck) -> list[str]:
    """Replace the installer, recording that it ran."""
    calls: list[str] = []

    def _install() -> ChromiumCheck:
        calls.append("install")
        return check

    monkeypatch.setattr(startup, "install_chromium", _install)
    return calls


# ── A browser that is already there ───────────────────────────────────────────
def test_an_available_browser_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    _present(monkeypatch)
    _installs(monkeypatch, ChromiumCheck(ChromiumStatus.FAILED))

    assert ensure_chromium().ok is True


def test_an_available_browser_is_not_downloaded_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _present(monkeypatch)
    calls = _installs(monkeypatch, ChromiumCheck(ChromiumStatus.INSTALLED))

    ensure_chromium()

    assert calls == []


def test_nothing_is_announced_when_there_is_nothing_to_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A message about a download that never happens is worse than silence."""
    _present(monkeypatch)
    announced: list[str] = []

    ensure_chromium(before_install=lambda: announced.append("announced"))

    assert announced == []


# ── A browser that has to be downloaded ───────────────────────────────────────
def test_a_missing_browser_is_downloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    _missing(monkeypatch)
    calls = _installs(monkeypatch, ChromiumCheck(ChromiumStatus.INSTALLED))

    assert ensure_chromium().ok is True
    assert calls == ["install"]


def test_the_download_is_announced_before_it_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole reason this is a callback. A minute of apparent silence is what
    an interface has to be able to avoid, and it cannot once the download is
    over.
    """
    _missing(monkeypatch)
    order: list[str] = []

    def _install() -> ChromiumCheck:
        order.append("install")
        return ChromiumCheck(ChromiumStatus.INSTALLED)

    monkeypatch.setattr(startup, "install_chromium", _install)

    ensure_chromium(before_install=lambda: order.append("announce"))

    assert order == ["announce", "install"]


def test_the_announcement_happens_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _missing(monkeypatch)
    _installs(monkeypatch, ChromiumCheck(ChromiumStatus.INSTALLED))
    announced: list[str] = []

    ensure_chromium(before_install=lambda: announced.append("announced"))

    assert announced == ["announced"]


def test_a_caller_that_says_nothing_still_gets_a_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A script or a test has nowhere to announce it to."""
    _missing(monkeypatch)
    calls = _installs(monkeypatch, ChromiumCheck(ChromiumStatus.INSTALLED))

    assert ensure_chromium().ok is True
    assert calls == ["install"]


# ── A download that does not work ─────────────────────────────────────────────
@pytest.mark.parametrize(
    "status", [ChromiumStatus.NOT_INSTALLABLE, ChromiumStatus.FAILED]
)
def test_a_failed_download_is_reported_as_it_came(
    status: ChromiumStatus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason is passed through rather than flattened into a boolean: the
    interface needs it to say something useful."""
    _missing(monkeypatch)
    _installs(monkeypatch, ChromiumCheck(status, "connection refused"))

    result = ensure_chromium()

    assert result.ok is False
    assert result.status is status
    assert result.detail == "connection refused"
