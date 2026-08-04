from concurrent.futures import ThreadPoolExecutor, as_completed

from playwright.sync_api import sync_playwright

from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.parsing import APPOINTMENTS_TABLE_SELECTOR, parse_appointments
from consulta_vacantes_mep.settings import SCRAPING
from consulta_vacantes_mep.utils.console import clear_screen, print_result, print_section
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)


# ── Extraction ────────────────────────────────────────────────────────────────
def _search_single_appointment(
    vacancy_number: str,
    year: int,
    headless: bool = SCRAPING.headless,
    attempt: int = 1,
) -> list[Appointment]:
    """Fetch appointments for one vacancy number, retrying on failure."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(
                SCRAPING.appointments_url,
                wait_until="domcontentloaded",
                timeout=SCRAPING.page_load_timeout_ms,
            )
            page.wait_for_timeout(SCRAPING.settle_ms)

            page.locator("#radioVacante").check()
            page.locator("#txtCedula").fill(str(vacancy_number))
            page.locator("#ddlAño").select_option(str(year))
            page.evaluate("__doPostBack('btnConsultar','')")

            try:
                page.wait_for_load_state(
                    "domcontentloaded", timeout=SCRAPING.postback_timeout_ms
                )
            except Exception:
                logger.warning(
                    "Vacancy %s: postback did not settle within %dms",
                    vacancy_number,
                    SCRAPING.postback_timeout_ms,
                )

            page.wait_for_timeout(SCRAPING.settle_ms)

            if page.locator(APPOINTMENTS_TABLE_SELECTOR).count() == 0:
                logger.info("Vacancy %s: no appointments found.", vacancy_number)
                return []

            appointments = parse_appointments(
                page.locator(APPOINTMENTS_TABLE_SELECTOR), vacancy_number
            )
            logger.info(
                "Vacancy %s: %d appointments found.", vacancy_number, len(appointments)
            )
            return appointments

        except Exception:
            if attempt < SCRAPING.max_retries:
                logger.warning(
                    "Retry %d/%d for vacancy %s",
                    attempt,
                    SCRAPING.max_retries,
                    vacancy_number,
                )
                browser.close()
                return _search_single_appointment(
                    vacancy_number, year, headless, attempt + 1
                )

            logger.exception(
                "Vacancy %s failed after %d attempts",
                vacancy_number,
                SCRAPING.max_retries,
            )
            raise

        finally:
            browser.close()


# ── Public API ────────────────────────────────────────────────────────────────
def scrape_appointments_for_vacancies(
    vacancies: list[Vacancy],
    year: int,
    headless: bool = SCRAPING.headless,
) -> list[Appointment]:
    if not vacancies:
        return []

    vacancy_numbers = list({v.number for v in vacancies if v.number})
    total = len(vacancy_numbers)

    clear_screen()
    print_section(
        f"Nombramientos MEP — {total} vacantes únicas  ·  "
        f"{SCRAPING.max_concurrency} consultas simultáneas"
    )

    all_appointments: list[Appointment] = []

    with ThreadPoolExecutor(max_workers=SCRAPING.max_concurrency) as executor:
        futures = {
            executor.submit(_search_single_appointment, vn, year, headless): vn
            for vn in vacancy_numbers
        }

        for index, future in enumerate(as_completed(futures), start=1):
            vacancy_number = futures[future]

            try:
                result = future.result()
                print_result(index, total, vacancy_number, len(result))
                all_appointments.extend(result)

            except Exception:
                print_result(index, total, vacancy_number, None)
                logger.exception("Error fetching vacancy %s", vacancy_number)

    print_section(f"Total: {len(all_appointments)} nombramientos encontrados.")
    return all_appointments
