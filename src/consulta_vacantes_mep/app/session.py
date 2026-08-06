"""One search, whatever the interface asks for it.

The CLI ran the same sequence twice, once per menu option, differing only in
whether a specialty filter was applied in the middle. A GUI would have been a
third copy of it. This module owns the sequence and the vacancy cache, so an
interface is left with what to ask and how to show the answer.
"""

from dataclasses import dataclass

from consulta_vacantes_mep.events import Reporter
from consulta_vacantes_mep.models import Appointment, AppointmentQuery, QueryOutcome, Vacancy
from consulta_vacantes_mep.scrapers.appointments import scrape_appointments_for_vacancies
from consulta_vacantes_mep.scrapers.vacancies import (
    filter_vacancies_by_specialty,
    scrape_all_vacancies,
)
from consulta_vacantes_mep.settings import SCRAPING


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Everything one search produced.

    Both lists are kept rather than only the appointments: a vacancy nobody was
    appointed to is a result in itself, and a query that could not be completed
    has to stay visible instead of looking like an absence of appointments.
    """

    vacancies: list[Vacancy]
    queries: list[AppointmentQuery]

    @property
    def appointments(self) -> list[Appointment]:
        return [
            appointment for query in self.queries for appointment in query.appointments
        ]

    @property
    def failed(self) -> list[AppointmentQuery]:
        return [query for query in self.queries if query.outcome is QueryOutcome.FAILED]


class Session:
    """A run of the tool, holding what has already been scraped.

    Scraping every regional office takes about half a minute, so the result is
    kept for as long as the session lives and reused while the user explores
    different specialties. Nothing is written to disk: the site publishes a
    different set of vacancies from one hour to the next, and a cache that
    outlived the session would hand back results that no longer exist.
    """

    def __init__(
        self, reporter: Reporter | None = None, headless: bool = SCRAPING.headless
    ) -> None:
        self._reporter = reporter
        self._headless = headless
        self._cache: list[Vacancy] | None = None

    @property
    def cached_count(self) -> int | None:
        """How many vacancies are already loaded, or None if none are."""
        return None if self._cache is None else len(self._cache)

    def vacancies(self, *, refresh: bool = False) -> list[Vacancy]:
        """Return every published vacancy, scraping only when needed."""
        if self._cache is None or refresh:
            self._cache = scrape_all_vacancies(
                headless=self._headless, reporter=self._reporter
            )

        return self._cache

    def search(
        self, year: int, specialty: str | None = None, *, refresh: bool = False
    ) -> SearchResult:
        """Look up the appointments recorded against the matching vacancies.

        An empty specialty means every vacancy, which is what the two menu
        options differed on and the only thing they differed on.
        """
        vacancies = self.vacancies(refresh=refresh)

        if specialty:
            vacancies = filter_vacancies_by_specialty(vacancies, specialty)

        queries = scrape_appointments_for_vacancies(
            vacancies, year=year, headless=self._headless, reporter=self._reporter
        )

        return SearchResult(vacancies, queries)
