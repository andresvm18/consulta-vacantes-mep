"""The workbook the user actually opens.

This is the only module that produces the deliverable, and pandas is coming out
of it in Etapa 8. These tests are the net for that: they describe the workbook,
not how it was built, so a rewrite that keeps the output passes and one that
quietly drops a sheet or a header does not.

Every test writes to a temporary directory. OUTPUT_DIR is read from the module
namespace at call time, so redirecting it there keeps the suite from leaving
files under the working directory.
"""

from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from consulta_vacantes_mep.exports import excel as excel_module
from consulta_vacantes_mep.exports.excel import export_data_to_excel
from consulta_vacantes_mep.labels import (
    APPOINTMENT_LABELS,
    PERSONAL_FIELDS,
    VACANCY_LABELS,
    appointment_labels,
)
from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.settings import EXPORT


def _vacancy(
    number: str,
    specialty: str = "Francés",
    institution: str = "Liceo de Prueba",
) -> Vacancy:
    return Vacancy(
        number=number,
        regional_office="Dirección Regional de Prueba",
        position_class="Profesor de Enseñanza Media",
        specialty=specialty,
        institution=institution,
        lessons="10",
        starts_on="05/08/2026",
        ends_on="31/12/2026",
    )


def _appointment(vacancy_number: str) -> Appointment:
    """An appointment carrying an obviously invented national id.

    Real ones identify a specific person and have no business in a repository.
    """
    return Appointment(
        vacancy_number=vacancy_number,
        national_id="0-0000-0000",
        full_name="Persona De Prueba",
        institution="Liceo de Prueba",
        position_class="Profesor de Enseñanza Media",
        specialty="Francés",
        group="MT 4",
        position_number="0",
        starts_on="05/08/2026",
        ends_on="31/12/2026",
        status="Activo",
        eligibility_rating="0",
        roster_title="Nómina de prueba",
    )


PUBLISHED = [
    _vacancy("1531185"),
    _vacancy("1536996"),
    _vacancy("1538058", "Matemática"),
]


@pytest.fixture(autouse=True)
def output_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(excel_module, "OUTPUT_DIR", tmp_path)
    return tmp_path


def _row(sheet: Worksheet, number: int) -> list[object]:
    return [cell.value for cell in sheet[number]]


def _sheet(path: Path, name: str) -> Worksheet:
    return load_workbook(path)[name]


# ── Nothing to export ─────────────────────────────────────────────────────────
def test_no_vacancies_produces_no_workbook() -> None:
    assert export_data_to_excel([]) is None


def test_no_vacancies_writes_no_file(output_dir: Path) -> None:
    """An empty workbook is worse than no workbook: it looks like an answer."""
    export_data_to_excel([])

    assert list(output_dir.iterdir()) == []


# ── The file ──────────────────────────────────────────────────────────────────
def test_the_workbook_is_written_where_it_was_asked_for(output_dir: Path) -> None:
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    assert path.parent == output_dir
    assert path.exists()


def test_the_filename_carries_the_prefix_it_was_given() -> None:
    path = export_data_to_excel(PUBLISHED, filename_prefix="busqueda")

    assert path is not None
    assert path.name.startswith("busqueda_")
    assert path.suffix == ".xlsx"


def test_the_filename_defaults_to_the_spanish_prefix() -> None:
    """The user reads this one, so it stays in Spanish."""
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    assert path.name.startswith("vacantes_")


def test_the_filename_is_stamped_with_the_time() -> None:
    """Two runs an hour apart must not overwrite each other."""
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    stamp = path.stem.removeprefix("vacantes_")

    assert datetime.strptime(stamp, EXPORT.timestamp_format)  # noqa: DTZ007


# ── The sheets ────────────────────────────────────────────────────────────────
def test_both_sheets_are_always_present() -> None:
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    assert load_workbook(path).sheetnames == ["Vacantes", "Nombramientos"]


def test_the_vacancy_headers_are_the_spanish_labels() -> None:
    """labels.py is the single source of these, and the scrapers match table
    headers on the site against the same strings."""
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    assert _row(_sheet(path, "Vacantes"), 1) == list(VACANCY_LABELS.values())


def test_every_vacancy_gets_a_row() -> None:
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    assert _sheet(path, "Vacantes").max_row == len(PUBLISHED) + 1


def test_a_vacancy_row_holds_its_fields_in_label_order() -> None:
    path = export_data_to_excel([_vacancy("1531185")])

    assert path is not None
    assert _row(_sheet(path, "Vacantes"), 2) == [
        "1531185",
        "Dirección Regional de Prueba",
        "Profesor de Enseñanza Media",
        "Francés",
        "Liceo de Prueba",
        "10",
        "05/08/2026",
        "31/12/2026",
    ]


def test_the_appointment_headers_are_the_spanish_labels() -> None:
    """Minus the identifying ones, which are not written unless asked for."""
    path = export_data_to_excel(PUBLISHED, [_appointment("1531185")])

    assert path is not None
    assert _row(_sheet(path, "Nombramientos"), 1) == list(
        appointment_labels(include_personal=False).values()
    )


def test_every_appointment_gets_a_row() -> None:
    """A vacancy can carry more than one, which is the point of cross-referencing."""
    appointments = [_appointment("1531185"), _appointment("1531185")]

    path = export_data_to_excel(PUBLISHED, appointments)

    assert path is not None
    assert _sheet(path, "Nombramientos").max_row == len(appointments) + 1


