from playwright.sync_api import sync_playwright

from consulta_vacantes_mep.utils.console import clear_screen, print_progress, print_section
from consulta_vacantes_mep.utils.logger import write_error, write_log
from consulta_vacantes_mep.utils.text import normalize_text

VACANCIES_URL = "https://apps.mep.go.cr/formulario"

VACANCY_COLUMNS = [
    "Vacante",
    "Dirección Regional",
    "Clase de Puesto",
    "Especialidad",
    "Institución",
    "Lecciones",
    "Rige",
    "Vence",
]

MAX_RETRIES = 3
ROW_TIMEOUT_MS = 3_000
PAGE_LOAD_TIMEOUT_MS = 60_000
SELECTOR_TIMEOUT_MS = 8_000
SETTLE_MS = 1_500


# ── Helpers ───────────────────────────────────────────────────────────────────


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


def _extract_vacancies_from_table(page) -> list[dict]:
    rows = page.locator("table tr")
    vacancies = []

    for i in range(rows.count()):
        columns = rows.nth(i).locator("td")

        if columns.count() == 0:
            continue

        data = []

        for j in range(columns.count()):
            try:
                text = columns.nth(j).inner_text(timeout=ROW_TIMEOUT_MS).strip()
            except Exception as error:
                write_error(f"Error reading vacancy table cell: {error}")
                continue

            if text.upper() == "APLICAR":
                continue

            data.append(text)

        data = data[:8]

        if len(data) == 8:
            vacancies.append(dict(zip(VACANCY_COLUMNS, data)))

    return vacancies


def _scrape_regional_office(page, office: dict, attempt: int = 1) -> list[dict]:
    """Scrape one regional office, retrying up to MAX_RETRIES times."""
    try:
        page.locator("select").first.select_option(office["value"])

        try:
            page.wait_for_selector("table tr td", timeout=SELECTOR_TIMEOUT_MS)
            page.wait_for_timeout(SETTLE_MS)
        except Exception:
            return []

        return _extract_vacancies_from_table(page)

    except Exception as error:
        if attempt < MAX_RETRIES:
            write_log(f"Retry {attempt}/{MAX_RETRIES} for {office['text']}")
            return _scrape_regional_office(page, office, attempt + 1)

        write_error(f"Regional {office['text']} failed after {MAX_RETRIES} attempts: {error}")
        return []


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_all_vacancies(headless: bool = True) -> list[dict]:
    all_vacancies = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(VACANCIES_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            page.wait_for_timeout(3_000)

            offices = _get_regional_offices(page)
            total = len(offices)

            clear_screen()
            print_section(f"Vacantes MEP — {total} direcciones regionales")

            for index, office in enumerate(offices, start=1):
                vacancies = _scrape_regional_office(page, office)
                all_vacancies.extend(vacancies)

                print_progress(index, total, office["text"], len(vacancies))
                write_log(f"{office['text']}: {len(vacancies)} vacantes encontradas.")

            print()  # newline after progress bar

        except Exception as error:
            print("\n  ✗ Error general consultando vacantes.")
            write_error(f"Fatal error in scrape_all_vacancies: {error}")

        finally:
            browser.close()

    print_section(f"Total: {len(all_vacancies)} vacantes encontradas.")
    return all_vacancies


def filter_vacancies_by_specialty(vacancies: list[dict], specialty: str) -> list[dict]:
    normalized = normalize_text(specialty)
    return [v for v in vacancies if normalized in normalize_text(v["Especialidad"])]