"""What the window does with what the user clicks, and with what comes back.

The worker is a double. It carries real signals, so the window is wired the way
it will be in production, but nothing here starts a thread or a browser: a test
makes the result arrive by emitting, which is what the worker would have done.

The window is never shown. Nothing asserted here needs pixels, and the platform
is offscreen anyway; see tests/gui/conftest.py.
"""

import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal, SignalInstance
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

from consulta_vacantes_mep.app.session import SearchResult
from consulta_vacantes_mep.events import (
    ItemCompleted,
    Phase,
    PhaseFinished,
    PhaseStarted,
)
from consulta_vacantes_mep.exceptions import PermanentScrapingError
from consulta_vacantes_mep.exports import excel as excel_module
from consulta_vacantes_mep.gui import window as window_module
from consulta_vacantes_mep.gui.reporter import QtReporter
from consulta_vacantes_mep.gui.window import (
    APPOINTMENT_COLUMNS,
    EXPORT_FAILURE_MESSAGE,
    FAILURE_MESSAGE,
    PHASE_TITLES,
    VACANCY_COLUMNS,
    MainWindow,
)
from consulta_vacantes_mep.labels import APPOINTMENT_LABELS, VACANCY_LABELS
from consulta_vacantes_mep.models import Appointment, AppointmentQuery, QueryOutcome, Vacancy
from consulta_vacantes_mep.settings import default_year

Drain = Callable[..., bool]

CEDULA = "102340567"


def _vacancy(number: str, specialty: str = "Francés") -> Vacancy:
    return Vacancy(
        number=number,
        regional_office="Direc. Regional Educacion Cartago",
        position_class="Profesor de Enseñanza Media",
        specialty=specialty,
        institution="Liceo de Prueba",
        lessons="10",
        starts_on="01/10/2026",
        ends_on="12/11/2026",
    )


def _appointment(vacancy_number: str) -> Appointment:
    return Appointment(
        vacancy_number=vacancy_number,
        national_id=CEDULA,
        full_name="PEREZ PEREZ JUAN",
        institution="Liceo de Prueba",
        position_class="Profesor de Enseñanza Media",
        specialty="Francés",
        group="MT 4",
        position_number="12345",
        starts_on="01/10/2026",
        ends_on="12/11/2026",
        status="Activo",
        eligibility_rating="No Consta",
        roster_title="Nómina de prueba",
    )


PUBLISHED = [_vacancy("1548582"), _vacancy("1548490", "Matemática")]


def _result(
    vacancies: list[Vacancy] | None = None,
    found: list[str] | None = None,
    failed: list[str] | None = None,
) -> SearchResult:
    queries = [
        AppointmentQuery(number, QueryOutcome.FOUND, [_appointment(number)])
        for number in found or []
    ]
    queries += [
        AppointmentQuery(number, QueryOutcome.FAILED, [], "timeout")
        for number in failed or []
    ]

    return SearchResult(
        vacancies=PUBLISHED if vacancies is None else vacancies, queries=queries
    )


class FakeWorker(QObject):
    """The worker's shape, with nothing behind it.

    A QObject here rather than the composition the real worker uses, because a
    double only has to carry signals and there is no emit of its own to collide
    with. The window reads is_running and calls search and refresh; that is the
    whole surface it depends on.
    """

    searched = Signal(object)
    refreshed = Signal(int)
    failed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.search_calls: list[tuple[int, str | None]] = []
        self.refresh_calls = 0
        self.is_running = False

    def search(self, year: int, specialty: str | None = None) -> None:
        self.search_calls.append((year, specialty))

    def refresh(self) -> None:
        self.refresh_calls += 1


@pytest.fixture
def window() -> MainWindow:
    """The QApplication an unparented widget needs is autouse; see conftest."""
    return MainWindow(FakeWorker(), QtReporter())  # type: ignore[arg-type]


