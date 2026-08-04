"""Developer utility that saves raw HTML from the MEP pages as test fixtures.

Run this when the source site changes, or when a new parsing edge case needs
to be reproduced in tests. The output is committed to the repository so the
test suite never has to reach the network.

Personal data is redacted before writing. See the redaction note below.

Usage:
    python scripts/capture_fixtures.py --vacancy 1536996 --year 2026
"""

import argparse
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from consulta_vacantes_mep.settings import SCRAPING

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# The appointments registry exposes national identification numbers and full
# names. Fixtures live in a public repository, so those values are replaced
# with structurally identical placeholders: the parser sees the same shape,
# but no real person's data is published.
ID_PATTERN = re.compile(r"\b\d{9}\b")
ID_PLACEHOLDER = "000000000"

# ASP.NET serializes the entire grid, including personal data, into hidden
# form fields. Redacting the visible cells is not enough: the same values
# survive base64-encoded in __VIEWSTATE. Strip those fields entirely.
HIDDEN_FIELD_PATTERN = re.compile(
    r'(<input[^>]*id="__(?:VIEWSTATE|VIEWSTATEGENERATOR|EVENTVALIDATION)"[^>]*value=")[^"]*(")'
)

NAME_PATTERN = re.compile(r'(<td data-title="Nombre">)[^<]*(</td>)')

def redact(html: str) -> str:
    """Remove personal data before a fixture is committed to the repository."""
    html = ID_PATTERN.sub(ID_PLACEHOLDER, html)
    html = NAME_PATTERN.sub(r"\1PEREZ PEREZ JUAN\2", html)
    return HIDDEN_FIELD_PATTERN.sub(r"\1REDACTED\2", html)


def capture_appointments_initial(page) -> None:
    """Capture the page before any query is submitted."""
    page.goto(
        SCRAPING.appointments_url,
        wait_until="domcontentloaded",
        timeout=SCRAPING.page_load_timeout_ms,
    )
    page.wait_for_timeout(SCRAPING.settle_ms)

    path = FIXTURE_DIR / "appointments_initial.html"
    path.write_text(redact(page.content()), encoding="utf-8")
    print(f"Wrote {path}")


def capture_vacancies(page) -> None:
    page.goto(
        SCRAPING.vacancies_url,
        wait_until="domcontentloaded",
        timeout=SCRAPING.page_load_timeout_ms,
    )
    page.wait_for_timeout(3_000)

    select = page.locator("select").first
    options = select.locator("option")

    # Pick the first real option, skipping the placeholder entry.
    target_value = None

    for i in range(options.count()):
        text = options.nth(i).inner_text().strip()
        value = options.nth(i).get_attribute("value")

        if text and value and "Seleccione" not in text:
            target_value = value
            break

    if target_value is None:
        print("No regional office options found.")
        return

    select.select_option(target_value)
    page.wait_for_selector("table tr td", timeout=SCRAPING.selector_timeout_ms)
    page.wait_for_timeout(SCRAPING.settle_ms)

    path = FIXTURE_DIR / "vacancies_table.html"
    path.write_text(page.content(), encoding="utf-8")
    print(f"Wrote {path}")


def capture_appointments(page, vacancy_number: str, year: int) -> None:
    page.goto(
        SCRAPING.appointments_url,
        wait_until="domcontentloaded",
        timeout=SCRAPING.page_load_timeout_ms,
    )
    page.wait_for_timeout(SCRAPING.settle_ms)

    page.locator("#radioVacante").check()
    page.locator("#txtCedula").fill(vacancy_number)
    page.locator("#ddlAño").select_option(str(year))
    page.evaluate("__doPostBack('btnConsultar','')")

    page.wait_for_load_state("domcontentloaded", timeout=SCRAPING.postback_timeout_ms)
    page.wait_for_timeout(SCRAPING.settle_ms)

    path = FIXTURE_DIR / "appointments_table.html"
    path.write_text(redact(page.content()), encoding="utf-8")
    print(f"Wrote {path}")


def capture_appointments_empty(page, vacancy_number: str, year: int) -> None:
    """Capture the page for a vacancy that returns no appointments."""
    page.goto(
        SCRAPING.appointments_url,
        wait_until="domcontentloaded",
        timeout=SCRAPING.page_load_timeout_ms,
    )
    page.wait_for_timeout(SCRAPING.settle_ms)

    page.locator("#radioVacante").check()
    page.locator("#txtCedula").fill(vacancy_number)
    page.locator("#ddlAño").select_option(str(year))
    page.evaluate("__doPostBack('btnConsultar','')")

    page.wait_for_load_state("domcontentloaded", timeout=SCRAPING.postback_timeout_ms)
    page.wait_for_timeout(SCRAPING.settle_ms)

    path = FIXTURE_DIR / "appointments_empty.html"
    path.write_text(redact(page.content()), encoding="utf-8")
    print(f"Wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vacancy", required=True, help="Vacancy number with results")
    parser.add_argument("--empty", required=True, help="Vacancy number without results")
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            capture_appointments_initial(page)
            capture_vacancies(page)
            capture_appointments(page, args.vacancy, args.year)
            capture_appointments_empty(page, args.empty, args.year)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
