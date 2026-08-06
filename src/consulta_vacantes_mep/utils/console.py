"""Terminal rendering for a scraping run.

Temporary. The Rich reporter replaces this module once the CLI is rebuilt, and
the console UI disappears with it. It stays until then so that every commit in
between still produces a run the developer can watch.
"""

import os

from consulta_vacantes_mep.events import (
    Event,
    ItemCompleted,
    Phase,
    PhaseFinished,
    PhaseStarted,
)


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_section(title: str, width: int = 48) -> None:
    print(f"\n  {'─' * width}")
    print(f"  {title}")
    print(f"  {'─' * width}")


def print_progress(current: int, total: int, label: str, count: int | None) -> None:
    bar_width = 30
    filled = int(bar_width * current / total)
    bar = "█" * filled + "░" * (bar_width - filled)
    pct = int(100 * current / total)
    status = f"{count} vacante(s)" if count is not None else "error, se continúa"
    print(f"\r  [{bar}] {pct:>3}%  {label[:28]:<28}  {status}", end="", flush=True)


def print_result(index: int, total: int, vacancy: str, count: int | None) -> None:
    status = f"{count} nombramiento(s)" if count is not None else "error, se continúa"
    icon = "✓" if count else ("✗" if count is None else "·")
    print(f"  [{index:>{len(str(total))}}/{total}] {icon}  Vacante {vacancy}: {status}")


class ConsoleReporter:
    """Draws a scraping run on the terminal.

    Every branch here is presentation. The scrapers report what happened and
    this decides how it reads, which is the whole point of the split: the GUI
    will implement the same protocol and draw the same run differently.
    """

    def emit(self, event: Event, /) -> None:
        match event:
            case PhaseStarted(phase=Phase.VACANCIES, total=total):
                clear_screen()
                print_section(f"Vacantes MEP — {total} direcciones regionales")

            case PhaseStarted(phase=Phase.APPOINTMENTS, total=total, concurrency=workers):
                clear_screen()
                print_section(
                    f"Nombramientos MEP — {total} vacantes únicas  ·  "
                    f"{workers} consultas simultáneas"
                )

            case ItemCompleted(phase=Phase.VACANCIES):
                print_progress(event.index, event.total, event.label, event.count)

            case ItemCompleted(phase=Phase.APPOINTMENTS):
                print_result(event.index, event.total, event.label, event.count)

            case PhaseFinished(phase=Phase.VACANCIES, total=total, failed=failed):
                if failed:
                    print_section(
                        f"Total: {total} vacantes  ·  {failed} regionales no consultadas"
                    )
                else:
                    print_section(f"Total: {total} vacantes encontradas.")

            case PhaseFinished(phase=Phase.APPOINTMENTS, total=total, failed=failed):
                if failed:
                    print_section(
                        f"Total: {total} nombramientos  ·  {failed} consultas fallidas"
                    )
                else:
                    print_section(f"Total: {total} nombramientos encontrados.")