@pytest.fixture
def reporter(window: MainWindow) -> QtReporter:
    """A reporter already connected to the window under test.

    Built here rather than taken from the window, which does not keep it: the
    window connects and has no further use for it, the same way the scrapers
    report without knowing who is listening.
    """
    fresh = QtReporter()
    fresh.progressed.connect(window._on_progress)

    return fresh


def _worker(window: MainWindow) -> FakeWorker:
    """The double the window was given."""
    return window._worker  # type: ignore[return-value]


def _text(item: QTableWidgetItem | None) -> str:
    """A cell's text. Qt returns None for a cell that was never filled, and a
    test reading one is asking about a row the window did not write."""
    assert item is not None, "the table has nothing in that cell"

    return item.text()


def _headings(table: QTableWidget) -> list[str]:
    return [
        _text(table.horizontalHeaderItem(column))
        for column in range(table.columnCount())
    ]


def _row(table: QTableWidget, row: int) -> list[str]:
    return [_text(table.item(row, column)) for column in range(table.columnCount())]


def _emit(signal: SignalInstance, payload: object) -> None:
    """Deliver what the worker would have delivered, and let it land."""
    signal.emit(payload)
    QApplication.processEvents()


def _report(reporter: QtReporter, *events: object) -> None:
    """Deliver what the scrapers would have reported, in order."""
    for event in events:
        reporter.emit(event)  # type: ignore[arg-type]

    QApplication.processEvents()


# ── It opens ──────────────────────────────────────────────────────────────────
def test_the_window_is_titled_in_spanish(window: MainWindow) -> None:
    assert window.windowTitle() == "Consulta Vacantes MEP"


def test_the_year_starts_at_the_current_one(window: MainWindow) -> None:
    """The year almost every search wants, so nobody has to set it."""
    assert window.year.value() == default_year()


def test_the_specialty_field_says_what_leaving_it_empty_means(
    window: MainWindow,
) -> None:
    """One search action, not two. Empty means every specialty, which is what
    the application layer already means by it, and the placeholder is what makes
    that visible instead of folklore."""
    assert window.specialty.placeholderText() == "Todas las especialidades"


def test_both_tabs_are_there(window: MainWindow) -> None:
    labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]

    assert labels == ["Vacantes", "Nombramientos"]


def test_the_tables_start_empty(window: MainWindow) -> None:
    assert window.vacancies_table.rowCount() == 0
    assert window.appointments_table.rowCount() == 0


def test_the_controls_start_usable(window: MainWindow) -> None:
    assert window.search_button.isEnabled() is True
    assert window.refresh_button.isEnabled() is True


# ── Headings ──────────────────────────────────────────────────────────────────
def test_the_vacancy_headings_come_from_the_labels(window: MainWindow) -> None:
    headings = _headings(window.vacancies_table)

    assert headings == [VACANCY_LABELS[field] for field in VACANCY_COLUMNS]


def test_the_appointment_headings_come_from_the_labels(window: MainWindow) -> None:
    headings = _headings(window.appointments_table)

    assert headings == [APPOINTMENT_LABELS[field] for field in APPOINTMENT_COLUMNS]


def test_no_column_shows_the_identification_number() -> None:
    """Checked against the column list rather than the rendered table, so it
    holds whether or not a test happened to put an appointment in one."""
    assert "national_id" not in APPOINTMENT_COLUMNS
    assert "national_id" not in VACANCY_COLUMNS


def test_the_name_is_shown() -> None:
    """Whether a post was filled, and by whom, is the question being asked."""
    assert "full_name" in APPOINTMENT_COLUMNS


# ── Asking for a search ───────────────────────────────────────────────────────
def test_pressing_search_asks_the_worker(window: MainWindow) -> None:
    window.search_button.click()

    assert _worker(window).search_calls == [(default_year(), None)]


def test_a_typed_specialty_is_passed_on(window: MainWindow) -> None:
    window.specialty.setText("Matemática")

    window.search_button.click()

    assert _worker(window).search_calls == [(default_year(), "Matemática")]


