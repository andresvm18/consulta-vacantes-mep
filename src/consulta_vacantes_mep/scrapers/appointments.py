from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright

from consulta_vacantes_mep.utils.console import clear_screen, print_result, print_section
from consulta_vacantes_mep.utils.logger import write_error, write_log

APPOINTMENTS_URL = "https://apps.mep.go.cr/consultanombramientos/"

MAX_WORKERS = 10
MAX_RETRIES = 3
CELL_TIMEOUT_MS = 3_000
PAGE_LOAD_TIMEOUT_MS = 60_000
POSTBACK_SETTLE_MS = 1_000
POSTBACK_TIMEOUT_MS = 8_000

APPOINTMENT_COLUMNS = [
    "Vacante",
    "Cédula",
    "Nombre",
    "Institución",
    "Clase Puesto",
    "Especialidad",
    "Grupo",
    "N° Puesto",
    "Rige",
    "Vence",
    "Estado",
    "Calificación R. Elegibles",
    "Título Nómina",
]


# ── Extraction ────────────────────────────────────────────────────────────────

def _extract_appointments_from_table(page) -> list[dict]:
    rows = page.locator("table tr")
    appointments = []

    for i in range(rows.count()):
        columns = rows.nth(i).locator("td")

        if columns.count() == 0:
            continue

        data = []

        for j in range(columns.count()):
            try:
                text = columns.nth(j).inner_text(timeout=CELL_TIMEOUT_MS).strip()
            except Exception as error:
                write_error(f"Error reading appointment table cell: {error}")
                continue

            if text:
                data.append(text)

        data = data[:13]

        if len(data) == 13:
            appointments.append(dict(zip(APPOINTMENT_COLUMNS, data)))

    return appointments


def _search_single_appointment(vacancy_number: str, year: str = "2026", headless: bool = True, attempt: int = 1) -> list[dict]:
    """Fetch appointments for one vacancy number, retrying up to MAX_RETRIES times."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(APPOINTMENTS_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            page.wait_for_timeout(POSTBACK_SETTLE_MS)

            page.locator("#radioVacante").check()
            page.locator("#txtCedula").fill(str(vacancy_number))
            page.locator("#ddlAño").select_option(str(year))
            page.evaluate("__doPostBack('btnConsultar','')")

            try:
                page.wait_for_load_state("domcontentloaded", timeout=POSTBACK_TIMEOUT_MS)
            except Exception:
                pass

            page.wait_for_timeout(POSTBACK_SETTLE_MS)

            if page.locator("table").count() == 0:
                write_log(f"Vacancy {vacancy_number}: no appointments found.")
                return []

            appointments = _extract_appointments_from_table(page)
            write_log(f"Vacancy {vacancy_number}: {len(appointments)} appointments found.")
            return appointments

        except Exception as error:
            if attempt < MAX_RETRIES:
                write_log(f"Retry {attempt}/{MAX_RETRIES} for vacancy {vacancy_number}")
                browser.close()
                return _search_single_appointment(vacancy_number, year, headless, attempt + 1)

            write_error(f"Vacancy {vacancy_number} failed after {MAX_RETRIES} attempts: {error}")
            raise

        finally:
            browser.close()


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_appointments_for_vacancies(vacancies: list[dict], year: str = "2026", headless: bool = True) -> list[dict]:
    if not vacancies:
        return []

    vacancy_numbers = list({v["Vacante"] for v in vacancies if v.get("Vacante")})
    total = len(vacancy_numbers)

    clear_screen()
    print_section(
        f"Nombramientos MEP — {total} vacantes únicas  ·  {MAX_WORKERS} consultas simultáneas"
    )

    all_appointments = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
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

            except Exception as error:
                print_result(index, total, vacancy_number, None)
                write_error(f"Error fetching vacancy {vacancy_number}: {error}")

    print_section(f"Total: {len(all_appointments)} nombramientos encontrados.")
    return all_appointments