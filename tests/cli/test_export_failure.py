"""What the terminal says when the workbook could not be written.

The search succeeded and its results were shown; only the file failed. Excel
locks a workbook it has open, and a second export in the same minute writes to
the same name, so this is something a user does without trying.

Kept apart from test_entry.py and test_failures.py: one fakes a session that
always succeeds with no way to make the export fail, the other a session that
never gets as far as exporting.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from consulta_vacantes_mep.app.session import SearchResult
from consulta_vacantes_mep.cli import entry as entry_module
from consulta_vacantes_mep.cli.entry import EXPORT_FAILURE_MESSAGE, app
from consulta_vacantes_mep.models import Vacancy
from tests.rendering import visible

VACANCY = Vacancy(
    number="1531185",
    regional_office="Dirección Regional de Prueba",
    position_class="Profesor de Enseñanza Media",
    specialty="Francés",
    institution="Liceo de Prueba",
    lessons="10",
    starts_on="05/08/2026",
    ends_on="31/12/2026",
)


class WorkingSession:
    """A session that finds one vacancy and nobody appointed to it."""

    def __init__(self, **_: object) -> None:
        pass

    def vacancies(self, *_args: object, **_kwargs: object) -> list[Vacancy]:
        return [VACANCY]

    def search(self, *_args: object, **_kwargs: object) -> SearchResult:
        return SearchResult(vacancies=[VACANCY], queries=[])


@pytest.fixture(autouse=True)
def locked_workbook(monkeypatch: pytest.MonkeyPatch) -> None:
    """A session that works, and a workbook Excel is holding open."""
    monkeypatch.setattr(entry_module, "Session", WorkingSession)

    def _locked(*_args: object, **_kwargs: object) -> Path:
        message = "[Errno 13] Permission denied: 'outputs/todas_las_vacantes.xlsx'"
        raise PermissionError(message)

    monkeypatch.setattr(entry_module, "export_data_to_excel", _locked)


def _run(runner: CliRunner, command: str) -> Result:
    return runner.invoke(app, [command, "--exportar"])


@pytest.mark.parametrize("command", ["buscar", "vacantes"])
def test_a_locked_workbook_is_explained_in_spanish(runner: CliRunner, command: str) -> None:
    result = _run(runner, command)

    assert "No se pudo escribir el archivo" in visible(result.output)


@pytest.mark.parametrize("command", ["buscar", "vacantes"])
def test_the_advice_is_the_one_the_window_gives(runner: CliRunner, command: str) -> None:
    """Closing the file in Excel is what fixes it, and the user has to be told.
    Checked as a whole sentence through the constant, since Rich wraps lines."""
    result = _run(runner, command)

    written = " ".join(visible(result.output).split())

    assert " ".join(EXPORT_FAILURE_MESSAGE.split()) in written


@pytest.mark.parametrize("command", ["buscar", "vacantes"])
def test_a_locked_workbook_ends_with_a_failing_exit_code(
    runner: CliRunner, command: str
) -> None:
    """The user asked for a file and did not get one; a script has to know."""
    result = _run(runner, command)

    assert result.exit_code == 1


@pytest.mark.parametrize("command", ["buscar", "vacantes"])
def test_the_error_does_not_escape_as_a_traceback(runner: CliRunner, command: str) -> None:
    result = _run(runner, command)

    assert not isinstance(result.exception, PermissionError)


def test_the_results_are_still_shown(runner: CliRunner) -> None:
    """The search worked. Losing the file should not lose what was found."""
    result = _run(runner, "vacantes")

    assert "1531185" in visible(result.output)