def test_a_specialty_of_only_spaces_means_every_one(window: MainWindow) -> None:
    """A field that looks empty is empty."""
    window.specialty.setText("   ")

    window.search_button.click()

    assert _worker(window).search_calls == [(default_year(), None)]


def test_the_year_that_was_set_is_the_year_asked_for(window: MainWindow) -> None:
    window.year.setValue(2025)

    window.search_button.click()

    assert _worker(window).search_calls == [(2025, None)]


def test_enter_in_the_specialty_field_searches(window: MainWindow) -> None:
    """Typing a specialty and pressing enter is what a person does."""
    window.specialty.setText("Francés")

    window.specialty.returnPressed.emit()

    assert _worker(window).search_calls == [(default_year(), "Francés")]


def test_pressing_refresh_asks_the_worker(window: MainWindow) -> None:
    window.refresh_button.click()

    assert _worker(window).refresh_calls == 1


def test_a_refresh_does_not_start_a_search(window: MainWindow) -> None:
    window.refresh_button.click()

    assert _worker(window).search_calls == []


# ── While a run is going ──────────────────────────────────────────────────────
def test_the_controls_go_dead_during_a_search(window: MainWindow) -> None:
    window.search_button.click()

    assert window.search_button.isEnabled() is False
    assert window.refresh_button.isEnabled() is False
    assert window.specialty.isEnabled() is False
    assert window.year.isEnabled() is False


def test_the_controls_go_dead_during_a_refresh(window: MainWindow) -> None:
    window.refresh_button.click()

    assert window.search_button.isEnabled() is False


def test_the_status_bar_says_a_search_is_going(window: MainWindow) -> None:
    window.search_button.click()

    assert "Consultando" in window.statusBar().currentMessage()


def test_the_status_bar_says_a_refresh_is_going(window: MainWindow) -> None:
    window.refresh_button.click()

    assert "Actualizando" in window.statusBar().currentMessage()


def test_a_second_search_is_not_asked_for_while_one_is_going(
    window: MainWindow,
) -> None:
    """The worker raises on a second run, which is right for a programming
    mistake and wrong as something a double click can cause. The window asks
    once."""
    worker = _worker(window)
    worker.is_running = True

    window.search_button.click()
    window.refresh_button.click()

    assert worker.search_calls == []
    assert worker.refresh_calls == 0


# ── A finished search ─────────────────────────────────────────────────────────
def test_every_vacancy_gets_a_row(window: MainWindow) -> None:
    _emit(_worker(window).searched, _result())

    assert window.vacancies_table.rowCount() == len(PUBLISHED)


def test_a_vacancy_row_holds_its_fields_in_column_order(window: MainWindow) -> None:
    _emit(_worker(window).searched, _result(vacancies=[_vacancy("1548582")]))

    assert _row(window.vacancies_table, 0) == [
        "1548582",
        "Francés",
        "Liceo de Prueba",
        "Direc. Regional Educacion Cartago",
        "01/10/2026",
        "12/11/2026",
    ]


def test_every_appointment_gets_a_row(window: MainWindow) -> None:
    _emit(_worker(window).searched, _result(found=["1548582", "1548490"]))

    assert window.appointments_table.rowCount() == 2


def test_an_appointment_row_holds_its_fields_in_column_order(
    window: MainWindow,
) -> None:
    _emit(_worker(window).searched, _result(found=["1548582"]))

    assert _row(window.appointments_table, 0) == [
        "1548582",
        "PEREZ PEREZ JUAN",
        "Liceo de Prueba",
        "Francés",
        "MT 4",
        "01/10/2026",
        "12/11/2026",
        "Activo",
    ]


def test_the_identification_number_is_nowhere_in_the_table(
    window: MainWindow,
) -> None:
    """The column list says it is not asked for. This says it did not arrive by
    some other route."""
    _emit(_worker(window).searched, _result(found=["1548582"]))

    table = window.appointments_table
    shown = {
        _text(table.item(row, column))
        for row in range(table.rowCount())
        for column in range(table.columnCount())
    }

    assert CEDULA not in shown


