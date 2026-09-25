"""Spanish labels for domain fields.

This is the only place where user-facing column names are defined. The scrapers
also use these labels to match table headers on the source site, which is why
the strings must match the site exactly, accents included.
"""

from consulta_vacantes_mep.models import Appointment, Vacancy

VACANCY_LABELS: dict[str, str] = {
    "number": "Vacante",
    "regional_office": "Dirección Regional",
    "position_class": "Clase de Puesto",
    "specialty": "Especialidad",
    "institution": "Institución",
    "lessons": "Lecciones",
    "starts_on": "Rige",
    "ends_on": "Vence",
}

APPOINTMENT_LABELS: dict[str, str] = {
    "vacancy_number": "Vacante",
    "national_id": "Cédula",
    "full_name": "Nombre",
    "institution": "Institución",
    "position_class": "Clase Puesto",
    "specialty": "Especialidad",
    "group": "Grupo",
    "position_number": "N° Puesto",
    "starts_on": "Rige",
    "ends_on": "Vence",
    "status": "Estado",
    "eligibility_rating": "Calificación R. Elegibles",
    "roster_title": "Título Nómina",
}


# The appointment fields that identify a specific person. Named here rather
# than at each call site so that adding a field to the model is a decision
# about this set, not something that leaks by default.
PERSONAL_FIELDS = frozenset({"national_id", "full_name"})


def appointment_labels(*, include_personal: bool) -> dict[str, str]:
    """The appointment labels, with or without the ones naming a person.

    Order is preserved either way, so a caller can write a heading row and the
    rows under it from the same call and have them line up.
    """
    if include_personal:
        return dict(APPOINTMENT_LABELS)

    return {
        field: label
        for field, label in APPOINTMENT_LABELS.items()
        if field not in PERSONAL_FIELDS
    }


def vacancy_to_row(vacancy: Vacancy) -> dict[str, str]:
    """Convert a vacancy into a Spanish-keyed row for export."""
    return {
        label: getattr(vacancy, field) for field, label in VACANCY_LABELS.items()
    }


def appointment_to_row(
    appointment: Appointment, *, include_personal: bool = False
) -> dict[str, str]:
    """Convert an appointment into a Spanish-keyed row for export.

    Leaves out the identifying columns unless asked for them. The default is
    the safe one on purpose: a caller that forgets to decide gets a row it can
    hand to anyone.
    """
    return {
        label: getattr(appointment, field)
        for field, label in appointment_labels(include_personal=include_personal).items()
    }
