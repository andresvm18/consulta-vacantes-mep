from concurrent.futures import ThreadPoolExecutor, as_completed

from playwright.sync_api import sync_playwright

from consulta_vacantes_mep.settings import SCRAPING
from consulta_vacantes_mep.utils.console import clear_screen, print_result, print_section
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)

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
                text = columns.nth(j).inner_text(timeout=SCRAPING.cell_timeout_ms).strip()
            except Exception:
                logger.exception("Error reading appointment table cell")
                continue

            if text:
                data.append(text)

        data = data[:13]

        if len(data) == 13:
            appointments.append(dict(zip(APPOINTMENT_COLUMNS, data, strict=True)))

    return appointments


def _search_single_appointment(
    vacancy_number: str,
    year: int,
    headless: bool = SCRAPING.headless,
    attempt: int = 1,
) -> list[dict]:
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

            if page.locator("table").count() == 0:
                logger.info("Vacancy %s: no appointments found.", vacancy_number)
                return []

            appointments = _extract_appointments_from_table(page)
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
    vacancies: list[dict],
    year: int,
    headless: bool = SCRAPING.headless,
) -> list[dict]:
    if not vacancies:
        return []

    vacancy_numbers = list({v["Vacante"] for v in vacancies if v.get("Vacante")})
    total = len(vacancy_numbers)

    clear_screen()
    print_section(
        f"Nombramientos MEP — {total} vacantes únicas  ·  "
        f"{SCRAPING.max_concurrency} consultas simultáneas"
    )

    all_appointments = []

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