def test_vacancies_with_nobody_appointed_still_fill_a_table(
    window: MainWindow,
) -> None:
    """The ordinary case in the days after a batch is published, and the reason
    there are two tabs. One table of appointments would be blank here."""
    _emit(_worker(window).searched, _result())

    assert window.vacancies_table.rowCount() == len(PUBLISHED)
    assert window.appointments_table.rowCount() == 0


def test_a_second_search_replaces_the_first_results(window: MainWindow) -> None:
    """Rows left over from a previous search would read as part of this one."""
    worker = _worker(window)

    _emit(worker.searched, _result(found=["1548582", "1548490"]))
    _emit(worker.searched, _result(vacancies=[_vacancy("1548582")]))

    assert window.vacancies_table.rowCount() == 1
    assert window.appointments_table.rowCount() == 0


def test_the_controls_come_back_when_a_search_ends(window: MainWindow) -> None:
    window.search_button.click()

    _emit(_worker(window).searched, _result())

    assert window.search_button.isEnabled() is True
    assert window.refresh_button.isEnabled() is True


def test_the_status_bar_counts_what_was_found(window: MainWindow) -> None:
    _emit(_worker(window).searched, _result(found=["1548582"]))

    message = window.statusBar().currentMessage()

    assert "2 vacantes" in message
    assert "1 nombramientos" in message


def test_the_status_bar_reports_lookups_that_failed(window: MainWindow) -> None:
    """A query that could not be completed must not read as an absence of
    appointments, which is the whole reason AppointmentQuery exists."""
    _emit(_worker(window).searched, _result(failed=["1548490"]))

    assert "1 sin respuesta" in window.statusBar().currentMessage()


def test_nothing_is_said_about_failures_when_there_were_none(
    window: MainWindow,
) -> None:
    _emit(_worker(window).searched, _result(found=["1548582"]))

    assert "sin respuesta" not in window.statusBar().currentMessage()


# ── A finished refresh ────────────────────────────────────────────────────────
def test_a_refresh_reports_the_new_count(window: MainWindow) -> None:
    _emit(_worker(window).refreshed, 45)

    assert "45 vacantes" in window.statusBar().currentMessage()


def test_the_controls_come_back_when_a_refresh_ends(window: MainWindow) -> None:
    window.refresh_button.click()

    _emit(_worker(window).refreshed, 45)

    assert window.refresh_button.isEnabled() is True


# ── A run that failed ─────────────────────────────────────────────────────────
def test_a_failure_is_explained_in_spanish(window: MainWindow) -> None:
    error = PermanentScrapingError("the page structure changed")

    _emit(_worker(window).failed, error)

    assert window.statusBar().currentMessage() == FAILURE_MESSAGE


def test_the_english_detail_does_not_reach_the_window(window: MainWindow) -> None:
    """It is in the log, with its traceback. A window is not where English
    belongs."""
    _emit(_worker(window).failed,
        PermanentScrapingError("the page structure changed"),
    )

    assert "page structure" not in window.statusBar().currentMessage()


def test_the_controls_come_back_after_a_failure(window: MainWindow) -> None:
    """A failed run is ordinary: the site goes down, a postback times out. The
    window has to let the user try again."""
    window.search_button.click()

    _emit(_worker(window).failed, PermanentScrapingError("nope"))

    assert window.search_button.isEnabled() is True
    assert window.refresh_button.isEnabled() is True


def test_a_failure_leaves_earlier_results_alone(window: MainWindow) -> None:
    """Clearing the tables would throw away the only thing on screen worth
    looking at while the user decides whether to retry."""
    worker = _worker(window)
    _emit(worker.searched, _result(found=["1548582"]))

    _emit(worker.failed, PermanentScrapingError("nope"))

    assert window.vacancies_table.rowCount() == len(PUBLISHED)
    assert window.appointments_table.rowCount() == 1


