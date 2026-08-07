"""Table parsing for the two MEP pages.

Cells on both sites carry an attribute naming their column: data-label on the
Blazor vacancies grid, data-title on the WebForms appointments grid. Parsing by
that attribute rather than by position makes extraction immune to added,
reordered, or hidden columns.

Cell text is read from textContent rather than rendered text: the vacancies
grid applies a CSS text transform, so what is displayed differs from the value
the site actually published.

The whole table is read in a single evaluation. The previous version walked
locators cell by cell, which made every read a separate round trip against a
DOM that Blazor can re-render between any two of them, so a row could be
counted under one office and read under the next. One snapshot removes the race
instead of narrowing the window it happens in.
"""

import re
from typing import TypedDict, cast

from playwright.sync_api import Locator

from consulta_vacantes_mep.labels import APPOINTMENT_LABELS, VACANCY_LABELS
from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)

VACANCIES_TABLE_SELECTOR = "table.mud-table-root"
APPOINTMENTS_TABLE_SELECTOR = "#grvNombramientos"

VACANCY_CELL_ATTRIBUTE = "data-label"
APPOINTMENT_CELL_ATTRIBUTE = "data-title"

_WHITESPACE = re.compile(r"\s+")


class RowSnapshot(TypedDict):
    """One row as it stood at the instant the snapshot was taken.

    The html is kept so a row that yielded no labelled cells can be reported as
    what it actually was. That is how the transient MudBlazor placeholders were
    identified in the first place.
    """

    values: dict[str, str]
    html: str


class TableSnapshot(TypedDict):
    """A whole grid, plus whether the site is showing only part of it."""

    rows: list[RowSnapshot]
    has_more_pages: bool


# Read in the browser in one pass, so every row comes from the same instant.
# MudBlazor paginates client side, so a Next button that is present and enabled
# means rows exist that this table is not currently showing.
_TABLE_SNAPSHOT = """(tables, attribute) => {
    const table = tables[0];
    if (!table) return { rows: [], has_more_pages: false };

    const rows = Array.from(table.querySelectorAll('tbody tr')).map((row) => {
        const values = {};

        for (const cell of row.querySelectorAll('td[' + attribute + ']')) {
            const column = cell.getAttribute(attribute);
            if (column) values[column] = cell.textContent || '';
        }

        return { values, html: row.outerHTML.slice(0, 300) };
    });

    const wrapper = table.closest('.mud-table');
    const next = wrapper
        ? wrapper.querySelector('.mud-table-pagination button[aria-label="Next page"]')
        : null;

    return { rows, has_more_pages: Boolean(next) && !next.disabled };
}"""


def clean(text: str | None) -> str:
    """Collapse whitespace and trim.

    Source values carry trailing padding, doubled spaces, and non-breaking
    spaces. Python's strip treats U+00A0 as whitespace, so a single pass
    handles all three.
    """
    if not text:
        return ""

    return _WHITESPACE.sub(" ", text).strip()


def _snapshot(table: Locator, attribute: str) -> TableSnapshot:
    """Read the entire table in one round trip.

    evaluate_all rather than evaluate, so a grid that was never rendered comes
    back empty instead of raising. The appointments site renders no table at
    all when a vacancy has no appointments.
    """
    return cast("TableSnapshot", table.evaluate_all(_TABLE_SNAPSHOT, attribute))


def _cleaned(row: RowSnapshot) -> dict[str, str]:
    return {clean(column): clean(value) for column, value in row["values"].items()}


def _build[ModelT: (Vacancy, Appointment)](
    model: type[ModelT],
    labels: dict[str, str],
    values: dict[str, str],
    context: str,
) -> ModelT | None:
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
    snapshot = _snapshot(table, VACANCY_CELL_ATTRIBUTE)
    rows = snapshot["rows"]
    vacancies: list[Vacancy] = []

    logger.debug("%s: grid has %d rows", regional_office, len(rows))

    if snapshot["has_more_pages"]:
        # Never seen on the live site, where every office has fit on one page.
        # Reported rather than paged through: a warning that never fires
        # settles the question for free, and one that does fire says the run is
        # dropping rows, which is worth knowing before writing the code to
        # click through them.
        logger.warning(
            "%s: the grid has more pages; only the first was read", regional_office
        )

    for index, row in enumerate(rows):
        values = _cleaned(row)

        if not values:
            logger.warning(
                "%s: skipping row %d with no labelled cells: %s",
                regional_office,
                index,
                clean(row["html"]),
            )
            continue

        vacancy = _build(Vacancy, VACANCY_LABELS, values, regional_office)

        if vacancy is not None:
            vacancies.append(vacancy)

    return vacancies


def parse_appointments(table: Locator, vacancy_number: str) -> list[Appointment]:
    """Extract appointments from the results grid for one vacancy number."""
    appointments: list[Appointment] = []

    for row in _snapshot(table, APPOINTMENT_CELL_ATTRIBUTE)["rows"]:
        values = _cleaned(row)

        if not values:
            continue

        appointment = _build(
            Appointment, APPOINTMENT_LABELS, values, f"vacancy {vacancy_number}"
        )

        if appointment is not None:
            appointments.append(appointment)

    return appointments
