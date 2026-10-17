"""Handing files and folders to the system.

Neither Qt nor Explorer is really asked: the first is replaced by a recorder and
the second by a fake Popen, so a test run never opens a window on the machine
running it. What is checked is what each would have been asked, and that a
refusal comes back as False instead of an exception.

Kept outside tests/gui, whose conftest replaces these very functions for the
window's tests.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl

from consulta_vacantes_mep.gui import desktop


@pytest.fixture
def urls(monkeypatch: pytest.MonkeyPatch) -> list[QUrl]:
    """What Qt was asked to open, each request succeeding."""
    asked: list[QUrl] = []

    def _open(url: QUrl) -> bool:
        asked.append(url)
        return True

    monkeypatch.setattr(desktop, "_open_url", _open)
    return asked


def test_a_path_is_handed_to_qt_as_a_local_file(urls: list[QUrl], tmp_path: Path) -> None:
    target = tmp_path / "vacantes.xlsx"

    assert desktop.open_path(target) is True
    assert [Path(url.toLocalFile()) for url in urls] == [target]


def test_a_refusal_comes_back_as_false(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(desktop, "_open_url", lambda _url: False)

    assert desktop.open_path(tmp_path) is False


def test_a_folder_that_does_not_exist_yet_is_created(
    urls: list[QUrl], tmp_path: Path
) -> None:
    """The button is there before the first export, when the folder is not."""
    folder = tmp_path / "Documentos" / "Consulta Vacantes MEP"

    assert desktop.open_folder(folder) is True
    assert folder.is_dir()
    assert [Path(url.toLocalFile()) for url in urls] == [folder]


def test_a_folder_that_cannot_be_created_comes_back_as_false(
    urls: list[QUrl], tmp_path: Path
) -> None:
    """A file where the folder should be is the simplest way to make it fail."""
    blocker = tmp_path / "Consulta Vacantes MEP"
    blocker.write_text("not a folder", encoding="utf-8")

    assert desktop.open_folder(blocker / "inside") is False
    assert urls == []


@pytest.mark.skipif(sys.platform != "win32", reason="Explorer is Windows only")
def test_on_windows_explorer_is_asked_to_select_the_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(subprocess, "Popen", commands.append)

    target = tmp_path / "con espacios" / "vacantes.xlsx"

    assert desktop.show_in_folder(target) is True
    assert commands == [[str(desktop._explorer()), "/select,", str(target)]]


@pytest.mark.skipif(sys.platform != "win32", reason="Explorer is Windows only")
def test_explorer_that_will_not_start_comes_back_as_false(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _broken(_command: list[str]) -> None:
        message = "explorer.exe not found"
        raise OSError(message)

    monkeypatch.setattr(subprocess, "Popen", _broken)

    assert desktop.show_in_folder(tmp_path / "vacantes.xlsx") is False


@pytest.mark.skipif(sys.platform == "win32", reason="the fallback off Windows")
def test_elsewhere_the_folder_is_opened_instead(urls: list[QUrl], tmp_path: Path) -> None:
    target = tmp_path / "vacantes.xlsx"

    assert desktop.show_in_folder(target) is True
    assert [Path(url.toLocalFile()) for url in urls] == [tmp_path]