# ── Progress while a run goes ─────────────────────────────────────────────────
def test_there_is_a_title_for_every_phase() -> None:
    """PHASE_TITLES is indexed by phase, so a phase added to the enum without a
    title is a KeyError in the middle of a run, in the one code path that only
    runs when the window is already busy."""
    assert set(PHASE_TITLES) == set(Phase)


def test_no_bar_is_shown_before_anything_starts(window: MainWindow) -> None:
    """A progress bar sitting at zero reads as something stuck."""
    assert window.progress.isVisible() is False


def test_the_bar_appears_when_a_run_starts(window: MainWindow) -> None:
    window.search_button.click()

    assert window.progress.isHidden() is False


def test_the_bar_is_a_busy_indicator_until_a_total_is_known(
    window: MainWindow,
) -> None:
    """The scraper cannot report a total until it has loaded the page and read
    the dropdown, which is a second or two of a browser starting up. A range of
    nothing is how Qt draws that."""
    window.search_button.click()

    assert window.progress.minimum() == 0
    assert window.progress.maximum() == 0


def test_a_phase_gives_the_bar_its_total(
    window: MainWindow, reporter: QtReporter
) -> None:
    window.search_button.click()

    _report(reporter, PhaseStarted(Phase.VACANCIES, 19))

    assert window.progress.maximum() == 19
    assert window.progress.value() == 0


def test_the_bar_follows_the_count_the_event_carries(
    window: MainWindow, reporter: QtReporter
) -> None:
    _report(
        reporter,
        PhaseStarted(Phase.VACANCIES, 19),
        ItemCompleted(Phase.VACANCIES, 1, 19, "Cartago", 3),
        ItemCompleted(Phase.VACANCIES, 2, 19, "Alajuela", 2),
    )

    assert window.progress.value() == 2


def test_the_bar_does_not_go_backwards_when_workers_finish_out_of_order(
    window: MainWindow, reporter: QtReporter
) -> None:
    """The appointments phase runs four at once and reports in the order they
    finish, so the labels arrive shuffled while index stays a count. A bar
    driven by anything other than index would jump around."""
    _report(
        reporter,
        PhaseStarted(Phase.APPOINTMENTS, 45, concurrency=4),
        ItemCompleted(Phase.APPOINTMENTS, 1, 45, "1548639", 0),
        ItemCompleted(Phase.APPOINTMENTS, 2, 45, "1548490", 1),
        ItemCompleted(Phase.APPOINTMENTS, 3, 45, "1548582", 0),
    )

    assert window.progress.value() == 3


def test_the_status_bar_says_which_phase_and_how_far(
    window: MainWindow, reporter: QtReporter
) -> None:
    _report(
        reporter,
        PhaseStarted(Phase.VACANCIES, 19),
        ItemCompleted(Phase.VACANCIES, 3, 19, "Cartago", 3),
    )

    message = window.statusBar().currentMessage()

    assert "Vacantes" in message
    assert "3 de 19" in message
    assert "Cartago" in message


def test_a_finished_phase_fills_the_bar(
    window: MainWindow, reporter: QtReporter
) -> None:
    _report(
        reporter,
        PhaseStarted(Phase.VACANCIES, 19),
        ItemCompleted(Phase.VACANCIES, 1, 19, "Cartago", 3),
        PhaseFinished(Phase.VACANCIES, 45),
    )

    assert window.progress.value() == window.progress.maximum()


def test_a_finished_phase_says_what_it_came_to(
    window: MainWindow, reporter: QtReporter
) -> None:
    """Said between the two phases, so the user learns the vacancy count before
    the appointments phase starts counting from zero again."""
    _report(reporter, PhaseStarted(Phase.VACANCIES, 19), PhaseFinished(Phase.VACANCIES, 45))

    assert window.statusBar().currentMessage() == "45 vacantes."


