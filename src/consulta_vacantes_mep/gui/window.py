"""The window.

What the user does here is what the menu did: ask for every vacancy, ask for one
specialty, or scrape the vacancy list again. The sequence behind each is the
same application layer the terminal interface drives, reached through a worker
so that a run does not stop the window repainting.

Two tables rather than one. A search that finds vacancies nobody has been
appointed to yet is an ordinary result, common in the days after a batch is
published, and a single table of appointments would leave the user looking at an
empty screen after half a minute of waiting. The two tabs are the two sheets of
the workbook, which is the shape the exported file already has.

Columns are listed by field name and their headings come from labels.py, so the
Spanish is defined in one place. The cédula is in neither list. Nobody opens
this to look up an identification number, and a window left open shows it to
whoever walks past.
"""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from consulta_vacantes_mep.app.session import SearchResult
from consulta_vacantes_mep.events import (
    Event,
    ItemCompleted,
    Phase,
    PhaseFinished,
    PhaseStarted,
)
from consulta_vacantes_mep.exports.excel import export_data_to_excel, filename_prefix
from consulta_vacantes_mep.gui.reporter import QtReporter
from consulta_vacantes_mep.gui.worker import SearchWorker
from consulta_vacantes_mep.labels import APPOINTMENT_LABELS, VACANCY_LABELS
from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.settings import EXPORT, default_year
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)

WINDOW_TITLE = "Consulta Vacantes MEP"

# What each scraping phase is called on screen. The tabs are named from the
# same place as the progress line, so the user reads one word for one thing.
PHASE_TITLES = {
    Phase.VACANCIES: "Vacantes",
    Phase.APPOINTMENTS: "Nombramientos",
}

# Qt's own bounds are enormous and a year outside this range is a typo.
MIN_YEAR = 2000
MAX_YEAR = 2100

VACANCY_COLUMNS = (
    "number",
    "specialty",
    "institution",
    "regional_office",
    "starts_on",
    "ends_on",
)

# Everything the registry answers except who, plus the name. national_id is
# absent on purpose; see the module docstring.
APPOINTMENT_COLUMNS = (
    "vacancy_number",
    "full_name",
    "institution",
    "specialty",
    "group",
    "starts_on",
    "ends_on",
    "status",
)

FAILURE_MESSAGE = (
    "No se pudo completar la consulta. Revise su conexión e intente de nuevo; "
    "el detalle quedó en el archivo de registro."
)

# The one that actually happens: the user exports, opens the file, exports
# again, and Windows refuses to overwrite a workbook Excel has open. The
# timestamp in the name only goes down to the minute, so a second export within
# the same minute lands on the same file.
EXPORT_FAILURE_MESSAGE = (
    "No se pudo escribir el archivo. Si lo tiene abierto en Excel, ciérrelo e "
    "intente de nuevo; el detalle quedó en el archivo de registro."
)


def _table(columns: tuple[str, ...], labels: dict[str, str]) -> QTableWidget:
    """A read-only table of whole rows, headed in Spanish."""
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels([labels[field] for field in columns])
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.verticalHeader().setVisible(False)

    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(True)

    return table


def _fill(
    table: QTableWidget, columns: tuple[str, ...], records: list[Vacancy] | list[Appointment]
) -> None:
    """Replace whatever the table held with these records."""
    table.setRowCount(len(records))

    for row, record in enumerate(records):
        for column, field in enumerate(columns):
            table.setItem(row, column, QTableWidgetItem(getattr(record, field)))

    table.resizeColumnsToContents()


