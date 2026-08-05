from concurrent.futures import ThreadPoolExecutor, as_completed

from playwright.sync_api import Page

from consulta_vacantes_mep.exceptions import (
    PermanentScrapingError,
    ScrapingError,
    TransientScrapingError,
)
from consulta_vacantes_mep.models import (
    Appointment,
    AppointmentQuery,
    QueryOutcome,
    Vacancy,
)
from consulta_vacantes_mep.parsing import APPOINTMENTS_TABLE_SELECTOR, parse_appointments
from consulta_vacantes_mep.retry import with_retry
from consulta_vacantes_mep.scrapers.browser import BrowserPool
from consulta_vacantes_mep.scrapers.errors import classify, detect_challenge
from consulta_vacantes_mep.settings import SCRAPING
from consulta_vacantes_mep.utils.console import clear_screen, print_result, print_section
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)


def _run_query(page: Page, vacancy_number: str, year: int) -> list[Appointment]:
    """Submit one query and read the result grid.

    Raises a ScrapingError subclass on failure. An empty return means the site
    rendered no grid, which is how it reports a vacancy with no appointments.
    """
    try:
        page.goto(
            SCRAPING.appointments_url,
            wait_until="domcontentloaded",
            timeout=SCRAPING.page_load_timeout_ms,
        )
        detect_challenge(page)

        page.wait_for_timeout(SCRAPING.settle_ms)

        page.locator("#radioVacante").check()
        page.locator("#txtCedula").fill(vacancy_number)
        page.locator("#ddlAño").select_option(str(year))
        page.evaluate("__doPostBack('btnConsultar','')")

        page.wait_for_load_state(
            "domcontentloaded", timeout=SCRAPING.postback_timeout_ms
        )
        page.wait_for_timeout(SCRAPING.settle_ms)

        detect_challenge(page)

    except ScrapingError:
        raise
    except Exception as error:
        raise classify(error, f"vacancy {vacancy_number}") from error

    table = page.locator(APPOINTMENTS_TABLE_SELECTOR)

    if table.count() == 0:
        return []

    return parse_appointments(table, vacancy_number)


_run_query_with_retry = with_retry(_run_query)

def _query_appointments(
    pool: BrowserPool, vacancy_number: str, year: int
) -> AppointmentQuery:
    """Look up appointments for one vacancy, reporting why the result is empty."""
    try:
        with pool.page() as page:
            appointments = _run_query_with_retry(page, vacancy_number, year)

    except ScrapingError as error:
        logger.warning("Vacancy %s: query failed (%s)", vacancy_number, error)
        return AppointmentQuery(
            vacancy_number=vacancy_number,
            outcome=QueryOutcome.FAILED,
            appointments=[],
            error=str(error),
        )

    if not appointments:
        logger.info("Vacancy %s: no appointments found.", vacancy_number)
        return AppointmentQuery(vacancy_number, QueryOutcome.EMPTY, [])

    logger.info(
        "Vacancy %s: %d appointments found.", vacancy_number, len(appointments)
    )
    return AppointmentQuery(vacancy_number, QueryOutcome.FOUND, appointments)


# ── Public API ────────────────────────────────────────────────────────────────
def scrape_appointments_for_vacancies(
    vacancies: list[Vacancy],
    year: int,
    headless: bool = SCRAPING.headless,
) -> list[AppointmentQuery]:
    if not vacancies:
        return []

    vacancy_numbers = sorted({v.number for v in vacancies if v.number})
    total = len(vacancy_numbers)

    clear_screen()
    print_section(
        f"Nombramientos MEP — {total} vacantes únicas  ·  "
        f"{SCRAPING.max_concurrency} consultas simultáneas"
    )

    results: list[AppointmentQuery] = []
    pool = BrowserPool(headless=headless)
    pool.start()

    try:
        with ThreadPoolExecutor(max_workers=SCRAPING.max_concurrency) as executor:
            futures = {
                executor.submit(_query_appointments, pool, number, year): number
                for number in vacancy_numbers
            }

            for index, future in enumerate(as_completed(futures), start=1):
                number = futures[future]

                try:
                    query = future.result()

                except PermanentScrapingError as error:
                    logger.exception("Vacancy %s: page structure changed", number)
                    query = AppointmentQuery(number, QueryOutcome.FAILED, [], str(error))

                results.append(query)
                print_result(
                    index,
                    total,
                    number,
                    len(query.appointments)
                    if query.outcome is not QueryOutcome.FAILED
                    else None,
                )

    finally:
        pool.stop()

    found = sum(len(q.appointments) for q in results)
    failed = sum(1 for q in results if q.outcome is QueryOutcome.FAILED)

    if failed:
        print_section(f"Total: {found} nombramientos  ·  {failed} consultas fallidas")
    else:
        print_section(f"Total: {found} nombramientos encontrados.")

    return results


def _submit_query(page: Page, vacancy_number: str, year: int) -> bool:
    """Submit the form and wait for the server's response.

    The previous implementation called wait_for_load_state after triggering the
    postback. That returns as soon as the *current* page is loaded, which it
    already is, so it never actually waited: a fixed sleep was doing the work.
    Waiting on the POST response is a real condition, and its status tells us
    the query ran even when the result is empty.
    """
    page.locator("#radioVacante").check()
    page.locator("#txtCedula").fill(vacancy_number)
    page.locator("#ddlA\u00f1o").select_option(str(year))

    with page.expect_response(
        lambda response: response.request.method == "POST"
        and "consultanombramientos" in response.url.lower(),
        timeout=SCRAPING.postback_timeout_ms,
    ) as response_info:
        page.evaluate("__doPostBack('btnConsultar','')")

    response = response_info.value

    if not response.ok:
        message = f"vacancy {vacancy_number}: server returned {response.status}"
        raise TransientScrapingError(message)

    return True
