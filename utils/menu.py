import sys

from utils.console import clear_screen

MENU_OPTIONS = {
    "1": "Buscar todas las especialidades",
    "2": "Buscar especialidad por nombre",
    "3": "Salir",
}

DEFAULT_YEAR = "2026"


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


def ask_year() -> str:
    """Prompt for a consultation year; returns DEFAULT_YEAR if input is empty or invalid."""
    print()
    year = input(f"  Año de consulta [{DEFAULT_YEAR}]: ").strip()

    if not year:
        return DEFAULT_YEAR

    if not year.isdigit() or not (2000 <= int(year) <= 2099):
        print(f"  ✗  Año inválido. Se usará {DEFAULT_YEAR}.")
        return DEFAULT_YEAR

    return year


# ── Example usage ─────────────────────────────────────────────────────────────

def main():
    while True:
        choice = show_welcome_menu()

        if choice == "3":
            print("\n  Hasta pronto.\n")
            sys.exit(0)

        year = ask_year()
        print(f"\n  → Opción {choice} — año {year}")
        print("  (Aquí iría la lógica de búsqueda…)\n")
        input("  Presione Enter para volver al menú…")
        clear_screen()


if __name__ == "__main__":
    main()