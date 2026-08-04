from consulta_vacantes_mep.exports.excel import export_data_to_excel
from consulta_vacantes_mep.labels import appointment_to_row, vacancy_to_row
from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.scrapers.appointments import scrape_appointments_for_vacancies
from consulta_vacantes_mep.scrapers.vacancies import (
    filter_vacancies_by_specialty,
    scrape_all_vacancies,
)
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


def main():
    configure_logging()

    if not ensure_chromium_installed():
        return

    while True:
        option = show_welcome_menu()

        # ==========================================
        # OPCIÓN 1
        # ==========================================
        if option == "1":

            vacancies = scrape_all_vacancies(headless=True)

            # print_vacancies(vacancies)

            year = ask_year()
            print("\nConsultando nombramientos...")

            appointments = scrape_appointments_for_vacancies(
                vacancies,
                year=year,
                headless=True
            )

            print_appointments(appointments)

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

            vacancies = scrape_all_vacancies(headless=True)

            filtered_vacancies = filter_vacancies_by_specialty(
                vacancies,
                specialty
            )

            # print_vacancies(filtered_vacancies)

            year = ask_year()
            print("\nConsultando nombramientos...")

            appointments = scrape_appointments_for_vacancies(
                filtered_vacancies,
                year=year,
                headless=True
            )

            print_appointments(appointments)

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
