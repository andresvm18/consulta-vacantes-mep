"""The workbook the user opens at the end of a run.

Written with openpyxl directly. The previous version built two pandas frames
and handed them to an ExcelWriter that used openpyxl underneath anyway, so
pandas was doing one job here: turning a list of dicts into rows. It cost the
frozen build roughly a hundred megabytes, since it drags in NumPy, and every
sheet was already being reopened afterwards to be formatted by hand.

Sheets are written even when they have nothing in them. A run that finds
vacancies nobody was appointed to is a result, and it has to look like an empty
table rather than a damaged file.
"""

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from consulta_vacantes_mep.labels import (
    APPOINTMENT_LABELS,
    VACANCY_LABELS,
    appointment_to_row,
    vacancy_to_row,
)
from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.settings import EXPORT
from consulta_vacantes_mep.utils.logger import get_logger
from consulta_vacantes_mep.utils.paths import OUTPUT_DIR

logger = get_logger(__name__)


def format_worksheet(worksheet: Worksheet) -> None:
    """Style the heading row and size the columns to their contents."""
    header_fill = PatternFill(
        start_color=EXPORT.header_fill_color,
        end_color=EXPORT.header_fill_color,
        fill_type="solid",
    )

    header_font = Font(
        color=EXPORT.header_font_color,
        bold=True
    )

    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    # The index comes from the enumeration rather than from the first cell:
    # openpyxl types a cell's column as possibly absent, and both sheets are
    # written from A1, so the nth column read is the nth column of the sheet.
    for index, column_cells in enumerate(worksheet.columns, start=1):
        max_length = 0
        column_letter = get_column_letter(index)

        for cell in column_cells:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))

        adjusted_width = min(max_length + 2, EXPORT.max_column_width)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def _write_sheet(
    worksheet: Worksheet, labels: dict[str, str], rows: list[dict[str, str]]
) -> None:
    """Fill one sheet with a heading row and the rows under it.

    The headings come from the labels rather than from the rows, so a sheet
    with nothing to show still names its columns.
    """
    headings = list(labels.values())
    worksheet.append(headings)

    for row in rows:
        worksheet.append([row[heading] for heading in headings])


def export_data_to_excel(
    vacancies: list[Vacancy],
    appointments: list[Appointment] | None = None,
    filename_prefix: str = "vacantes",
) -> Path | None:
    """Write both sheets to a timestamped workbook, or nothing at all.

    Returns the path written, or None when there was nothing to write: an empty
    workbook is worse than no workbook, because it looks like an answer.
    """
    if not vacancies:
        logger.warning("No vacancies to export; skipping workbook creation.")
        return None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().astimezone().strftime(EXPORT.timestamp_format)
    filename = f"{filename_prefix}_{timestamp}.xlsx"
    file_path = OUTPUT_DIR / filename

    workbook = Workbook()

    # A new workbook arrives with one sheet already in it. Dropping it and
    # creating both by name keeps the two symmetrical, and openpyxl types the
    # active sheet as possibly absent and possibly a chartsheet, which it is
    # neither of here.
    workbook.remove(workbook.worksheets[0])
    vacancies_sheet = workbook.create_sheet("Vacantes")
    appointments_sheet = workbook.create_sheet("Nombramientos")

    _write_sheet(
        vacancies_sheet, VACANCY_LABELS, [vacancy_to_row(v) for v in vacancies]
    )
    _write_sheet(
        appointments_sheet,
        APPOINTMENT_LABELS,
        [appointment_to_row(a) for a in appointments or []],
    )

    for worksheet in workbook.worksheets:
        format_worksheet(worksheet)

    workbook.save(file_path)

    return file_path
