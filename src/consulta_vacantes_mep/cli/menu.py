from consulta_vacantes_mep.settings import default_year
from consulta_vacantes_mep.utils.console import clear_screen

MIN_YEAR = 2000
MAX_YEAR = 2100

MENU_OPTIONS = {
    "1": "Buscar todas las especialidades",
    "2": "Buscar especialidad por nombre",
    "3": "Salir",
}

def _divider(char="─", width=52):
    return char * width


def _print_header():
    print()
    print(_divider("═"))
    print("  Sistema de Consulta MEP".center(52))
    print("  Nombramientos y vacantes docentes".center(52))
    print(_divider("═"))


def _print_options():
    print()
    for key, label in MENU_OPTIONS.items():
        print(f"  [{key}]  {label}")
    print()
    print(_divider())


def show_welcome_menu() -> str:
    """Display the main menu and return the chosen option (1-3)."""
    while True:
        clear_screen()
        _print_header()
        _print_options()
        choice = input("  Seleccione una opción: ").strip()

        if choice in MENU_OPTIONS:
            return choice

        print(f"\n  ✗  Opción inválida: «{choice}». Intente de nuevo.")


def ask_year() -> int:
    """Prompt for a query year, falling back to the current one."""
    fallback = default_year()

    print()
    raw = input(f"  Año de consulta [{fallback}]: ").strip()

    if not raw:
        return fallback

    if not raw.isdigit() or not (MIN_YEAR <= int(raw) <= MAX_YEAR):
        print(f"  ✗  Año inválido. Se usará {fallback}.")
        return fallback

    return int(raw)
