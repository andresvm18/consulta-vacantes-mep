"""What the subcommands do with what the user typed.

These invoke the Typer app the way a shell does, so the argument parsing is
real. Session is replaced by a double: the commands are under test, not the
scraping underneath them. The result they read is a real SearchResult, since
imitating its shape would only prove the imitation was right.
"""

import importlib
from typing import ClassVar

import pytest
from typer.testing import CliRunner, Result

from consulta_vacantes_mep.app.session import SearchResult
from consulta_vacantes_mep.cli.main import app, prepare_browser
from consulta_vacantes_mep.models import Vacancy
from consulta_vacantes_mep.utils.playwright_setup import ChromiumCheck, ChromiumStatus

# See tests/cli/conftest.py for why this is not a plain import.
main_module = importlib.import_module("consulta_vacantes_mep.cli.main")


def _vacancy(number: str, specialty: str) -> Vacancy:
    return Vacancy(
        number=number,
        regional_office="Dirección Regional de Prueba",
        position_class="Profesor de Enseñanza Media",
        specialty=specialty,
        institution="Liceo de Prueba",
        lessons="10",
        starts_on="05/08/2026",
        ends_on="31/12/2026",
    )


PUBLISHED = [
    _vacancy("1531185", "Francés"),
    _vacancy("1536996", "Francés"),
    _vacancy("1538058", "Matemática"),
]


class FakeSession:
    """Records what the commands asked of the application layer."""

    instances: ClassVar[list["FakeSession"]] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.vacancy_calls: list[str | None] = []
        self.refresh_calls: list[bool] = []
        self.search_calls: list[tuple[int, str | None]] = []
        FakeSession.instances.append(self)

    def vacancies(
        self, specialty: str | None = None, refresh: bool = False
    ) -> list[Vacancy]:
        self.vacancy_calls.append(specialty)
        self.refresh_calls.append(refresh)

        if not specialty:
            return list(PUBLISHED)

        return [v for v in PUBLISHED if v.specialty == specialty]

    def search(self, year: int, specialty: str | None = None) -> SearchResult:
        self.search_calls.append((year, specialty))
        return SearchResult(vacancies=PUBLISHED, queries=[])


@pytest.fixture(autouse=True)
def fake_session(monkeypatch: pytest.MonkeyPatch) -> type[FakeSession]:
    FakeSession.instances = []
    monkeypatch.setattr(main_module, "Session", FakeSession)
    return FakeSession


def _invoke(runner: CliRunner, *args: str) -> Result:
    return runner.invoke(app, list(args))


# ── Help ──────────────────────────────────────────────────────────────────────
def test_help_opens_no_browser(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Click answers --help before the callback runs.

    This is why asking for help does not pay for a browser launch, and making
    the callback eager again would take it away silently.
    """

    def explode() -> bool:
        message = "the browser check ran for --help"
        raise AssertionError(message)

    monkeypatch.setattr(main_module, "chromium_is_available", explode)

    result = _invoke(runner, "--help")

    assert result.exit_code == 0


def test_help_is_in_spanish(runner: CliRunner) -> None:
    """Typer renders the command docstrings, which the user reads."""
    result = _invoke(runner, "--help")

    assert "vacantes" in result.output
    assert "buscar" in result.output


# ── vacantes ──────────────────────────────────────────────────────────────────
def test_vacantes_lists_every_vacancy(runner: CliRunner) -> None:
    result = _invoke(runner, "vacantes")

    assert result.exit_code == 0
    assert "1531185" in result.output
    assert "1538058" in result.output


def test_vacantes_passes_the_specialty_through(runner: CliRunner) -> None:
    result = _invoke(runner, "vacantes", "--especialidad", "Francés")

    assert result.exit_code == 0
    assert FakeSession.instances[0].vacancy_calls == ["Francés"]


def test_vacantes_without_a_specialty_asks_for_all(runner: CliRunner) -> None:
    _invoke(runner, "vacantes")

    assert FakeSession.instances[0].vacancy_calls == [None]


# ── buscar ────────────────────────────────────────────────────────────────────
def test_buscar_passes_the_year_through(runner: CliRunner) -> None:
    result = _invoke(runner, "buscar", "--anio", "2025")

    assert result.exit_code == 0
    assert FakeSession.instances[0].search_calls == [(2025, None)]


def test_buscar_defaults_to_the_current_year(runner: CliRunner) -> None:
    """The year the user almost always wants, so it should not be required.

    Asserted as a lower bound rather than a value, since a literal would fail
    on its own every first of January.
    """
    _invoke(runner, "buscar")

    year, _ = FakeSession.instances[0].search_calls[0]

    assert year >= 2026


def test_buscar_passes_the_specialty_through(runner: CliRunner) -> None:
    _invoke(runner, "buscar", "--especialidad", "Matemática")

    _, specialty = FakeSession.instances[0].search_calls[0]

    assert specialty == "Matemática"


def test_an_unknown_option_is_rejected(runner: CliRunner) -> None:
    """Typer's own behaviour, pinned because a typo silently ignored would be
    worse than one refused."""
    result = _invoke(runner, "buscar", "--especialdad", "Francés")

    assert result.exit_code != 0


# ── prepare_browser ───────────────────────────────────────────────────────────
def test_an_available_browser_needs_no_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def not_called() -> ChromiumCheck:
        message = "install ran with a browser already present"
        raise AssertionError(message)

    monkeypatch.setattr(main_module, "chromium_is_available", lambda: True)
    monkeypatch.setattr(main_module, "install_chromium", not_called)

    assert prepare_browser() is True


def test_a_missing_browser_is_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "chromium_is_available", lambda: False)
    monkeypatch.setattr(
        main_module, "install_chromium", lambda: ChromiumCheck(ChromiumStatus.INSTALLED)
    )

    assert prepare_browser() is True


def test_an_install_that_fails_gives_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "chromium_is_available", lambda: False)
    monkeypatch.setattr(
        main_module,
        "install_chromium",
        lambda: ChromiumCheck(ChromiumStatus.FAILED, "connection refused"),
    )

    assert prepare_browser() is False


@pytest.mark.parametrize(
    "status", [ChromiumStatus.NOT_INSTALLABLE, ChromiumStatus.FAILED]
)
def test_every_failing_status_has_something_to_say(
    status: ChromiumStatus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CHROMIUM_MESSAGES is indexed by status, so a value added to the enum
    without a message is a KeyError during startup, in the one code path that
    runs before anything else."""
    monkeypatch.setattr(main_module, "chromium_is_available", lambda: False)
    monkeypatch.setattr(main_module, "install_chromium", lambda: ChromiumCheck(status))

    assert prepare_browser() is False
