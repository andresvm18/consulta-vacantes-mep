"""What the terminal says when the site could not be read.

Kept apart from test_entry.py, whose session double always succeeds and is
installed for every test there. Here it always fails.

The case that matters is the one the terminal used to get wrong: a run that
never reached the site printed the same line as a site with nothing published,
so the user was told there were no vacancies.
"""

import pytest
from typer.testing import CliRunner, Result

from consulta_vacantes_mep.app.session import SearchResult
from consulta_vacantes_mep.cli import entry as entry_module
from consulta_vacantes_mep.cli.entry import NO_VACANCIES_MESSAGE, app
from consulta_vacantes_mep.exceptions import TransientScrapingError
from consulta_vacantes_mep.models import Vacancy
from tests.rendering import visible

# The English detail carried by the exception. It belongs in the log.
DETAIL = "vacancies page: timed out"


class FailingSession:
    """A session whose every request fails the way the live run did."""

    def __init__(self, **_: object) -> None:
        pass

    def vacancies(self, *_args: object, **_kwargs: object) -> list[Vacancy]:
        raise TransientScrapingError(DETAIL)

    def search(self, *_args: object, **_kwargs: object) -> SearchResult:
        raise TransientScrapingError(DETAIL)


@pytest.fixture(autouse=True)
def failing_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry_module, "Session", FailingSession)


@pytest.fixture
def exports(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Record any attempt to write a workbook. There should be none."""
    calls: list[object] = []
    monkeypatch.setattr(
        entry_module, "export_data_to_excel", lambda *args, **_kwargs: calls.append(args)
    )
    return calls


def _text(result: Result) -> str:
    return visible(result.output)


@pytest.mark.parametrize("command", ["buscar", "vacantes"])
def test_a_failed_run_ends_with_a_failing_exit_code(runner: CliRunner, command: str) -> None:
    """A script calling this has to be able to tell."""
    result = runner.invoke(app, [command])

    assert result.exit_code == 1


@pytest.mark.parametrize("command", ["buscar", "vacantes"])
def test_a_failed_run_is_not_reported_as_an_empty_one(runner: CliRunner, command: str) -> None:
    """The bug itself."""
    result = runner.invoke(app, [command])

    assert NO_VACANCIES_MESSAGE not in _text(result)


@pytest.mark.parametrize("command", ["buscar", "vacantes"])
def test_a_failed_run_says_so_in_spanish(runner: CliRunner, command: str) -> None:
    result = runner.invoke(app, [command])

    written = _text(result)

    assert "No se pudo consultar el sitio del MEP" in written


@pytest.mark.parametrize("command", ["buscar", "vacantes"])
def test_the_exception_is_not_left_to_escape(runner: CliRunner, command: str) -> None:
    """Typer would print a traceback for it. The user is told what happened;
    the traceback is the log's business."""
    result = runner.invoke(app, [command])

    assert not isinstance(result.exception, TransientScrapingError)


def test_a_failed_run_writes_no_workbook(runner: CliRunner, exports: list[object]) -> None:
    """An empty workbook would be the same lie in a file."""
    runner.invoke(app, ["buscar", "--exportar"])

    assert exports == []