def test_an_appointments_sheet_with_nothing_in_it_still_names_its_columns() -> None:
    """A search can legitimately find vacancies nobody has been appointed to.

    That result has to look like an empty table rather than a damaged file, so
    the headings are written whether or not there is anything under them.
    """
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    assert _row(_sheet(path, "Nombramientos"), 1) == list(
        appointment_labels(include_personal=False).values()
    )


def test_an_empty_appointments_sheet_holds_only_its_headers() -> None:
    """Headings without rows, not a blank row pretending to be an appointment."""
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    assert _sheet(path, "Nombramientos").max_row == 1


# ── Personal data ─────────────────────────────────────────────────────────────
PERSONAL_HEADINGS = [APPOINTMENT_LABELS[field] for field in PERSONAL_FIELDS]


def test_the_identifying_columns_are_absent_by_default() -> None:
    """A workbook is a file that gets forwarded, so it does not carry these
    unless the person exporting it said so."""
    path = export_data_to_excel(PUBLISHED, [_appointment("1531185")])

    assert path is not None
    headings = _row(_sheet(path, "Nombramientos"), 1)

    assert not set(headings) & set(PERSONAL_HEADINGS)


def test_the_identifying_values_are_absent_by_default() -> None:
    """Dropping the headings is not enough if the values are still in the row."""
    path = export_data_to_excel(PUBLISHED, [_appointment("1531185")])

    assert path is not None
    written = {
        cell.value
        for row in _sheet(path, "Nombramientos").iter_rows()
        for cell in row
    }

    assert "0-0000-0000" not in written
    assert "Persona De Prueba" not in written


def test_the_identifying_columns_are_written_when_asked_for() -> None:
    path = export_data_to_excel(
        PUBLISHED, [_appointment("1531185")], include_personal=True
    )

    assert path is not None
    assert _row(_sheet(path, "Nombramientos"), 1) == list(APPOINTMENT_LABELS.values())


def test_the_identifying_values_are_written_when_asked_for() -> None:
    path = export_data_to_excel(
        PUBLISHED, [_appointment("1531185")], include_personal=True
    )

    assert path is not None
    row = _row(_sheet(path, "Nombramientos"), 2)

    assert row[1] == "0-0000-0000"
    assert row[2] == "Persona De Prueba"


def test_the_remaining_columns_survive_the_redaction() -> None:
    """Everything the registry answers except who: a workbook that lost the
    vacancy number or the dates would be useless rather than private."""
    path = export_data_to_excel(PUBLISHED, [_appointment("1531185")])

    assert path is not None
    headings = _row(_sheet(path, "Nombramientos"), 1)

    assert len(headings) == len(APPOINTMENT_LABELS) - len(PERSONAL_FIELDS)
    assert headings[0] == "Vacante"


def test_a_redacted_row_still_lines_up_with_its_headers() -> None:
    """Dropping two columns from the middle is where an export silently shifts
    every value one cell to the left."""
    path = export_data_to_excel(PUBLISHED, [_appointment("1531185")])

    assert path is not None
    sheet = _sheet(path, "Nombramientos")
    headings = _row(sheet, 1)
    values = _row(sheet, 2)

    assert dict(zip(headings, values, strict=True)) == {
        "Vacante": "1531185",
        "Institución": "Liceo de Prueba",
        "Clase Puesto": "Profesor de Enseñanza Media",
        "Especialidad": "Francés",
        "Grupo": "MT 4",
        "N° Puesto": "0",
        "Rige": "05/08/2026",
        "Vence": "31/12/2026",
        "Estado": "Activo",
        "Calificación R. Elegibles": "0",
        "Título Nómina": "Nómina de prueba",
    }


def test_the_vacancies_sheet_is_untouched_by_the_setting() -> None:
    """Vacancies name a post, not a person, so nothing there is redacted."""
    with_personal = export_data_to_excel(PUBLISHED, None, include_personal=True)
    without = export_data_to_excel(PUBLISHED, None, include_personal=False)

    assert with_personal is not None
    assert without is not None
    assert _row(_sheet(with_personal, "Vacantes"), 1) == _row(
        _sheet(without, "Vacantes"), 1
    )


# ── The formatting ────────────────────────────────────────────────────────────
def test_the_header_row_is_filled_and_bold() -> None:
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    header = _sheet(path, "Vacantes")["A1"]

    # openpyxl reports colours with an alpha channel the settings do not carry.
    assert header.fill.start_color.rgb.endswith(EXPORT.header_fill_color)
    assert header.font.color.rgb.endswith(EXPORT.header_font_color)
    assert header.font.bold is True
    assert header.alignment.horizontal == "center"


def test_the_body_is_not_styled_like_the_header() -> None:
    path = export_data_to_excel(PUBLISHED)

    assert path is not None

    assert _sheet(path, "Vacantes")["A2"].font.bold is not True


def test_the_header_row_stays_visible_while_scrolling() -> None:
    """Fifty rows of vacancies are unreadable without it."""
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    assert _sheet(path, "Vacantes").freeze_panes == "A2"


def test_the_columns_can_be_filtered() -> None:
    path = export_data_to_excel(PUBLISHED)

    assert path is not None
    sheet = _sheet(path, "Vacantes")

    assert sheet.auto_filter.ref == sheet.dimensions


def test_a_long_value_does_not_widen_a_column_without_limit() -> None:
    """Institution names run long, and one of them should not push every other
    column off the screen."""
    path = export_data_to_excel([_vacancy("1531185", institution="Liceo " + "muy largo " * 20)])

    assert path is not None
    widths = _sheet(path, "Vacantes").column_dimensions

    assert widths["E"].width == EXPORT.max_column_width
