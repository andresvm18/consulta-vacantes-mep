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
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from consulta_vacantes_mep.app.session import SearchResult
from consulta_vacantes_mep.gui.worker import SearchWorker
from consulta_vacantes_mep.labels import APPOINTMENT_LABELS, VACANCY_LABELS
from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.settings import default_year
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)

WINDOW_TITLE = "Consulta Vacantes MEP"

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

    def __init__(self, worker: SearchWorker) -> None:
        super().__init__()
        self._worker = worker

        self.setWindowTitle(WINDOW_TITLE)
        self._build()

        self._worker.searched.connect(self._on_searched)
        self._worker.refreshed.connect(self._on_refreshed)
        self._worker.failed.connect(self._on_failed)

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
        self.tabs.addTab(self.vacancies_table, "Vacantes")
        self.tabs.addTab(self.appointments_table, "Nombramientos")

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addWidget(self.tabs, stretch=1)

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

        self._set_busy(message="Consultando vacantes y nombramientos...")
        self._worker.search(self.year.value(), specialty)

    def start_refresh(self) -> None:
        """Scrape the vacancy list again, without querying appointments."""
        if self._worker.is_running:
            return

        self._set_busy(message="Actualizando la lista de vacantes...")
        self._worker.refresh()

    # ── What comes back ──────────────────────────────────────────────────────
    def _on_searched(self, result: SearchResult) -> None:
        _fill(self.vacancies_table, VACANCY_COLUMNS, result.vacancies)
        _fill(self.appointments_table, APPOINTMENT_COLUMNS, result.appointments)

        self._set_idle(message=self._summary(result))

    def _on_refreshed(self, total: int) -> None:
        self._set_idle(message=f"{total} vacantes publicadas.")

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

    # ── Busy or not ──────────────────────────────────────────────────────────
    def _set_busy(self, *, message: str) -> None:
        """Stop a second run from being asked for while one is going.

        The worker refuses one anyway, by raising, which is right for a
        programming mistake and wrong as something a user can trigger by
        double-clicking.
        """
        self._enable_controls(enabled=False)
        self.statusBar().showMessage(message)

    def _set_idle(self, *, message: str) -> None:
        self._enable_controls(enabled=True)
        self.statusBar().showMessage(message)

    def _enable_controls(self, *, enabled: bool) -> None:
        for widget in (
            self.specialty,
            self.year,
            self.search_button,
            self.refresh_button,
        ):
            widget.setEnabled(enabled)
