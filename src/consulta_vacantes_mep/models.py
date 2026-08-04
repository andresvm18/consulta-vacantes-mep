"""Domain records produced by the scrapers.

Field names are English snake_case and are the only identifiers used inside the
application. The Spanish labels shown to users live in labels.py, so renaming a
report heading never breaks the logic that reads the data.

Every field is a string. The source publishes dates in an unspecified format
and numbers as free text, so parsing them into richer types would mean guessing.
The scrapers record what the site published; interpretation belongs elsewhere.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vacancy:
    """One open teaching position published by a regional office."""

    number: str
    regional_office: str
    position_class: str
    specialty: str
    institution: str
    lessons: str
    starts_on: str
    ends_on: str


@dataclass(frozen=True, slots=True)
class Appointment:
    """One appointment recorded against a vacancy number.

    Contains personal data: national_id and full_name identify a specific
    person. See NOTICE for the handling policy.
    """

    vacancy_number: str
    national_id: str
    full_name: str
    institution: str
    position_class: str
    specialty: str
    group: str
    position_number: str
    starts_on: str
    ends_on: str
    status: str
    eligibility_rating: str
    roster_title: str
