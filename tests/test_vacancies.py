"""Filtering published vacancies by specialty.

The specialty is typed by hand in the interface, so the filter normalizes both
sides: lowercase, and accents decomposed and dropped. Nobody searching for
French is going to reach for the acute accent.

This is worth pinning because the failure is silent. A filter that stopped
normalizing would not raise, it would return nothing, and nothing is a
plausible answer on a site whose dropdown only lists offices that have
vacancies at all.
"""

from consulta_vacantes_mep.models import Vacancy
from consulta_vacantes_mep.scrapers.vacancies import filter_vacancies_by_specialty


def _vacancy(number: str, specialty: str) -> Vacancy:
    return Vacancy(
        number=number,
        regional_office="Dirección Regional de Prueba",
        position_class="Profesor de Enseñanza Media",
        specialty=specialty,
        institution="Liceo de Prueba",
        lessons="10",
        starts_on="05/08/2026",
        ends_on="31/12/2026",
    )


# Specialties as the site publishes them, capitalization included.
PUBLISHED = [
    _vacancy("1531185", "Francés"),
    _vacancy("1536996", "Francés"),
    _vacancy("1538058", "Matemática"),
    _vacancy("1540001", "Educación Física"),
]


def _numbers(vacancies: list[Vacancy]) -> list[str]:
    return [v.number for v in vacancies]


def test_an_exact_specialty_matches() -> None:
    found = filter_vacancies_by_specialty(PUBLISHED, "Francés")

    assert _numbers(found) == ["1531185", "1536996"]


def test_case_is_ignored() -> None:
    found = filter_vacancies_by_specialty(PUBLISHED, "FRANCÉS")

    assert _numbers(found) == ["1531185", "1536996"]


def test_a_missing_accent_still_matches() -> None:
    """The one the interface depends on, since the user types this."""
    found = filter_vacancies_by_specialty(PUBLISHED, "frances")

    assert _numbers(found) == ["1531185", "1536996"]


def test_an_accent_the_source_does_not_carry_still_matches() -> None:
    """Normalizing one side only would fail here."""
    found = filter_vacancies_by_specialty(PUBLISHED, "matemática")

    assert _numbers(found) == ["1538058"]


def test_surrounding_whitespace_is_ignored() -> None:
    """The CLI strips its input, but the filter should not depend on that."""
    found = filter_vacancies_by_specialty(PUBLISHED, "  Francés  ")

    assert _numbers(found) == ["1531185", "1536996"]


def test_a_partial_specialty_matches() -> None:
    """Substring matching, so a half-remembered name still finds something."""
    found = filter_vacancies_by_specialty(PUBLISHED, "física")

    assert _numbers(found) == ["1540001"]


def test_a_specialty_nobody_published_finds_nothing() -> None:
    assert filter_vacancies_by_specialty(PUBLISHED, "Astrofísica") == []


def test_filtering_an_empty_list_finds_nothing() -> None:
    assert filter_vacancies_by_specialty([], "Francés") == []


def test_the_source_list_is_left_alone() -> None:
    """Session hands its cache to this and keeps using it afterwards."""
    filter_vacancies_by_specialty(PUBLISHED, "Francés")

    assert len(PUBLISHED) == 4
