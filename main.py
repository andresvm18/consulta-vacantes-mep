from scrapers.vacancies_scraper import (
    scrape_all_vacancies,
    filter_vacancies_by_specialty,
)

from scrapers.appointments_scraper import (
    scrape_appointments_for_vacancies,
)

from exports.excel_exporter import export_data_to_excel
from utils.menu import show_welcome_menu, ask_year
from utils.playwright_setup import ensure_chromium_installed
from datetime import datetime

def print_vacancies(vacancies):
    if not vacancies:
        print("\nNo se encontraron vacantes.")
        return

    print("\n" + "=" * 48)
    print(f"Vacantes encontradas: {len(vacancies)}")
    print("=" * 48)

    for vacancy in vacancies:
        print("\n----------------------------------------")
        print(f"Vacante: {vacancy['Vacante']}")
        print(f"Dirección Regional: {vacancy['Dirección Regional']}")
        print(f"Clase de Puesto: {vacancy['Clase de Puesto']}")
        print(f"Especialidad: {vacancy['Especialidad']}")
        print(f"Institución: {vacancy['Institución']}")
        print(f"Lecciones: {vacancy['Lecciones']}")
        print(f"Rige: {vacancy['Rige']}")
        print(f"Vence: {vacancy['Vence']}")


def print_appointments(appointments):
    if not appointments:
        print("\nNo se encontraron nombramientos.")
        return

    print("\n" + "=" * 48)
    print(f"Nombramientos encontrados: {len(appointments)}")
    print("=" * 48)

    for appointment in appointments:
        print("\n----------------------------------------")

        for key, value in appointment.items():
            print(f"{key}: {value}")


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

def ask_appointments_year():
    current_year = str(datetime.now().year)

    year = input(
        f"\nIngrese el año para consultar nombramientos "
        f"[Enter = {current_year}]: "
    ).strip()

    if not year:
        return current_year

    if not year.isdigit():
        print(f"\nAño inválido. Se utilizará {current_year}.")
        return current_year

    return year

def main():
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

            year = ask_appointments_year()
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

            year = ask_appointments_year()
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