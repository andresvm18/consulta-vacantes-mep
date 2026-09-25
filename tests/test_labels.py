"""The Spanish labels, and which of them name a person.

Nothing here touches a browser or a file. The module is a mapping and two
functions, but it is the one place that decides what a workbook is allowed to
carry, so the decisions are worth pinning down.
"""

from dataclasses import fields

import pytest

from consulta_vacantes_mep.labels import (
    APPOINTMENT_LABELS,
    PERSONAL_FIELDS,
    VACANCY_LABELS,
    appointment_labels,
    appointment_to_row,
    vacancy_to_row,
)
from consulta_vacantes_mep.models import Appointment, Vacancy

APPOINTMENT = Appointment(
    vacancy_number="1531185",
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

VACANCY = Vacancy(
    number="1531185",
    regional_office="Dirección Regional de Prueba",
    position_class="Profesor de Enseñanza Media",
    specialty="Francés",
    institution="Liceo de Prueba",
    lessons="10",
    starts_on="05/08/2026",
    ends_on="31/12/2026",
)


# ── The labels cover the models ───────────────────────────────────────────────
@pytest.mark.parametrize(
    ("model", "labels"),
    [(Vacancy, VACANCY_LABELS), (Appointment, APPOINTMENT_LABELS)],
)
def test_every_model_field_has_a_label(
    model: type, labels: dict[str, str]
) -> None:
    """A field added to a model without a label would vanish from the export."""
    assert {f.name for f in fields(model)} == set(labels)


# ── Which fields name a person ────────────────────────────────────────────────
def test_the_personal_fields_exist_on_the_model() -> None:
    """A typo here would redact nothing at all, silently."""
    assert PERSONAL_FIELDS.issubset({f.name for f in fields(Appointment)})


def test_the_personal_fields_are_the_identifying_ones() -> None:
    assert set(PERSONAL_FIELDS) == {"national_id", "full_name"}


# ── Selecting the labels ──────────────────────────────────────────────────────
def test_asking_for_personal_data_returns_every_label() -> None:
    assert appointment_labels(include_personal=True) == APPOINTMENT_LABELS


def test_the_identifying_labels_are_dropped_otherwise() -> None:
    assert set(appointment_labels(include_personal=False)) == (
        set(APPOINTMENT_LABELS) - PERSONAL_FIELDS
    )


def test_the_surviving_labels_keep_their_order() -> None:
    """The heading row and the rows under it are built from separate calls, so
    a reordering here would misalign every value in the sheet."""
    kept = [f for f in APPOINTMENT_LABELS if f not in PERSONAL_FIELDS]

    assert list(appointment_labels(include_personal=False)) == kept


def test_the_returned_mapping_is_not_the_stored_one() -> None:
    """Handing out the module-level dict would let a caller edit the source of
    truth for every other caller."""
    returned = appointment_labels(include_personal=True)
    returned["vacancy_number"] = "Cambiado"

    assert APPOINTMENT_LABELS["vacancy_number"] == "Vacante"


# ── Building a row ────────────────────────────────────────────────────────────
def test_a_row_is_keyed_by_the_spanish_labels() -> None:
    row = appointment_to_row(APPOINTMENT, include_personal=True)

    assert row["Vacante"] == "1531185"
    assert row["Cédula"] == "0-0000-0000"
    assert row["Título Nómina"] == "Nómina de prueba"


def test_a_row_leaves_out_personal_data_by_default() -> None:
    """The default is the safe one: a caller that forgets to decide gets a row
    it can hand to anyone."""
    row = appointment_to_row(APPOINTMENT)

    assert "Cédula" not in row
    assert "Nombre" not in row


def test_a_redacted_row_keeps_everything_else() -> None:
    row = appointment_to_row(APPOINTMENT)

    assert row["Vacante"] == "1531185"
    assert row["Especialidad"] == "Francés"
    assert row["Estado"] == "Activo"


def test_a_vacancy_row_is_keyed_by_the_spanish_labels() -> None:
    """Vacancies name a post, not a person, so there is nothing to redact."""
    assert vacancy_to_row(VACANCY) == {
        "Vacante": "1531185",
        "Dirección Regional": "Dirección Regional de Prueba",
        "Clase de Puesto": "Profesor de Enseñanza Media",
        "Especialidad": "Francés",
        "Institución": "Liceo de Prueba",
        "Lecciones": "10",
        "Rige": "05/08/2026",
        "Vence": "31/12/2026",
    }
