"""Getting from an exported workbook to the file itself.

Two ways in. Right after an export the window asks whether to open the file or
show it in its folder, and a button opens the export folder at any time. Both
end in gui/desktop.py, which is replaced here by recorders: what is tested is
which of its functions the window calls, with what, and what it says when the
system refuses.

The worker double and the result builders are the ones test_window.py uses, so
the window here is built exactly as it is there.
"""

from pathlib import Path

import pytest

from consulta_vacantes_mep.exports import excel as excel_module
from consulta_vacantes_mep.gui import desktop
from consulta_vacantes_mep.gui import window as window_module
from consulta_vacantes_mep.gui.reporter import QtReporter
from consulta_vacantes_mep.gui.window import OPEN_FOLDER_LABEL, AfterExport, MainWindow
from tests.gui.test_window import FakeWorker, _emit, _result, _worker

Calls = list[tuple[str, Path]]


@pytest.fixture
def window() -> MainWindow:
    return MainWindow(FakeWorker(), QtReporter())  # type: ignore[arg-type]


@pytest.fixture
def outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Where workbooks are written, and the folder the button should open."""
    folder = tmp_path / "Consulta Vacantes MEP"
    monkeypatch.setattr(excel_module, "OUTPUT_DIR", folder)
    return folder


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> Calls:
    """Record every request to the desktop, all of them succeeding."""
    calls: Calls = []

    def _recorder(name: str) -> object:
        def _record(path: Path) -> bool:
            calls.append((name, path))
            return True

        return _record

    for name in ("open_path", "open_folder", "show_in_folder"):
        monkeypatch.setattr(desktop, name, _recorder(name))

    return calls


def _answer(monkeypatch: pytest.MonkeyPatch, choice: AfterExport) -> list[Path]:
    """Make the dialog answer with choice, and record what it was asked about."""
    asked: list[Path] = []

    def _ask(_parent: object, path: Path) -> AfterExport:
        asked.append(path)
        return choice

    monkeypatch.setattr(window_module, "_ask_after_export", _ask)
    return asked


def _export(window: MainWindow) -> None:
    _emit(_worker(window).searched, _result(found=["1548582"]))
    window.export_button.click()


def _written(outputs: Path) -> Path:
    files = sorted(outputs.glob("*.xlsx"))
    assert len(files) == 1, f"expected one workbook, found {len(files)}"
    return files[0]


# ── The button ────────────────────────────────────────────────────────────────
def test_the_button_says_what_it_opens(window: MainWindow) -> None:
    assert window.open_folder_button.text() == OPEN_FOLDER_LABEL


def test_the_button_is_usable_before_anything_was_exported(window: MainWindow) -> None:
    """A file from another day is a reason to open the folder on startup."""
    assert window.open_folder_button.isEnabled() is True


def test_the_button_stays_usable_during_a_run(window: MainWindow) -> None:
    window.search_button.click()

    assert window.open_folder_button.isEnabled() is True


def test_the_button_opens_the_folder_exports_go_to(
    window: MainWindow, outputs: Path, opened: Calls
) -> None:
    window.open_folder_button.click()

    assert opened == [("open_folder", outputs)]


def test_a_folder_that_will_not_open_is_explained(
    window: MainWindow, outputs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the path, so the user can still get there by hand."""
    monkeypatch.setattr(desktop, "open_folder", lambda _folder: False)

    window.open_folder_button.click()

    message = window.statusBar().currentMessage()

    assert "No se pudo abrir la carpeta" in message
    assert str(outputs) in message


# ── After an export ───────────────────────────────────────────────────────────
def test_an_export_asks_about_the_file_it_wrote(
    window: MainWindow, outputs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = _answer(monkeypatch, AfterExport.NOTHING)

    _export(window)

    assert asked == [_written(outputs)]


def test_choosing_to_open_opens_the_file(
    window: MainWindow, outputs: Path, opened: Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answer(monkeypatch, AfterExport.OPEN_FILE)

    _export(window)

    assert opened == [("open_path", _written(outputs))]


def test_choosing_to_show_shows_it_in_its_folder(
    window: MainWindow, outputs: Path, opened: Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answer(monkeypatch, AfterExport.SHOW_IN_FOLDER)

    _export(window)

    assert opened == [("show_in_folder", _written(outputs))]


@pytest.mark.usefixtures("outputs")
def test_closing_the_dialog_opens_nothing(
    window: MainWindow, opened: Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answer(monkeypatch, AfterExport.NOTHING)

    _export(window)

    assert opened == []


def test_closing_the_dialog_leaves_the_path_on_screen(
    window: MainWindow, outputs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The status bar keeps saying where the file went, as it did before."""
    _answer(monkeypatch, AfterExport.NOTHING)

    _export(window)

    assert str(_written(outputs)) in window.statusBar().currentMessage()


def test_a_file_that_will_not_open_is_explained(
    window: MainWindow, outputs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answer(monkeypatch, AfterExport.OPEN_FILE)
    monkeypatch.setattr(desktop, "open_path", lambda _path: False)

    _export(window)

    message = window.statusBar().currentMessage()

    assert "No se pudo abrir" in message
    assert str(_written(outputs)) in message


def test_a_failed_export_asks_nothing(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """There is no file to offer, and the failure message has to stay up."""
    asked = _answer(monkeypatch, AfterExport.OPEN_FILE)

    def _locked(*_args: object, **_kwargs: object) -> None:
        message = "[Errno 13] Permission denied"
        raise PermissionError(message)

    monkeypatch.setattr(window_module, "export_data_to_excel", _locked)

    _export(window)

    assert asked == []