def test_a_finished_phase_reports_what_it_could_not_read(
    window: MainWindow, reporter: QtReporter
) -> None:
    _report(
        reporter,
        PhaseStarted(Phase.VACANCIES, 19),
        PhaseFinished(Phase.VACANCIES, 42, failed=2),
    )

    assert window.statusBar().currentMessage() == "42 vacantes, 2 sin respuesta."


def test_the_second_phase_starts_the_bar_over(
    window: MainWindow, reporter: QtReporter
) -> None:
    """Two phases run back to back, and the appointments one has a total of its
    own. A bar left full would show the second phase as already done."""
    _report(
        reporter,
        PhaseStarted(Phase.VACANCIES, 19),
        PhaseFinished(Phase.VACANCIES, 45),
        PhaseStarted(Phase.APPOINTMENTS, 45, concurrency=4),
    )

    assert window.progress.maximum() == 45
    assert window.progress.value() == 0


def test_the_bar_goes_away_when_the_result_arrives(
    window: MainWindow, reporter: QtReporter
) -> None:
    window.search_button.click()
    _report(reporter, PhaseStarted(Phase.APPOINTMENTS, 45), PhaseFinished(Phase.APPOINTMENTS, 12))

    _emit(_worker(window).searched, _result())

    assert window.progress.isHidden() is True


def test_the_bar_goes_away_when_a_run_fails(
    window: MainWindow, reporter: QtReporter
) -> None:
    """A bar left on screen after a failure says the run is still going."""
    window.search_button.click()
    _report(reporter, PhaseStarted(Phase.VACANCIES, 19))

    _emit(_worker(window).failed, PermanentScrapingError("nope"))

    assert window.progress.isHidden() is True


def test_an_unknown_event_is_ignored(window: MainWindow, reporter: QtReporter) -> None:
    """The reporter carries one signal for every event type so that an event
    added later lands in the same slot. It has to fall through rather than
    raise, which would take down a run for a message nobody needed."""
    window.search_button.click()

    _report(reporter, object())

    assert window.progress.isHidden() is False


