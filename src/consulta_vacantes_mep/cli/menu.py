"""The interactive menu.

Kept until the GUI replaces it. Rendering goes through Rich rather than raw
prints so there is one console in the process: two writers taking turns leave
the progress bar drawing over half-written lines.
"""

from rich.console import Console
from rich.panel import Panel

from consulta_vacantes_mep.settings import default_year

MIN_YEAR = 2000
MAX_YEAR = 2100

MENU_OPTIONS = {
    "1": "Buscar todas las especialidades",
    "2": "Buscar especialidad por nombre",
    "3": "Actualizar la lista de vacantes",
    "4": "Salir",
}


def show_welcome_menu(console: Console) -> str:
    """Display the main menu and return the chosen option."""
    while True:
        console.clear()
        console.print(
            Panel(
                "Nombramientos y vacantes docentes",
                title="Sistema de Consulta MEP",
                width=52,
            )
        )

        for key, label in MENU_OPTIONS.items():
            console.print(f"  [bold]{key}[/bold]  {label}")

        choice = console.input("\n  Seleccione una opción: ").strip()

        if choice in MENU_OPTIONS:
            return choice

        console.print(f"\n  [yellow]Opción inválida: «{choice}». Intente de nuevo.[/yellow]")
        console.input("  Presione Enter para continuar...")


def ask_year(console: Console) -> int:
    """Prompt for a query year, falling back to the current one."""
    fallback = default_year()
    raw = console.input(f"\n  Año de consulta [{fallback}]: ").strip()

    if not raw:
        return fallback

    if not raw.isdigit() or not (MIN_YEAR <= int(raw) <= MAX_YEAR):
        console.print(f"  [yellow]Año inválido. Se usará {fallback}.[/yellow]")
        return fallback

    return int(raw)
