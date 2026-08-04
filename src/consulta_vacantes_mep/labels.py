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


def vacancy_to_row(vacancy: Vacancy) -> dict[str, str]:
    """Convert a vacancy into a Spanish-keyed row for export."""
    return {
        label: getattr(vacancy, field) for field, label in VACANCY_LABELS.items()
    }


def appointment_to_row(appointment: Appointment) -> dict[str, str]:
    """Convert an appointment into a Spanish-keyed row for export."""
    return {
        label: getattr(appointment, field)
        for field, label in APPOINTMENT_LABELS.items()
    }
