"""The application layer's contract, without a browser.

Session sits between an interface and the scrapers, and the GUI in Etapa 9 will
be its second consumer. These tests fix what a consumer can rely on: when
scraping happens, when it does not, and what a filtered search does to the
cache.

Both scrapers are replaced by doubles that record how they were called. The
doubles are installed on the module attributes rather than injected, so the
production signature stays the one real callers need. An import that stops
resolving makes monkeypatch raise, which is the loud failure we want.
"""

import pytest

from consulta_vacantes_mep.app import session as session_module
from consulta_vacantes_mep.app.session import SearchResult, Session
from consulta_vacantes_mep.events import NullReporter, Reporter
from consulta_vacantes_mep.models import (
    Appointment,
    AppointmentQuery,
    QueryOutcome,
    Vacancy,
)


def _vacancy(number: str, specialty: str) -> Vacancy:
    """A vacancy varying only in the two fields these tests care about."""
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


# Real vacancy numbers, so a failure reads like the runs it stands in for.
PUBLISHED = [
    _vacancy("1531185", "Francés"),
    _vacancy("1536996", "Francés"),
    _vacancy("1538058", "Matemática"),
]


class FakeVacancyScraper:
    """Stands in for scrape_all_vacancies and records how it was called."""

    def __init__(self, vacancies: list[Vacancy]) -> None:
        self._vacancies = vacancies
        self.calls = 0
        self.headless: bool | None = None
        self.reporter: Reporter | None = None

    def __call__(
        self, headless: bool = True, reporter: Reporter | None = None
    ) -> list[Vacancy]:
        self.calls += 1
        self.headless = headless
        self.reporter = reporter

        # A fresh list per call, as the real scraper builds. Handing back the
        # same one would let a test pass because two names point at one object.
        return list(self._vacancies)


class FakeAppointmentScraper:
    """Stands in for scrape_appointments_for_vacancies."""

    def __init__(self, queries: list[AppointmentQuery] | None = None) -> None:
        self._queries = queries or []
        self.calls = 0
        self.vacancies: list[Vacancy] = []
        self.year: int | None = None
        self.headless: bool | None = None
        self.reporter: Reporter | None = None

    def __call__(
        self,
        vacancies: list[Vacancy],
        year: int,
        headless: bool = True,
        reporter: Reporter | None = None,
    ) -> list[AppointmentQuery]:
        self.calls += 1
        self.vacancies = list(vacancies)
        self.year = year
        self.headless = headless
        self.reporter = reporter
        return list(self._queries)


@pytest.fixture
def vacancy_scraper(monkeypatch: pytest.MonkeyPatch) -> FakeVacancyScraper:
    fake = FakeVacancyScraper(PUBLISHED)
    monkeypatch.setattr(session_module, "scrape_all_vacancies", fake)
    return fake


@pytest.fixture
def appointment_scraper(monkeypatch: pytest.MonkeyPatch) -> FakeAppointmentScraper:
    fake = FakeAppointmentScraper()
    monkeypatch.setattr(session_module, "scrape_appointments_for_vacancies", fake)
    return fake


# ── The cache ─────────────────────────────────────────────────────────────────
def test_nothing_is_scraped_until_something_is_asked_for(
    vacancy_scraper: FakeVacancyScraper,
) -> None:
    session = Session()

    assert session.cached_count is None
    assert vacancy_scraper.calls == 0


def test_vacancies_are_scraped_once_and_reused(
    vacancy_scraper: FakeVacancyScraper,
) -> None:
    """Scraping every regional office takes about half a minute."""
    session = Session()

    session.vacancies()
    session.vacancies()

    assert vacancy_scraper.calls == 1
    assert session.cached_count == len(PUBLISHED)


