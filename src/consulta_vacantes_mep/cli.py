from consulta_vacantes_mep.events import Reporter
from consulta_vacantes_mep.exports.excel import export_data_to_excel
from consulta_vacantes_mep.labels import appointment_to_row, vacancy_to_row
from consulta_vacantes_mep.models import Appointment, QueryOutcome, Vacancy
from consulta_vacantes_mep.scrapers.appointments import scrape_appointments_for_vacancies
from consulta_vacantes_mep.scrapers.vacancies import (
    filter_vacancies_by_specialty,
    scrape_all_vacancies,
)
from consulta_vacantes_mep.utils.console import ConsoleReporter
from consulta_vacantes_mep.utils.logger import configure_logging
from consulta_vacantes_mep.utils.menu import ask_year, show_welcome_menu
from consulta_vacantes_mep.utils.playwright_setup import ensure_chromium_installed


def print_vacancies(vacancies: list[Vacancy]) -> None:
    if not vacancies:
        print("\nNo se encontraron vacantes.")
        return

    print("\n" + "=" * 48)
    print(f"Vacantes encontradas: {len(vacancies)}")
    print("=" * 48)

    for vacancy in vacancies:
        print("\n----------------------------------------")

        for label, value in vacancy_to_row(vacancy).items():
            print(f"{label}: {value}")


def print_appointments(appointments: list[Appointment]) -> None:
    if not appointments:
        print("\nNo se encontraron nombramientos.")
        return

    print("\n" + "=" * 48)
    print(f"Nombramientos encontrados: {len(appointments)}")
    print("=" * 48)

    for appointment in appointments:
        print("\n----------------------------------------")

        for label, value in appointment_to_row(appointment).items():
            print(f"{label}: {value}")


def ask_export_to_excel(
    vacancies,
    appointments=None,
    filename_prefix="vacantes"
):
    answer = input(
        "\n¿Desea exportar los resultados a Excel? (S/N): "
    ).strip().lower()

    if answer != "s":
        print("\nResultados no exportados.")
        return

    file_path = export_data_to_excel(
        vacancies,
        appointments,
        filename_prefix
    )

    if file_path:
        print("\nArchivo Excel generado correctamente:")
        print(file_path)

def get_vacancies(cache: list[Vacancy] | None, reporter: Reporter) -> list[Vacancy]:
    """Return the cached vacancies, scraping every regional office on first use.

    Scraping all offices takes about half a minute. Reusing the result lets the
    user explore several specialties in one session without paying that cost
    again. The cache lives for one session only.
    """
    if cache is not None:
        print(f"\nUsando {len(cache)} vacantes ya consultadas.")
        return cache

    return scrape_all_vacancies(reporter=reporter)

def main() -> None:  # noqa: PLR0912  # TODO(stage-6): split into command handlers
    configure_logging()
    # Initialize the console reporter
    reporter: Reporter = ConsoleReporter()

    if not ensure_chromium_installed():
        return

    # Scraping every regional office takes about half a minute. Reuse the
    # result while the user explores different specialties in one session.
    cached_vacancies: list[Vacancy] | None = None

    while True:
        option = show_welcome_menu()

        # ==========================================
        # OPCIÓN 1
        # ==========================================
        if option == "1":
            cached_vacancies = get_vacancies(cached_vacancies, reporter)
            vacancies = cached_vacancies
            year = ask_year()
            print("\nConsultando nombramientos...")

            queries = scrape_appointments_for_vacancies(
                vacancies, year=year, headless=True, reporter=reporter
            )

            appointments = [a for q in queries for a in q.appointments]
            failed = [q for q in queries if q.outcome is QueryOutcome.FAILED]

            print_appointments(appointments)

            if failed:
                print(f"\n⚠  {len(failed)} vacantes no se pudieron consultar:")
                for query in failed[:10]:
                    print(f"   {query.vacancy_number}")
                if len(failed) > 10:
                    print(f"   ... y {len(failed) - 10} más")

            ask_export_to_excel(
                vacancies,
                appointments,
                "todas_las_vacantes"
            )

        # ==========================================
        # OPCIÓN 2
        # ==========================================
        elif option == "2":

            specialty = input(
                "\nIngrese la especialidad a buscar: "
            ).strip()

            if not specialty:
                print("\nDebe ingresar una especialidad válida.")
                continue

            cached_vacancies = get_vacancies(cached_vacancies, reporter)

            filtered_vacancies = filter_vacancies_by_specialty(
                cached_vacancies,
                specialty
            )

            year = ask_year()
            print("\nConsultando nombramientos...")

            queries = scrape_appointments_for_vacancies(
                filtered_vacancies, year=year, headless=True, reporter=reporter
            )

            appointments = [a for q in queries for a in q.appointments]
            failed = [q for q in queries if q.outcome is QueryOutcome.FAILED]

            print_appointments(appointments)

            if failed:
                print(f"\n⚠  {len(failed)} vacantes no se pudieron consultar:")
                for query in failed[:10]:
                    print(f"   {query.vacancy_number}")
                if len(failed) > 10:
                    print(f"   ... y {len(failed) - 10} más")

            ask_export_to_excel(
                filtered_vacancies,
                appointments,
                f"vacantes_{specialty.replace(' ', '_')}"
            )

        # ==========================================
        # OPCIÓN 3
        # ==========================================
        elif option == "3":
            print("\nGracias por usar el sistema. Hasta luego.")
            break

        # ==========================================
        # OPCIÓN INVÁLIDA
        # ==========================================
        else:
            print("\nOpción inválida. Intente nuevamente.")

        input("\nPresione Enter para continuar...")


if __name__ == "__main__":
    main()
