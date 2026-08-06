from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from consulta_vacantes_mep.events import (
    ItemCompleted,
    NullReporter,
    Phase,
    PhaseFinished,
    PhaseStarted,
    Reporter,
)
from consulta_vacantes_mep.exceptions import PermanentScrapingError, ScrapingError
from consulta_vacantes_mep.models import Vacancy
from consulta_vacantes_mep.parsing import VACANCIES_TABLE_SELECTOR, parse_vacancies
from consulta_vacantes_mep.retry import with_retry
from consulta_vacantes_mep.scrapers.errors import classify
from consulta_vacantes_mep.settings import SCRAPING
from consulta_vacantes_mep.utils.logger import get_logger
from consulta_vacantes_mep.utils.text import normalize_text

logger = get_logger(__name__)

_OFFICES_LOADED = """(minimum) => {
    const select = document.querySelector('select');
    return Boolean(select) && select.options.length > minimum;
}"""

# The select carries a "Seleccione" placeholder before Blazor fills in the real
# offices, so a single option means the list has not arrived yet.
_PLACEHOLDER_OPTIONS = 1


_PAGE_READY = """({ selector, minimum }) => {
    const select = document.querySelector('select');
    if (!select || select.options.length <= minimum) return false;

    const body = document.querySelector(selector + ' tbody');
    return Boolean(body) && (body.textContent || '').trim() !== '';
}"""


def _wait_for_page_ready(page: Page) -> None:
    """Wait until the page has rendered, which is as far as the DOM can tell us.

    Replaces a three second sleep after navigation. The page is a Blazor app:
    the document is parsed well before the component fetches the offices and
    renders them, so domcontentloaded says nothing about either.

    This proves the markup arrived, not that the app responds to it. Blazor
    prerenders, so the select and the grid exist before the app is live, and a
    selection made in that window changes the DOM value with nothing reacting.
    The first office of a run therefore fails its first attempt; the retry
    policy covers it, which is why the grid timeout is kept short.
    """
    page.wait_for_function(
        _PAGE_READY,
        arg={"selector": VACANCIES_TABLE_SELECTOR, "minimum": _PLACEHOLDER_OPTIONS},
        timeout=SCRAPING.grid_timeout_ms,
    )


# MudBlazor replaces the rows with a single full-width cell while the grid is not
# showing data. Neither of these means the office has no vacancies, so neither
# ends the wait. Captured from the live site; see the note in _select_office.
_TRANSIENT_GRID_TEXT = ("Cargando", "Seleccione una Direcci\u00f3n Regional")

_GRID_READY = """({ selector, previous, transient }) => {
    const body = document.querySelector(selector + ' tbody');
    if (!body) return false;

    const text = (body.textContent || '').trim();
    if (text === previous) return false;

    if (body.querySelector('td[data-label]')) return true;

    const placeholder = body.querySelector('.mud-table-empty-row');
    if (!placeholder) return false;

    const message = (placeholder.textContent || '').trim();
    return message !== '' && !transient.some((m) => message.includes(m));
}"""


def _select_office(page: Page, office: dict) -> None:
    """Select a regional office and wait for the grid to finish showing its rows.

    Two things have to be true before the grid can be read, and waiting for
    either one alone loses rows.

    The content has to differ from what was there before, because Blazor keeps
    the previous office's rows in the DOM while it re-renders.

    And the grid has to be in a final state. In place of rows, MudBlazor renders
    a single cell carrying a message: "Cargando.." while the query runs, and
    "Seleccione una Direccion Regional para buscar vacantes" before anything is
    picked. Both differ from the previous content, so a change alone was enough
    to end the wait, and the office was reported as empty. Real rows carry
    data-label cells; a genuinely empty office carries a message that is neither
    of the two transient ones.
    """
    table = page.locator(VACANCIES_TABLE_SELECTOR)

    try:
        previous = (
            table.locator("tbody").text_content(timeout=SCRAPING.cell_timeout_ms) or ""
        ).strip()
    except PlaywrightError:
        previous = ""

    try:
        page.locator("select").first.select_option(office["value"])

        page.wait_for_function(
            _GRID_READY,
            arg={
                "selector": VACANCIES_TABLE_SELECTOR,
                "previous": previous,
                "transient": list(_TRANSIENT_GRID_TEXT),
            },
            timeout=SCRAPING.grid_timeout_ms,
        )

    except Exception as error:
        raise classify(error, f"office {office['text']}") from error


_select_office_with_retry = with_retry(_select_office)


def _scrape_regional_office(page: Page, office: dict) -> list[Vacancy] | None:
    """Scrape one regional office, or return None if it could not be read.

    An office that failed and an office with nothing published are different
    facts, and collapsing them into an empty list is exactly how the grid race
    stayed invisible: the run reported zero vacancies and looked complete.

    Raises on permanent failure.
    """
    try:
        _select_office_with_retry(page, office)

    except PermanentScrapingError:
        raise

    except ScrapingError as error:
        logger.warning("Office %s: %s", office["text"], error)
        return None

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
def scrape_all_vacancies(
    headless: bool = SCRAPING.headless, reporter: Reporter | None = None
) -> list[Vacancy]:
    report = reporter or NullReporter()
    all_vacancies: list[Vacancy] = []

    # Bound before the browser opens: the handlers below report on them, and a
    # failure during navigation would otherwise leave them undefined.
    total = 0
    failed = 0
    permanent_failures = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(SCRAPING.vacancies_url, wait_until="domcontentloaded", timeout=SCRAPING.page_load_timeout_ms)
            _wait_for_page_ready(page)

            offices = _get_regional_offices(page)
            total = len(offices)

            report.emit(PhaseStarted(Phase.VACANCIES, total))

            for index, office in enumerate(offices, start=1):
                try:
                    vacancies = _scrape_regional_office(page, office)

                except PermanentScrapingError:
                    permanent_failures += 1
                    logger.exception("Office %s: page structure changed", office["text"])
                    vacancies = None

                    # Every office failing the same way means the site changed,
                    # not that this run was unlucky. Continuing would produce an
                    # empty workbook that looks like a legitimate result.
                    if permanent_failures == total:
                        raise

                if vacancies is None:
                    failed += 1
                    logger.warning("%s: could not be read.", office["text"])
                else:
                    all_vacancies.extend(vacancies)
                    logger.info("%s: %d vacancies found.", office["text"], len(vacancies))

                report.emit(
                    ItemCompleted(
                        Phase.VACANCIES,
                        index,
                        total,
                        office["text"],
                        None if vacancies is None else len(vacancies),
                    )
                )

        except PermanentScrapingError:
            logger.exception("All %d offices failed; the site structure changed", total)
            raise

        except Exception:
            logger.exception("Fatal error in scrape_all_vacancies")

        finally:
            browser.close()

    report.emit(PhaseFinished(Phase.VACANCIES, len(all_vacancies), failed))
    logger.info("Total: %d vacancies found.", len(all_vacancies))
    return all_vacancies


def filter_vacancies_by_specialty(
    vacancies: list[Vacancy], specialty: str
) -> list[Vacancy]:
    normalized = normalize_text(specialty)
    return [v for v in vacancies if normalized in normalize_text(v.specialty)]
