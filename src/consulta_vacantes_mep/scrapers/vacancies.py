from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from consulta_vacantes_mep.exceptions import PermanentScrapingError, ScrapingError
from consulta_vacantes_mep.models import Vacancy
from consulta_vacantes_mep.parsing import VACANCIES_TABLE_SELECTOR, parse_vacancies
from consulta_vacantes_mep.retry import with_retry
from consulta_vacantes_mep.scrapers.errors import classify
from consulta_vacantes_mep.settings import SCRAPING
from consulta_vacantes_mep.utils.console import clear_screen, print_progress, print_section
from consulta_vacantes_mep.utils.logger import get_logger
from consulta_vacantes_mep.utils.text import normalize_text

logger = get_logger(__name__)

def _select_office(page: Page, office: dict) -> None:
    """Select a regional office and wait for its rows to replace the previous ones.

    Blazor keeps the previous office's rows in the DOM while it re-renders, so
    waiting for a row to exist matches stale content. Comparing against a
    snapshot taken before the change is a real condition.
    """
    table = page.locator(VACANCIES_TABLE_SELECTOR)

    try:
        previous = table.locator("tbody").text_content() or ""
    except PlaywrightError:
        previous = ""

    try:
        page.locator("select").first.select_option(office["value"])

        page.wait_for_function(
            """([selector, previous]) => {
                const body = document.querySelector(selector + ' tbody');
                if (!body) return false;
                return (body.textContent || '') !== previous;
            }""",
            arg=[VACANCIES_TABLE_SELECTOR, previous],
            timeout=SCRAPING.selector_timeout_ms,
        )

    except Exception as error:
        raise classify(error, f"office {office['text']}") from error


_select_office_with_retry = with_retry(_select_office)


def _scrape_regional_office(page: Page, office: dict) -> list[Vacancy]:
    """Scrape one regional office. Raises on permanent failure."""
    try:
        _select_office_with_retry(page, office)

    except PermanentScrapingError:
        raise

    except ScrapingError as error:
        logger.warning("Office %s: %s", office["text"], error)
        return []

    return parse_vacancies(page.locator(VACANCIES_TABLE_SELECTOR), office["text"])

# ── Extraction ────────────────────────────────────────────────────────────────
def _get_regional_offices(page) -> list[dict]:
    select = page.locator("select").first
    options = select.locator("option")
    offices = []

    for i in range(options.count()):
        text = options.nth(i).inner_text().strip()
        value = options.nth(i).get_attribute("value")

        if text and value and "Seleccione" not in text:
            offices.append({"text": text, "value": value})

    return offices



# ── Public API ────────────────────────────────────────────────────────────────
def scrape_all_vacancies(headless: bool = SCRAPING.headless) -> list[Vacancy]:
    all_vacancies: list[Vacancy] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(SCRAPING.vacancies_url, wait_until="domcontentloaded", timeout=SCRAPING.page_load_timeout_ms)
            page.wait_for_timeout(3_000)

            offices = _get_regional_offices(page)
            total = len(offices)

            clear_screen()
            print_section(f"Vacantes MEP — {total} direcciones regionales")

            permanent_failures = 0

            for index, office in enumerate(offices, start=1):
                try:
                    vacancies = _scrape_regional_office(page, office)

                except PermanentScrapingError:
                    permanent_failures += 1
                    logger.exception("Office %s: page structure changed", office["text"])
                    vacancies = []

                    # Every office failing the same way means the site changed,
                    # not that this run was unlucky. Continuing would produce an
                    # empty workbook that looks like a legitimate result.
                    if permanent_failures == total:
                        raise

                all_vacancies.extend(vacancies)

                print_progress(index, total, office["text"], len(vacancies))
                logger.info(
                    "%s: %d vacantes encontradas.", office["text"], len(vacancies)
                )

        except PermanentScrapingError:
            logger.exception("All %d offices failed; the site structure changed", total)
            raise

        except Exception:
            logger.exception("Fatal error in scrape_all_vacancies")

        finally:
            browser.close()

    print_section(f"Total: {len(all_vacancies)} vacantes encontradas.")
    logger.info(f"Total: {len(all_vacancies)} vacancies found.")
    return all_vacancies


def filter_vacancies_by_specialty(
    vacancies: list[Vacancy], specialty: str
) -> list[Vacancy]:
    normalized = normalize_text(specialty)
    return [v for v in vacancies if normalized in normalize_text(v.specialty)]
