"""The terminal interface, and the entry point that decides which one runs.

Running with no subcommand opens the window. The commands below are the
scriptable half: the same searches, with their answers on standard output
instead of in a table a person clicks on. The interactive menu that used to
live here is gone, since everything it offered the window offers better.

Named entry rather than main because the cli package reexports the main
function, and a submodule of the same name was shadowed by it: importing
consulta_vacantes_mep.cli.main handed back the function, not the module, so
patching anything in it needed importlib. A second interface would have had the
same problem under the same name, so the two are entry.py apiece.

One Console for the whole process. Rich draws the progress bar by repainting
the lines it owns, so a plain print landing in the middle of a run leaves the
bar drawing over torn output. Everything the user reads goes through here.
"""

from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from consulta_vacantes_mep.app.session import SearchResult, Session
from consulta_vacantes_mep.app.startup import ensure_chromium
from consulta_vacantes_mep.cli.reporter import RichReporter
from consulta_vacantes_mep.exceptions import ScrapingError
from consulta_vacantes_mep.exports.excel import export_data_to_excel, filename_prefix
from consulta_vacantes_mep.models import Appointment, Vacancy
from consulta_vacantes_mep.settings import EXPORT, default_year
from consulta_vacantes_mep.utils.logger import configure_logging, get_logger
from consulta_vacantes_mep.utils.playwright_setup import ChromiumStatus

logger = get_logger(__name__)

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

# A run that could not read the site. Worded so it cannot be mistaken for the
# site having published nothing, which is the other way a run comes back empty.
SCRAPING_FAILURE_MESSAGE = (
    "No se pudo consultar el sitio del MEP. Revise su conexión e intente de "
    "nuevo; el detalle quedó en logs/errors.log."
)
NO_VACANCIES_MESSAGE = "No se encontraron vacantes para esa búsqueda."

# The same advice the window gives. Excel locks a workbook it has open, and a
# second export within the same minute writes to the same name.
EXPORT_FAILURE_MESSAGE = (
    "No se pudo escribir el archivo. Si lo tiene abierto en Excel, ciérrelo e "
    "intente de nuevo; el detalle quedó en logs/errors.log."
)


def _announce_download() -> None:
    """Said before the download starts, since it takes about a minute."""
    console.print("\n  Chromium de Playwright no está instalado.")
    console.print("  Instalando Chromium automáticamente...")


def prepare_browser() -> bool:
    """Say what the startup sequence found, and whether a run can go ahead.

    The sequence itself is app/startup.py. What is left here is wording and
    where it goes, which is the only part a windowed interface would do
    differently.
    """
    result = ensure_chromium(before_install=_announce_download)

    if result.ok:
        return True

    console.print(f"\n  [red]{CHROMIUM_MESSAGES[result.status]}[/red]")
    return False


def show_result(result: SearchResult) -> None:
    """List the appointments found, and which lookups could not be completed.

    Six columns of the thirteen, the way show_vacancies picks four of eight:
    enough to answer whether a post was filled and by whom, with the full
    record left to the workbook. The cédula is not among them. Nobody consults
    this to find out somebody's identification number, and fifty of them on a
    terminal live on in scrollback.
    """
    if not result.appointments:
        console.print("\n  No se encontraron nombramientos.")
    else:
        table = Table(
            title=f"Nombramientos encontrados: {len(result.appointments)}",
            title_justify="left",
        )
        table.add_column("Vacante")
        table.add_column("Nombre")
        table.add_column("Institución")
        table.add_column("Especialidad")
        table.add_column("Rige")
        table.add_column("Vence")

        for appointment in result.appointments:
            table.add_row(
                appointment.vacancy_number,
                appointment.full_name,
                appointment.institution,
                appointment.specialty,
                appointment.starts_on,
                appointment.ends_on,
            )

        console.print()
        console.print(table)

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
    vacancies: list[Vacancy],
    appointments: list[Appointment] | None,
    specialty: str | None,
    *,
    include_personal: bool = EXPORT.include_personal_data,
) -> None:
    """Write the workbook and say where it landed, or that it could not be.

    A file that could not be written is an OSError, a PermissionError when Excel
    has it open. Left alone it reached the user as a traceback, after the
    results had already been shown.
    """
    try:
        file_path = export_data_to_excel(
            vacancies,
            appointments,
            filename_prefix(specialty),
            include_personal=include_personal,
        )

    except OSError:
        logger.exception("The workbook could not be written")
        console.print(f"\n  [red]{EXPORT_FAILURE_MESSAGE}[/red]")
        raise typer.Exit(code=1) from None

    if file_path:
        console.print(f"\n  Archivo Excel generado:\n  {file_path}")

        if not include_personal:
            console.print("  Sin cédula ni nombre. Use --datos-personales para incluirlos.")


def new_session() -> tuple[Session, RichReporter]:
    """A session and the reporter drawing it, which the caller has to close."""
    reporter = RichReporter(console)
    return Session(reporter=reporter), reporter


def fail_run() -> NoReturn:
    """Say the site could not be read, and end with a failing exit code.

    Called once the reporter is closed, not from inside the run: a line printed
    while the progress bar is live lands between its repaints. The traceback is
    already in the log; what the user reads here is only that it failed.
    """
    console.print(f"\n  [red]{SCRAPING_FAILURE_MESSAGE}[/red]")
    raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def entry_point(ctx: typer.Context) -> None:
    """Open the window, unless a subcommand asked for the terminal instead."""
    if ctx.invoked_subcommand is None:
        # Imported here rather than at the top of the module. PySide6.QtWidgets
        # takes about 150 milliseconds to import against the 330 this module
        # already costs, and the terminal path never needs a single widget.
        from consulta_vacantes_mep.gui.entry import main as run_window  # noqa: PLC0415

        raise typer.Exit(code=run_window())

    # Only the terminal path configures logging against the console, and only it
    # checks the browser here. The window does both for itself, with a dialog
    # instead of a printed line.
    configure_logging(console=console)

    if not prepare_browser():
        raise typer.Exit(code=1)


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
    datos_personales: Annotated[
        bool,
        typer.Option(
            "--datos-personales/--sin-datos-personales",
            help="Incluye la cédula y el nombre en el archivo Excel.",
        ),
    ] = EXPORT.include_personal_data,
) -> None:
    """Consulta las vacantes publicadas y los nombramientos hechos contra ellas."""
    session, reporter = new_session()
    result: SearchResult | None = None

    try:
        result = session.search(anio or default_year(), especialidad)
    except ScrapingError:
        result = None
    finally:
        reporter.close()

    if result is None:
        fail_run()

    if not result.vacancies:
        console.print(f"\n  {NO_VACANCIES_MESSAGE}")
        raise typer.Exit(code=1)

    show_result(result)

    if exportar:
        export_result(
            result.vacancies,
            result.appointments,
            especialidad,
            include_personal=datos_personales,
        )


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
    found: list[Vacancy] | None = None

    try:
        found = session.vacancies(especialidad)
    except ScrapingError:
        found = None
    finally:
        reporter.close()

    if found is None:
        fail_run()

    if not found:
        console.print(f"\n  {NO_VACANCIES_MESSAGE}")
        raise typer.Exit(code=1)

    show_vacancies(found)

    if exportar:
        export_result(found, None, especialidad)


def main() -> None:
    app()
