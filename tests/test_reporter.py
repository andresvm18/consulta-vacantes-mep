"""How a run reads on the terminal, and what it leaves behind.

The interesting guarantee is not the wording. It is that no live display
survives a run: a Progress that starts and never stops leaves the terminal in
its alternate drawing mode with the cursor hidden, which no assertion about
output would notice and every user would.

Rich sizes what it draws to the terminal, so the console here is given a fixed
width. Without it these tests would read differently on CI than on a laptop.
"""

import io

import pytest
from rich.console import Console

from consulta_vacantes_mep.cli.reporter import RichReporter
from consulta_vacantes_mep.events import (
    ItemCompleted,
    Phase,
    PhaseFinished,
    PhaseStarted,
)

_WIDTH = 100


@pytest.fixture
def output() -> io.StringIO:
    return io.StringIO()


@pytest.fixture
def reporter(output: io.StringIO) -> RichReporter:
    console = Console(file=output, width=_WIDTH, force_terminal=False, no_color=True)
    return RichReporter(console)


def _text(output: io.StringIO) -> str:
    return output.getvalue()


# ── The live display ──────────────────────────────────────────────────────────
def test_no_display_is_running_before_a_phase_starts(
    reporter: RichReporter,
) -> None:
    assert reporter._progress is None


def test_a_finished_phase_leaves_no_display_running(
    reporter: RichReporter,
) -> None:
    reporter.emit(PhaseStarted(Phase.VACANCIES, 15))
    reporter.emit(PhaseFinished(Phase.VACANCIES, 50))

    assert reporter._progress is None


def test_close_takes_down_a_phase_that_never_finished(
    reporter: RichReporter,
) -> None:
    """A phase that raises never emits its closing event.

    The CLI calls close from a finally block for exactly this case.
    """
    reporter.emit(PhaseStarted(Phase.VACANCIES, 15))
    reporter.close()

    assert reporter._progress is None


def test_close_is_safe_to_call_when_nothing_is_running(
    reporter: RichReporter,
) -> None:
    """The finally block runs whether or not a phase ever started."""
    reporter.close()
    reporter.close()

    assert reporter._progress is None


def test_a_second_phase_replaces_the_first_display(
    reporter: RichReporter,
) -> None:
    """The two phases run back to back and must not stack two live bars."""
    reporter.emit(PhaseStarted(Phase.VACANCIES, 15))
    first = reporter._progress

    reporter.emit(PhaseStarted(Phase.APPOINTMENTS, 50, concurrency=4))

    assert reporter._progress is not None
    assert reporter._progress is not first


# ── What the run reports ──────────────────────────────────────────────────────
def test_a_starting_phase_announces_how_much_work_there_is(
    reporter: RichReporter, output: io.StringIO
) -> None:
    reporter.emit(PhaseStarted(Phase.VACANCIES, 15))

    assert "Vacantes" in _text(output)
    assert "15" in _text(output)


def test_the_appointments_phase_announces_its_concurrency(
    reporter: RichReporter, output: io.StringIO
) -> None:
    """Four browsers at once explains why results arrive out of order."""
    reporter.emit(PhaseStarted(Phase.APPOINTMENTS, 50, concurrency=4))

    assert "Nombramientos" in _text(output)
    assert "4" in _text(output)


def test_the_vacancies_phase_announces_no_concurrency(
    reporter: RichReporter, output: io.StringIO
) -> None:
    """It drives a single page, so there is nothing to report."""
    reporter.emit(PhaseStarted(Phase.VACANCIES, 15))

    assert "paralelo" not in _text(output)


def test_an_item_that_failed_is_named_as_it_happens(
    reporter: RichReporter, output: io.StringIO
) -> None:
    """Failures are the lines worth reading, so they are printed, not counted."""
    reporter.emit(PhaseStarted(Phase.VACANCIES, 15))
    reporter.emit(
        ItemCompleted(Phase.VACANCIES, 1, 15, "Dirección Regional de Pérez Zeledón", None)
    )

    assert "Pérez Zeledón" in _text(output)


def test_an_item_that_succeeded_is_not_printed_as_a_failure(
    reporter: RichReporter, output: io.StringIO
) -> None:
    reporter.emit(PhaseStarted(Phase.VACANCIES, 15))
    reporter.emit(ItemCompleted(Phase.VACANCIES, 1, 15, "Dirección Regional de Heredia", 7))

    assert "sin respuesta" not in _text(output)


def test_a_finished_phase_reports_its_total(
    reporter: RichReporter, output: io.StringIO
) -> None:
    reporter.emit(PhaseStarted(Phase.VACANCIES, 15))
    reporter.emit(PhaseFinished(Phase.VACANCIES, 50))

    assert "50" in _text(output)
    assert "vacantes" in _text(output)


def test_a_finished_phase_reports_what_it_could_not_read(
    reporter: RichReporter, output: io.StringIO
) -> None:
    """An office that failed and an office with nothing published differ."""
    reporter.emit(PhaseStarted(Phase.VACANCIES, 15))
    reporter.emit(PhaseFinished(Phase.VACANCIES, 50, failed=2))

    assert "2" in _text(output)
    assert "sin respuesta" in _text(output)


def test_a_clean_phase_says_nothing_about_failures(
    reporter: RichReporter, output: io.StringIO
) -> None:
    reporter.emit(PhaseStarted(Phase.APPOINTMENTS, 50, concurrency=4))
    reporter.emit(PhaseFinished(Phase.APPOINTMENTS, 1))

    assert "sin respuesta" not in _text(output)


# ── Events arriving out of turn ───────────────────────────────────────────────
def test_an_item_without_a_started_phase_is_ignored(
    reporter: RichReporter,
) -> None:
    """A phase that fails during navigation never emits PhaseStarted.

    The scrapers bind their counters before the browser opens for the same
    reason. Dropping the event is right; raising here would turn a scraping
    failure into a crash in the code drawing it.
    """
    reporter.emit(ItemCompleted(Phase.VACANCIES, 1, 15, "Dirección Regional de Cartago", 3))

    assert reporter._progress is None
