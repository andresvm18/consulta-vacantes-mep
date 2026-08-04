"""Parser behavior against real HTML captured from the MEP sites."""

from playwright.sync_api import Page

from consulta_vacantes_mep.parsing import (
    APPOINTMENTS_TABLE_SELECTOR,
    VACANCIES_TABLE_SELECTOR,
    clean,
    parse_appointments,
    parse_vacancies,
)


def test_clean_collapses_whitespace_and_nbsp() -> None:
    assert clean("  MT 4  ") == "MT 4"
    assert clean("\u00a0MT 4") == "MT 4"
    assert clean("Profesor de   Enseñanza Media   ") == "Profesor de Enseñanza Media"
    assert clean(None) == ""


def test_parses_appointment_row(load_fixture) -> None:
    page: Page = load_fixture("appointments_table.html")
    table = page.locator(APPOINTMENTS_TABLE_SELECTOR)

    appointments = parse_appointments(table, "1536996")

    assert len(appointments) == 1

    appointment = appointments[0]
    assert appointment.vacancy_number == "1536996"
    assert appointment.specialty == "Francés"
    assert appointment.group == "MT 4"
    assert appointment.position_number == "0"
    assert appointment.starts_on == "03/08/2026"
    assert appointment.status == "Activo"
    assert appointment.roster_title.endswith("Reclutamiento Insuficiente")


def test_appointment_padding_is_trimmed(load_fixture) -> None:
    """The source pads position class with dozens of trailing spaces."""
    page: Page = load_fixture("appointments_table.html")
    table = page.locator(APPOINTMENTS_TABLE_SELECTOR)

    appointment = parse_appointments(table, "1536996")[0]

    assert appointment.position_class == "Profesor de Enseñanza Media (G. de E.)"


def test_empty_result_page_has_no_table(load_fixture) -> None:
    page: Page = load_fixture("appointments_empty.html")

    assert page.locator(APPOINTMENTS_TABLE_SELECTOR).count() == 0


def test_parses_vacancy_rows(load_fixture) -> None:
    page: Page = load_fixture("vacancies_table.html")
    table = page.locator(VACANCIES_TABLE_SELECTOR)

    vacancies = parse_vacancies(table, "Administracion Regional Del Sist. Educ.")

    assert len(vacancies) > 0

    first = vacancies[0]
    assert first.number == "1531185"
    assert first.starts_on == "05/08/2026"
    assert first.lessons == "0"


def test_vacancy_hidden_columns_are_excluded(load_fixture) -> None:
    """Each row carries two hidden cells with no data-label attribute."""
    page: Page = load_fixture("vacancies_table.html")
    table = page.locator(VACANCIES_TABLE_SELECTOR)

    vacancies = parse_vacancies(table, "test")

    # Nothing should have picked up the hidden 60 / 09600 values.
    for vacancy in vacancies:
        assert vacancy.ends_on not in {"60", "09600"}
        assert vacancy.lessons != "09600"


def test_vacancy_text_matches_the_dom_not_the_aria_label(load_fixture) -> None:
    """The source capitalizes cell text server-side; aria-label keeps the original.

    We extract the visible cell text, which is what the site publishes in the
    table. Recording the difference here so a future change in either place is
    caught by the suite.
    """
    page: Page = load_fixture("vacancies_table.html")
    table = page.locator(VACANCIES_TABLE_SELECTOR)

    vacancies = parse_vacancies(table, "test")
    classes = [v.position_class for v in vacancies]

    assert any("De Servicio Civil" in c for c in classes)
    assert not any("de Servicio Civil" in c for c in classes)


def test_parse_appointments_on_missing_table_returns_empty(load_fixture) -> None:
    """The parser must not raise when the grid was never rendered."""
    page: Page = load_fixture("appointments_empty.html")
    table = page.locator(APPOINTMENTS_TABLE_SELECTOR)

    assert parse_appointments(table, "1538058") == []
