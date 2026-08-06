"""The interactive console interface.

One Console for the whole process. Rich draws the progress bar by repainting
the lines it owns, so a plain print landing in the middle of a run leaves the
bar drawing over torn output. Everything the user reads goes through here.
"""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from consulta_vacantes_mep.app.session import SearchResult, Session
from consulta_vacantes_mep.cli.menu import ask_year, show_welcome_menu
from consulta_vacantes_mep.cli.reporter import RichReporter
from consulta_vacantes_mep.exports.excel import export_data_to_excel
from consulta_vacantes_mep.labels import appointment_to_row
from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.settings import default_year
from consulta_vacantes_mep.utils.logger import configure_logging
from consulta_vacantes_mep.utils.playwright_setup import (
    ChromiumStatus,
    chromium_is_available,
    install_chromium,
)

console = Console()
app = typer.Typer(
    help="Consulta vacantes y nombramientos docentes publicados por el MEP.",
    add_completion=False,
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


def prepare_browser() -> bool:
    """Make sure Chromium is usable, reporting to the user if it is not.

    Checking and installing are separate calls so that the message about a
    download that takes a minute is printed before it starts, not after.
    """
    if chromium_is_available():
        return True

    console.print("\n  Chromium de Playwright no está instalado.")
    console.print("  Instalando Chromium automáticamente...")

    result = install_chromium()

    if result.ok:
        return True

    console.print(f"\n  [red]{CHROMIUM_MESSAGES[result.status]}[/red]")
    return False


def show_result(result: SearchResult) -> None:
    """List the appointments found, and which lookups could not be completed."""
    if not result.appointments:
        console.print("\n  No se encontraron nombramientos.")
    else:
        console.print(f"\n  [bold]Nombramientos encontrados: {len(result.appointments)}[/bold]")

        for appointment in result.appointments:
            console.print()

            for label, value in appointment_to_row(appointment).items():
                console.print(f"  {label}: {value}")

    if not result.failed:
        return

    console.print(f"\n  [yellow]{len(result.failed)} vacantes no se pudieron consultar:[/yellow]")

    for query in result.failed[:MAX_FAILED_SHOWN]:
        console.print(f"    {query.vacancy_number}")

    if len(result.failed) > MAX_FAILED_SHOWN:
        console.print(f"    ... y {len(result.failed) - MAX_FAILED_SHOWN} más")


def show_vacancies(vacancies: list[Vacancy]) -> None:
    """List the vacancies as a table. The full record goes to the workbook."""
    table = Table(title=f"Vacantes publicadas: {len(vacancies)}", title_justify="left")
    table.add_column("Vacante")
    table.add_column("Especialidad")
    table.add_column("Institución")
    table.add_column("Regional")

    for vacancy in vacancies:
        table.add_row(
            vacancy.number, vacancy.specialty, vacancy.institution, vacancy.regional_office
        )

    console.print()
    console.print(table)


def export_result(
    vacancies: list[Vacancy], appointments: list[Appointment] | None, specialty: str | None
) -> None:
    """Write the workbook and say where it landed."""
    prefix = f"vacantes_{specialty.replace(' ', '_')}" if specialty else "todas_las_vacantes"
    file_path = export_data_to_excel(vacancies, appointments, prefix)

    if file_path:
        console.print(f"\n  Archivo Excel generado:\n  {file_path}")


def ask_export(result: SearchResult, specialty: str | None = None) -> None:
    """Offer to write the workbook. Only called when there is something in it."""
    answer = console.input("\n  ¿Desea exportar los resultados a Excel? (S/N): ").strip().lower()

    if answer != "s":
        console.print("  Resultados no exportados.")
        return

    export_result(result.vacancies, result.appointments, specialty)


def run_search(
    session: Session, specialty: str | None = None, *, refresh: bool = False
) -> None:
    """Run one search and show it.

    The two search options differ in one thing, whether a specialty narrows the
    vacancies down, so they share this.
    """
    year = ask_year(console)

    if session.cached_count is not None and not refresh:
        console.print(f"\n  Usando {session.cached_count} vacantes ya consultadas.")

    result = session.search(year, specialty, refresh=refresh)

    if not result.vacancies:
        console.print("\n  No se encontraron vacantes para esa búsqueda.")
        return

    show_result(result)
    ask_export(result, specialty)


def run_menu(session: Session) -> None:
    """Drive the menu until the user leaves."""
    while True:
        option = show_welcome_menu(console)

        if option == "1":
            run_search(session)

        elif option == "2":
            specialty = console.input("\n  Ingrese la especialidad a buscar: ").strip()

            if not specialty:
                console.print("\n  [yellow]Debe ingresar una especialidad válida.[/yellow]")
                console.input("\n  Presione Enter para continuar...")
                continue

            run_search(session, specialty)

        elif option == "3":
            session.vacancies(refresh=True)

        else:
            console.print("\n  Gracias por usar el sistema. Hasta luego.")
            return

        console.input("\n  Presione Enter para continuar...")


def new_session() -> tuple[Session, RichReporter]:
    """A session and the reporter drawing it, which the caller has to close."""
    reporter = RichReporter(console)
    return Session(reporter=reporter), reporter


@app.callback(invoke_without_command=True)
def entry_point(ctx: typer.Context) -> None:
    """Runs before every subcommand, and opens the menu when there is none."""
    configure_logging(console=console)

    if not prepare_browser():
        raise typer.Exit(code=1)

    if ctx.invoked_subcommand is not None:
        return

    session, reporter = new_session()

    try:
        run_menu(session)
    finally:
        # A phase that raises never emits its closing event, so the live display
        # has to be taken down here or the terminal keeps its drawing mode.
        reporter.close()


@app.command("buscar")
def search_command(
    especialidad: Annotated[
        str | None, typer.Option(help="Filtra las vacantes por especialidad.")
    ] = None,
    anio: Annotated[
        int | None, typer.Option(help="Año de los nombramientos a consultar.")
    ] = None,
    exportar: Annotated[
        bool, typer.Option("--exportar/--sin-exportar", help="Escribe el archivo Excel.")
    ] = True,
) -> None:
    """Consulta las vacantes publicadas y los nombramientos hechos contra ellas."""
    session, reporter = new_session()

    try:
        result = session.search(anio or default_year(), especialidad)
    finally:
        reporter.close()

    if not result.vacancies:
        console.print("\n  No se encontraron vacantes para esa búsqueda.")
        raise typer.Exit(code=1)

    show_result(result)

    if exportar:
        export_result(result.vacancies, result.appointments, especialidad)


@app.command("vacantes")
def vacancies_command(
    especialidad: Annotated[
        str | None, typer.Option(help="Filtra las vacantes por especialidad.")
    ] = None,
    exportar: Annotated[
        bool, typer.Option("--exportar/--sin-exportar", help="Escribe el archivo Excel.")
    ] = False,
) -> None:
    """Lista las vacantes publicadas, sin consultar nombramientos."""
    session, reporter = new_session()

    try:
        found = session.vacancies(especialidad)
    finally:
        reporter.close()

    if not found:
        console.print("\n  No se encontraron vacantes para esa búsqueda.")
        raise typer.Exit(code=1)

    show_vacancies(found)

    if exportar:
        export_result(found, None, especialidad)


def main() -> None:
    app()
