"""Where the application writes, from source and from the installed build.

The rule is easy to break in a way no other test notices: a frozen build that
fell back to writing beside itself would put the user's workbooks in a hidden
folder under AppData, and everything would still pass.

The functions read their inputs when called, so each case sets them and asks.
The module constants are left alone; other tests point those at temporary
directories themselves.
"""

import sys
from pathlib import Path

import pytest

from consulta_vacantes_mep.utils import paths
from consulta_vacantes_mep.utils.paths import (
    APP_NAME,
    documents_dir,
    get_log_dir,
    get_output_dir,
    local_app_data_dir,
)


@pytest.fixture
def from_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A frozen build, with AppData and Documents somewhere harmless."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.setattr(paths, "_windows_documents", lambda: tmp_path / "Documentos")
    return tmp_path


# ── Run from source ───────────────────────────────────────────────────────────
def test_from_source_logs_go_under_the_working_directory(from_source: Path) -> None:
    assert get_log_dir() == from_source / "logs"


def test_from_source_workbooks_go_under_the_working_directory(from_source: Path) -> None:
    assert get_output_dir() == from_source / "outputs"


# ── The installed build ───────────────────────────────────────────────────────
def test_installed_workbooks_go_to_documents(installed: Path) -> None:
    """The user's own files, somewhere the user looks."""
    assert get_output_dir() == installed / "Documentos" / APP_NAME


def test_installed_logs_go_to_app_data(installed: Path) -> None:
    assert get_log_dir() == installed / "AppData" / "Local" / APP_NAME / "logs"


def test_installed_never_writes_beside_the_executable(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What it used to do. Installed, beside the executable is a folder in
    AppData nobody opens, and one that may not be writable at all."""
    executable_folder = installed / "Programs" / APP_NAME
    monkeypatch.setattr(sys, "executable", str(executable_folder / "app.exe"))

    assert executable_folder not in get_output_dir().parents
    assert executable_folder not in get_log_dir().parents


# ── Finding the folders ───────────────────────────────────────────────────────
def test_documents_falls_back_to_the_home_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Windows cannot say, or this is not Windows."""
    monkeypatch.setattr(paths, "_windows_documents", lambda: None)

    assert documents_dir() == Path.home() / "Documents"


def test_app_data_falls_back_when_the_variable_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert local_app_data_dir() == Path.home() / "AppData" / "Local"


@pytest.mark.skipif(sys.platform != "win32", reason="asks the Windows shell")
def test_windows_knows_where_documents_is() -> None:
    """The real call, on the platform that has it. A folder that exists is the
    whole check: whether it is redirected to OneDrive depends on the machine."""
    found = paths._windows_documents()

    assert found is not None
    assert found.is_dir()


def test_elsewhere_windows_is_not_asked() -> None:
    if sys.platform == "win32":
        pytest.skip("only meaningful off Windows")

    assert paths._windows_documents() is None
