import os


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_section(title: str, width: int = 48) -> None:
    print(f"\n  {'─' * width}")
    print(f"  {title}")
    print(f"  {'─' * width}")


def print_progress(current: int, total: int, label: str, count: int) -> None:
    bar_width = 30
    filled = int(bar_width * current / total)
    bar = "█" * filled + "░" * (bar_width - filled)
    pct = int(100 * current / total)
    print(f"\r  [{bar}] {pct:>3}%  {label[:28]:<28}  {count} vacante(s)", end="", flush=True)


def print_result(index: int, total: int, vacancy: str, count: int | None) -> None:
    status = f"{count} nombramiento(s)" if count is not None else "error, se continúa"
    icon = "✓" if count else ("✗" if count is None else "·")
    print(f"  [{index:>{len(str(total))}}/{total}] {icon}  Vacante {vacancy}: {status}")
