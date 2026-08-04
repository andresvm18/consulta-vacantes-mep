from playwright.sync_api import sync_playwright

from consulta_vacantes_mep.models import Vacancy
from consulta_vacantes_mep.parsing import VACANCIES_TABLE_SELECTOR, parse_vacancies
from consulta_vacantes_mep.settings import SCRAPING
from consulta_vacantes_mep.utils.console import clear_screen, print_progress, print_section
from consulta_vacantes_mep.utils.logger import get_logger
from consulta_vacantes_mep.utils.text import normalize_text

logger = get_logger(__name__)

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


def _scrape_regional_office(page, office: dict, attempt: int = 1) -> list[Vacancy]:
    """Scrape one regional office, retrying on failure."""
    try:
        page.locator("select").first.select_option(office["value"])

        try:
            page.wait_for_selector(
                f"{VACANCIES_TABLE_SELECTOR} tbody tr",
                timeout=SCRAPING.selector_timeout_ms,
            )
            # The grid keeps the previous office's rows in the DOM while Blazor
            # re-renders, so waiting for a row to exist does not mean the new
            # data has arrived. This delay is a stopgap until stage 5 replaces
            # it with a wait on the actual render.
            page.wait_for_timeout(SCRAPING.settle_ms)
        except Exception:
            logger.warning("No result table for %s within timeout", office["text"])
            return []

        return parse_vacancies(page.locator(VACANCIES_TABLE_SELECTOR), office["text"])

    except Exception:
        if attempt < SCRAPING.max_retries:
            logger.warning(
                "Retry %d/%d for %s", attempt, SCRAPING.max_retries, office["text"]
            )
            return _scrape_regional_office(page, office, attempt + 1)

        logger.exception(
            "Regional %s failed after %d attempts", office["text"], SCRAPING.max_retries
        )
        return []


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

            for index, office in enumerate(offices, start=1):
                vacancies = _scrape_regional_office(page, office)
                all_vacancies.extend(vacancies)

                print_progress(index, total, office["text"], len(vacancies))
                logger.info(f"{office['text']}: {len(vacancies)} vacantes encontradas.")

            logger.info(f"Total: {len(all_vacancies)} vacantes encontradas.")

        except Exception:
            logger.exception("Fatal error in scrape_all_vacancies")

        finally:
            browser.close()

    logger.info(f"Total: {len(all_vacancies)} vacancies found.")
    return all_vacancies


def filter_vacancies_by_specialty(
    vacancies: list[Vacancy], specialty: str
) -> list[Vacancy]:
    normalized = normalize_text(specialty)
    return [v for v in vacancies if normalized in normalize_text(v.specialty)]
