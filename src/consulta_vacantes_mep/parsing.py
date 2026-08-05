"""Table parsing for the two MEP pages.

Cells on both sites carry an attribute naming their column: data-label on the
Blazor vacancies grid, data-title on the WebForms appointments grid. Parsing by
that attribute rather than by position makes extraction immune to added,
reordered, or hidden columns.

Cell text is read with text_content() rather than inner_text(): the vacancies
grid applies a CSS text transform, so the rendered text differs from the value
the site actually published.
"""

import re

from playwright.sync_api import Locator

from consulta_vacantes_mep.labels import APPOINTMENT_LABELS, VACANCY_LABELS
from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.settings import SCRAPING
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)

VACANCIES_TABLE_SELECTOR = "table.mud-table-root"
APPOINTMENTS_TABLE_SELECTOR = "#grvNombramientos"

VACANCY_CELL_ATTRIBUTE = "data-label"
APPOINTMENT_CELL_ATTRIBUTE = "data-title"

_WHITESPACE = re.compile(r"\s+")


def clean(text: str | None) -> str:
    """Collapse whitespace and trim.

    Source values carry trailing padding, doubled spaces, and non-breaking
    spaces. Python's strip treats U+00A0 as whitespace, so a single pass
    handles all three.
    """
    if not text:
        return ""

    return _WHITESPACE.sub(" ", text).strip()


def _row_by_column_attribute(row: Locator, attribute: str) -> dict[str, str]:
    """Map a row's cells to their declared column names."""
    cells = row.locator(f"td[{attribute}]")
    values: dict[str, str] = {}

    for i in range(cells.count()):
        cell = cells.nth(i)
        column = cell.get_attribute(attribute, timeout=SCRAPING.cell_timeout_ms)

        if column:
            values[clean(column)] = clean(cell.text_content())

    return values


def _build(model, labels: dict[str, str], values: dict[str, str], context: str):
    """Instantiate a model from label-keyed values, or return None with a reason."""
    missing = [label for label in labels.values() if label not in values]

    if missing:
        logger.warning(
            "%s: discarding row, missing columns: %s", context, ", ".join(missing)
        )
        return None

    return model(**{field: values[label] for field, label in labels.items()})


def parse_vacancies(table: Locator, regional_office: str) -> list[Vacancy]:
    """Extract vacancies from one regional office's results grid."""
    rows = table.locator("tbody tr")
    vacancies: list[Vacancy] = []

    for i in range(rows.count()):
        values = _row_by_column_attribute(rows.nth(i), VACANCY_CELL_ATTRIBUTE)

        if not values:
            row = rows.nth(i)
            logger.warning(
                "%s: skipping row %d with no labelled cells: %s",
                regional_office,
                i,
                clean(row.evaluate("node => node.outerHTML"))[:300],
            )
            continue

        logger.debug("%s: grid has %d rows", regional_office, rows.count())
        vacancy = _build(Vacancy, VACANCY_LABELS, values, regional_office)

        if vacancy is not None:
            vacancies.append(vacancy)

    return vacancies


def parse_appointments(table: Locator, vacancy_number: str) -> list[Appointment]:
    """Extract appointments from the results grid for one vacancy number."""
    rows = table.locator("tbody tr")
    appointments: list[Appointment] = []

    for i in range(rows.count()):
        values = _row_by_column_attribute(rows.nth(i), APPOINTMENT_CELL_ATTRIBUTE)

        if not values:
            continue

        appointment = _build(
            Appointment, APPOINTMENT_LABELS, values, f"vacancy {vacancy_number}"
        )

        if appointment is not None:
            appointments.append(appointment)

    return appointments