# ── Exporting ─────────────────────────────────────────────────────────────────
@pytest.fixture
def outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Send workbooks somewhere the test can read and nothing else can see."""
    monkeypatch.setattr(excel_module, "OUTPUT_DIR", tmp_path)

    return tmp_path


def _written(outputs: Path) -> Path:
    files = sorted(outputs.glob("*.xlsx"))

    assert len(files) == 1, f"expected one workbook, found {len(files)}"

    return files[0]


def _contents(path: Path) -> bytes:
    """Everything inside the workbook, uncompressed.

    An xlsx is a zip, so searching the file's own bytes for a value finds
    nothing whether or not it is in there, which would make a test for the
    absence of something pass for the wrong reason. Reading the parts also
    reaches the shared string table, where openpyxl keeps cell text.
    """
    with zipfile.ZipFile(path) as archive:
        return b"".join(archive.read(name) for name in archive.namelist())


def test_there_is_nothing_to_export_before_a_search(window: MainWindow) -> None:
    """A button that writes an empty file is worse than one that is greyed."""
    assert window.export_button.isEnabled() is False


def test_exporting_becomes_possible_once_there_are_results(
    window: MainWindow,
) -> None:
    _emit(_worker(window).searched, _result(found=["1548582"]))

    assert window.export_button.isEnabled() is True


def test_exporting_is_not_possible_during_a_run(window: MainWindow) -> None:
    _emit(_worker(window).searched, _result(found=["1548582"]))

    window.search_button.click()

    assert window.export_button.isEnabled() is False


def test_the_personal_data_box_starts_unchecked(window: MainWindow) -> None:
    """The same default the command has, read from the same setting, so one
    environment variable still governs both."""
    assert window.personal_data.isChecked() is False


def test_a_workbook_is_written(window: MainWindow, outputs: Path) -> None:
    _emit(_worker(window).searched, _result(found=["1548582"]))

    window.export_button.click()

    assert _written(outputs).exists()


def test_the_window_says_where_the_file_went(
    window: MainWindow, outputs: Path
) -> None:
    _emit(_worker(window).searched, _result(found=["1548582"]))

    window.export_button.click()

    assert str(_written(outputs)) in window.statusBar().currentMessage()


def test_the_file_is_named_for_the_specialty_that_was_searched(
    window: MainWindow, outputs: Path
) -> None:
    """The same rule the command uses, which is why it moved into the export
    layer rather than being written out twice."""
    window.specialty.setText("Educación Física")
    window.search_button.click()
    _emit(_worker(window).searched, _result(found=["1548582"]))

    window.export_button.click()

    assert _written(outputs).name.startswith("vacantes_Educación_Física_")


def test_a_search_for_everything_is_named_for_everything(
    window: MainWindow, outputs: Path
) -> None:
    window.search_button.click()
    _emit(_worker(window).searched, _result(found=["1548582"]))

    window.export_button.click()

    assert _written(outputs).name.startswith("todas_las_vacantes_")


def test_the_identification_number_is_left_out_by_default(
    window: MainWindow, outputs: Path
) -> None:
    """The window never shows it, and by default the file does not carry it
    either. Checked against the bytes, since openpyxl keeps strings in a part of
    the archive of their own."""
    _emit(_worker(window).searched, _result(found=["1548582"]))

    window.export_button.click()

    assert CEDULA.encode() not in _contents(_written(outputs))


def test_the_identification_number_is_written_when_the_box_is_checked(
    window: MainWindow, outputs: Path
) -> None:
    _emit(_worker(window).searched, _result(found=["1548582"]))
    window.personal_data.setChecked(True)

    window.export_button.click()

    assert CEDULA.encode() in _contents(_written(outputs))


def test_a_file_that_cannot_be_written_is_explained_in_spanish(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case that actually happens on Windows: the user exports, opens the
    file, exports again within the same minute, and Excel is holding it."""
    _emit(_worker(window).searched, _result(found=["1548582"]))

    def _locked(*_args: object, **_kwargs: object) -> None:
        message = "[Errno 13] Permission denied"
        raise PermissionError(message)

    monkeypatch.setattr(window_module, "export_data_to_excel", _locked)

    window.export_button.click()

    assert window.statusBar().currentMessage() == EXPORT_FAILURE_MESSAGE


def test_a_failed_export_leaves_the_button_usable(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closing Excel and clicking again is the fix, so the button has to still
    be there."""
    _emit(_worker(window).searched, _result(found=["1548582"]))

    def _locked(*_args: object, **_kwargs: object) -> None:
        message = "[Errno 13] Permission denied"
        raise PermissionError(message)

    monkeypatch.setattr(window_module, "export_data_to_excel", _locked)

    window.export_button.click()

    assert window.export_button.isEnabled() is True


# ── What a refresh does to the results ────────────────────────────────────────
def test_a_refresh_clears_what_was_on_screen(window: MainWindow) -> None:
    """Refreshing exists for when the site has published something new, so the
    rows from before answer the same question asked of different data."""
    worker = _worker(window)
    _emit(worker.searched, _result(found=["1548582"]))

    _emit(worker.refreshed, 45)

    assert window.vacancies_table.rowCount() == 0
    assert window.appointments_table.rowCount() == 0


def test_a_refresh_takes_exporting_away(window: MainWindow) -> None:
    """Otherwise the one way to get a file the user believes is current and is
    not: export rows scraped before the refresh they just asked for."""
    worker = _worker(window)
    _emit(worker.searched, _result(found=["1548582"]))

    _emit(worker.refreshed, 45)

    assert window.export_button.isEnabled() is False


def test_a_refresh_says_a_search_is_the_next_step(window: MainWindow) -> None:
    _emit(_worker(window).refreshed, 45)

    message = window.statusBar().currentMessage()

    assert "45 vacantes" in message
    assert "búsqueda" in message
