"""Drawing a scraping run on the terminal.

The scrapers report what happened; this decides how it reads. One progress bar
per phase, because the appointments phase runs four browsers at once and its
results arrive in whatever order they finish, which a list of lines turns into
noise. Failures are printed as they happen, since those are the lines worth
reading.
"""

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from consulta_vacantes_mep.events import (
    Event,
    ItemCompleted,
    Phase,
    PhaseFinished,
    PhaseStarted,
)

_PHASE_TITLES = {
    Phase.VACANCIES: "Vacantes",
    Phase.APPOINTMENTS: "Nombramientos",
}

# Room for the longest regional office name without pushing the bar around.
_LABEL_WIDTH = 34


class RichReporter:
    """Renders progress events as a live progress bar."""

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()
        self._progress: Progress | None = None
        self._task: TaskID | None = None

    def emit(self, event: Event, /) -> None:
        match event:
            case PhaseStarted():
                self._start(event)

            case ItemCompleted():
                self._advance(event)

            case PhaseFinished():
                self._finish(event)

    def close(self) -> None:
        """Take down the live display, whatever state the run ended in.

        A phase that raises never emits its closing event, and a progress bar
        left running would keep the terminal in its alternate drawing mode. The
        entry point calls this from a finally block.
        """
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
            self._task = None

    def _start(self, event: PhaseStarted) -> None:
        self.close()

        title = _PHASE_TITLES[event.phase]
        detail = f" · {event.concurrency} en paralelo" if event.concurrency else ""
        self._console.print(f"\n[bold]{title}[/bold]  {event.total} por consultar{detail}")

        self._progress = Progress(
            TextColumn("  "),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TextColumn("{task.fields[current]}", style="dim"),
            TimeElapsedColumn(),
            console=self._console,
        )
        self._progress.start()
        self._task = self._progress.add_task(title, total=event.total, current="")

    def _advance(self, event: ItemCompleted) -> None:
        if self._progress is None or self._task is None:
            return

        if event.count is None:
            self._progress.console.print(f"  [yellow]✗[/yellow]  {event.label}: sin respuesta")

        label = event.label[:_LABEL_WIDTH].ljust(_LABEL_WIDTH)
        self._progress.update(self._task, advance=1, current=label)

    def _finish(self, event: PhaseFinished) -> None:
        self.close()

        noun = "vacantes" if event.phase is Phase.VACANCIES else "nombramientos"
        summary = f"  Total: {event.total} {noun}"

        if event.failed:
            summary += f", [yellow]{event.failed} sin respuesta[/yellow]"

        self._console.print(summary)