def test_filtering_does_not_replace_the_cache(
    vacancy_scraper: FakeVacancyScraper,
) -> None:
    """The one that would bite silently.

    If the filtered list were stored, the second search would run against two
    French vacancies and report that no Matemática vacancy is published. The
    run would look complete and be wrong, which is exactly how the regional
    office grid race stayed invisible.
    """
    session = Session()

    french = session.vacancies("Francés")
    maths = session.vacancies("Matemática")

    assert [v.number for v in french] == ["1531185", "1536996"]
    assert [v.number for v in maths] == ["1538058"]
    assert session.cached_count == len(PUBLISHED)
    assert vacancy_scraper.calls == 1


def test_an_empty_specialty_means_every_vacancy(
    vacancy_scraper: FakeVacancyScraper,
) -> None:
    session = Session()

    assert session.vacancies("") == PUBLISHED
    assert vacancy_scraper.calls == 1


def test_refresh_scrapes_again(vacancy_scraper: FakeVacancyScraper) -> None:
    """The site publishes a different set from one hour to the next."""
    session = Session()

    session.vacancies()
    session.vacancies(refresh=True)

    assert vacancy_scraper.calls == 2


# ── What reaches the scrapers ─────────────────────────────────────────────────
def test_search_queries_only_the_matching_vacancies(
    vacancy_scraper: FakeVacancyScraper,
    appointment_scraper: FakeAppointmentScraper,
) -> None:
    session = Session()

    session.search(2026, "Matemática")

    assert [v.number for v in appointment_scraper.vacancies] == ["1538058"]
    assert vacancy_scraper.calls == 1


def test_search_returns_the_vacancies_it_queried(
    vacancy_scraper: FakeVacancyScraper,
    appointment_scraper: FakeAppointmentScraper,
) -> None:
    session = Session()

    result = session.search(2026, "Francés")

    assert [v.number for v in result.vacancies] == ["1531185", "1536996"]
    assert appointment_scraper.calls == 1
    assert vacancy_scraper.calls == 1


def test_the_query_year_is_passed_through(
    vacancy_scraper: FakeVacancyScraper,
    appointment_scraper: FakeAppointmentScraper,
) -> None:
    session = Session()

    session.search(2025)

    assert appointment_scraper.year == 2025
    assert vacancy_scraper.calls == 1


def test_the_reporter_reaches_both_scrapers(
    vacancy_scraper: FakeVacancyScraper,
    appointment_scraper: FakeAppointmentScraper,
) -> None:
    """Etapa 9 hangs a Qt signal off this."""
    reporter = NullReporter()
    session = Session(reporter=reporter)

    session.search(2026)

    assert vacancy_scraper.reporter is reporter
    assert appointment_scraper.reporter is reporter


def test_the_headless_flag_reaches_both_scrapers(
    vacancy_scraper: FakeVacancyScraper,
    appointment_scraper: FakeAppointmentScraper,
) -> None:
    session = Session(headless=False)

    session.search(2026)

    assert vacancy_scraper.headless is False
    assert appointment_scraper.headless is False


# ── SearchResult ──────────────────────────────────────────────────────────────
def test_appointments_are_flattened_across_queries() -> None:
    result = SearchResult(
        vacancies=PUBLISHED,
        queries=[
            AppointmentQuery("1531185", QueryOutcome.EMPTY, []),
            AppointmentQuery("1536996", QueryOutcome.FOUND, [_appointment("1536996")]),
            AppointmentQuery(
                "1538058",
                QueryOutcome.FOUND,
                [_appointment("1538058"), _appointment("1538058")],
            ),
        ],
    )

    assert [a.vacancy_number for a in result.appointments] == [
        "1536996",
        "1538058",
        "1538058",
    ]


def test_failed_excludes_queries_that_simply_found_nothing() -> None:
    """A vacancy nobody was appointed to is a result. A query that never ran is not."""
    result = SearchResult(
        vacancies=PUBLISHED,
        queries=[
            AppointmentQuery("1531185", QueryOutcome.EMPTY, []),
            AppointmentQuery("1536996", QueryOutcome.FAILED, [], "timeout"),
        ],
    )

    assert [q.vacancy_number for q in result.failed] == ["1536996"]
