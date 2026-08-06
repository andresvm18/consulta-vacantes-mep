from consulta_vacantes_mep.app.session import SearchResult, Session
from consulta_vacantes_mep.exports.excel import export_data_to_excel
from consulta_vacantes_mep.labels import appointment_to_row, vacancy_to_row
from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.utils.console import ConsoleReporter
from consulta_vacantes_mep.utils.logger import configure_logging
from consulta_vacantes_mep.utils.menu import ask_year, show_welcome_menu
from consulta_vacantes_mep.utils.playwright_setup import (
    ChromiumStatus,
    chromium_is_available,
    install_chromium,
)

MAX_FAILED_SHOWN = 10

# What each failed outcome means to the user. The check itself reports facts;
# the wording is a decision for whoever is showing them.
CHROMIUM_MESSAGES = {
    ChromiumStatus.NOT_INSTALLABLE: (
        "El ejecutable debería incluir el navegador y no lo trae. "
        "Reinstale la aplicación."
    ),
    ChromiumStatus.FAILED: (
        "No se pudo instalar Chromium automáticamente. "
        "Instálelo con: python -m playwright install chromium"
    ),
}


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


def show_result(result: SearchResult) -> None:
    print_appointments(result.appointments)

    if not result.failed:
        return

    print(f"\n⚠  {len(result.failed)} vacantes no se pudieron consultar:")

    for query in result.failed[:MAX_FAILED_SHOWN]:
        print(f"   {query.vacancy_number}")

    if len(result.failed) > MAX_FAILED_SHOWN:
        print(f"   ... y {len(result.failed) - MAX_FAILED_SHOWN} más")


def run_search(session: Session, specialty: str | None = None) -> None:
    """Run one search and show it. The only difference between the two menu
    options is whether a specialty narrows the vacancies down.
    """
    year = ask_year()

    if session.cached_count is not None:
        print(f"\nUsando {session.cached_count} vacantes ya consultadas.")

    print("\nConsultando nombramientos...")
    result = session.search(year, specialty)

    show_result(result)

    prefix = f"vacantes_{specialty.replace(' ', '_')}" if specialty else "todas_las_vacantes"
    ask_export_to_excel(result.vacancies, result.appointments, prefix)


def prepare_browser() -> bool:
    """Make sure Chromium is usable, reporting to the user if it is not.

    Checking and installing are separate calls so that the message about a
    download that takes a minute is printed before it starts, not after.
    """
    if chromium_is_available():
        return True

    print("\nChromium de Playwright no está instalado.")
    print("Instalando Chromium automáticamente...")

    result = install_chromium()

    if result.ok:
        return True

    print(f"\n{CHROMIUM_MESSAGES[result.status]}")
    return False


def main() -> None:
    configure_logging()

    reporter = ConsoleReporter()

    if not prepare_browser():
        return

    session = Session(reporter=reporter)

    while True:
        option = show_welcome_menu()

        # ==========================================
        # OPCIÓN 1
        # ==========================================
        if option == "1":
            run_search(session)

        # ==========================================
        # OPCIÓN 2
        # ==========================================
        elif option == "2":
            specialty = input("\nIngrese la especialidad a buscar: ").strip()

            if not specialty:
                print("\nDebe ingresar una especialidad válida.")
                continue

            run_search(session, specialty)

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