class MainWindow(QMainWindow):
    """Drives one SearchWorker and shows what comes back.

    The worker is given rather than built. It owns the Session, and the Session
    owns the vacancy cache, so what is handed in here decides whether a second
    search is cheap. It also lets a test drive the window without a browser.
    """

    def __init__(self, worker: SearchWorker, reporter: QtReporter) -> None:
        super().__init__()
        self._worker = worker

        # What the tables are showing, kept so it can be exported. A refresh
        # clears it: the cache it rescraped is a different snapshot from the one
        # these rows came from, and exporting the old one afterwards would hand
        # the user a file that disagrees with what they just asked for.
        self._result: SearchResult | None = None
        self._specialty: str | None = None

        self.setWindowTitle(WINDOW_TITLE)
        self._build()

        self._worker.searched.connect(self._on_searched)
        self._worker.refreshed.connect(self._on_refreshed)
        self._worker.failed.connect(self._on_failed)

        # Connected here, on the thread that owns the widgets, which is what
        # makes Qt queue the events the scrapers emit from their own threads.
        reporter.progressed.connect(self._on_progress)

    # ── Laying it out ────────────────────────────────────────────────────────
    def _build(self) -> None:
        self.specialty = QLineEdit()
        self.specialty.setPlaceholderText("Todas las especialidades")
        self.specialty.returnPressed.connect(self.start_search)

        self.year = QSpinBox()
        self.year.setRange(MIN_YEAR, MAX_YEAR)
        self.year.setValue(default_year())
        self.year.setGroupSeparatorShown(False)

        self.search_button = QPushButton("Buscar")
        self.search_button.setDefault(True)
        self.search_button.clicked.connect(self.start_search)

        self.refresh_button = QPushButton("Actualizar vacantes")
        self.refresh_button.clicked.connect(self.start_refresh)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Especialidad:"))
        controls.addWidget(self.specialty, stretch=1)
        controls.addWidget(QLabel("Año:"))
        controls.addWidget(self.year)
        controls.addWidget(self.search_button)
        controls.addWidget(self.refresh_button)

        self.vacancies_table = _table(VACANCY_COLUMNS, VACANCY_LABELS)
        self.appointments_table = _table(APPOINTMENT_COLUMNS, APPOINTMENT_LABELS)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.vacancies_table, PHASE_TITLES[Phase.VACANCIES])
        self.tabs.addTab(self.appointments_table, PHASE_TITLES[Phase.APPOINTMENTS])

        self.personal_data = QCheckBox("Incluir cédula y nombre")
        self.personal_data.setChecked(EXPORT.include_personal_data)
        self.personal_data.setToolTip(
            "Un archivo con estos datos identifica a personas. "
            "Trátelo en consecuencia."
        )

        self.export_button = QPushButton("Exportar a Excel")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export)

        exporting = QHBoxLayout()
        exporting.addWidget(self.personal_data)
        exporting.addStretch(1)
        exporting.addWidget(self.export_button)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addWidget(self.progress)
        layout.addWidget(self.tabs, stretch=1)
        layout.addLayout(exporting)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.statusBar().showMessage("Listo.")

    # ── What the user asks for ───────────────────────────────────────────────
    def start_search(self) -> None:
        """Look up the vacancies and the appointments made against them.

        An empty specialty field means every one of them, which is what the
        placeholder says and what the application layer already means by it.
        """
        if self._worker.is_running:
            return

        specialty = self.specialty.text().strip() or None

        self._specialty = specialty

        self._set_busy(message="Consultando vacantes y nombramientos...")
        self._worker.search(self.year.value(), specialty)

    def start_refresh(self) -> None:
        """Scrape the vacancy list again, without querying appointments."""
        if self._worker.is_running:
            return

        self._set_busy(message="Actualizando la lista de vacantes...")
        self._worker.refresh()

    # ── While a run is going ─────────────────────────────────────────────────
    def _on_progress(self, event: Event) -> None:
        """Show how far along the run is.

        Matched on rather than handled by one slot per event type, which is why
        the reporter has a single signal: an event added later lands here and
        falls through without breaking anything.
        """
        match event:
            case PhaseStarted():
                self._phase_started(event)

            case ItemCompleted():
                self._item_completed(event)

            case PhaseFinished():
                self._phase_finished(event)

    def _phase_started(self, event: PhaseStarted) -> None:
        """Give the bar something to measure against.

        Until this arrives the bar has no total, because the scraper cannot know
        one until it has loaded the page and read the dropdown. It spends that
        time as a busy indicator rather than sitting at zero, which would read
        as nothing happening.
        """
        self.progress.setRange(0, event.total)
        self.progress.setValue(0)
        self.statusBar().showMessage(self._phase_line(event.phase, 0, event.total))

    def _item_completed(self, event: ItemCompleted) -> None:
        """Advance to the count the event carries, not by one.

        index is how many have finished, which is what events.py promises and
        what both phases emit. Counting arrivals here instead would drift from
        the truth if an event were ever missed, and the appointments phase
        reports in the order four workers happen to finish.
        """
        self.progress.setValue(event.index)
        self.statusBar().showMessage(
            self._phase_line(event.phase, event.index, event.total, event.label)
        )

    def _phase_finished(self, event: PhaseFinished) -> None:
        """Fill the bar and say what the phase came to.

        Worth saying between the two phases: the user learns how many vacancies
        were found before the appointments phase starts counting from zero
        again, which otherwise looks like the run restarting.

        total is records collected, not items processed, so the noun comes from
        the phase. The bar is reset by the next phase and hidden once the result
        arrives.
        """
        self.progress.setValue(self.progress.maximum())

        found = f"{event.total} {PHASE_TITLES[event.phase].lower()}"
        failures = f", {event.failed} sin respuesta" if event.failed else ""

        self.statusBar().showMessage(f"{found}{failures}.")

    def _phase_line(
        self, phase: Phase, done: int, total: int, label: str | None = None
    ) -> str:
        """What the status bar says mid-run: the phase, the count, and where it is."""
        line = f"{PHASE_TITLES[phase]}: {done} de {total}"

        return f"{line} · {label}" if label else line

    # ── What comes back ──────────────────────────────────────────────────────
    def _on_searched(self, result: SearchResult) -> None:
        self._result = result

        _fill(self.vacancies_table, VACANCY_COLUMNS, result.vacancies)
        _fill(self.appointments_table, APPOINTMENT_COLUMNS, result.appointments)

        self._set_idle(message=self._summary(result))

    def _on_refreshed(self, total: int) -> None:
        """Forget what was on screen, because it is about an older snapshot.

        Refreshing exists for when the site has published something new, so the
        rows from before are answers to the same question asked of different
        data. Leaving them up, exportable, would be the one way to end up with a
        file the user believes is current and is not.
        """
        self._result = None
        self.vacancies_table.setRowCount(0)
        self.appointments_table.setRowCount(0)

        self._set_idle(message=f"{total} vacantes publicadas. Haga una búsqueda.")

    def _on_failed(self, error: Exception) -> None:
        """Say in Spanish that it did not work, and leave the why to the log.

        The exception message is English, and a window is not where English
        belongs. The worker has already logged it with its traceback.
        """
        logger.warning("Showing the user that the run failed: %s", error)
        self._set_idle(message=FAILURE_MESSAGE)

    def _summary(self, result: SearchResult) -> str:
        """What a finished search amounts to, in one line.

        The counts are worth saying out loud because a result can be legitimately
        empty on either side: a specialty nobody has published, or a batch of
        vacancies nobody has been appointed to yet.
        """
        parts = [
            f"{len(result.vacancies)} vacantes",
            f"{len(result.appointments)} nombramientos",
        ]

        if result.failed:
            parts.append(f"{len(result.failed)} sin respuesta")

        return ", ".join(parts) + "."

    # ── Exporting ────────────────────────────────────────────────────────────
    def export(self) -> None:
        """Write the workbook, and say where it went.

        On the interface thread, unlike a search: writing fifty rows takes
        milliseconds, so a thread would cost more in machinery than it saves in
        responsiveness.
        """
        if self._result is None:
            return

        include_personal = self.personal_data.isChecked()

        try:
            path = export_data_to_excel(
                self._result.vacancies,
                self._result.appointments,
                filename_prefix(self._specialty),
                include_personal=include_personal,
            )

        except OSError:
            logger.exception("The workbook could not be written")
            self.statusBar().showMessage(EXPORT_FAILURE_MESSAGE)
            return

        if path is None:
            self.statusBar().showMessage("No hay nada que exportar.")
            return

        logger.info("Workbook written to %s", path)
        self.statusBar().showMessage(f"Archivo generado: {path}")

    # ── Busy or not ──────────────────────────────────────────────────────────
    def _set_busy(self, *, message: str) -> None:
        """Stop a second run from being asked for while one is going.

        The worker refuses one anyway, by raising, which is right for a
        programming mistake and wrong as something a user can trigger by
        double-clicking.
        """
        self._enable_controls(enabled=False)

        # No total yet: the first phase cannot report one until it has read the
        # dropdown, and a range of nothing is how Qt draws a busy indicator.
        self.progress.setRange(0, 0)
        self.progress.show()

        self.statusBar().showMessage(message)

    def _set_idle(self, *, message: str) -> None:
        self._enable_controls(enabled=True)
        self.progress.hide()
        self.statusBar().showMessage(message)

    def _enable_controls(self, *, enabled: bool) -> None:
        for widget in (
            self.specialty,
            self.year,
            self.search_button,
            self.refresh_button,
            self.personal_data,
        ):
            widget.setEnabled(enabled)

        # Exporting needs something to export, which a run in progress and a
        # refresh both leave the window without.
        self.export_button.setEnabled(enabled and self._result is not None)
