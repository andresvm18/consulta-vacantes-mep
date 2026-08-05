"""Progress events emitted by the scrapers.

The scrapers used to print directly, which made them unusable from anything but
a terminal. They now emit these records instead, and whoever runs them decides
what to do with each one: draw a progress bar, update a widget, or ignore it.

The events carry data, never formatted text. A phase reports how many items it
is about to process, one event per finished item, and a summary at the end. That
is enough to render progress without the scraper knowing how it will look.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Phase(Enum):
    """Which of the two scraping passes an event belongs to."""
    VACANCIES = "vacancies"
    APPOINTMENTS = "appointments"


@dataclass(frozen=True, slots=True)
class PhaseStarted:
    """A phase is about to process `total` items.

    concurrency is the number of browsers that will run at once, and is set
    only for the appointments phase. The vacancies phase drives a single page,
    so there is nothing to report.
    """

    phase: Phase
    total: int
    concurrency: int | None = None


@dataclass(frozen=True, slots=True)
class ItemCompleted:
    """One regional office or one vacancy number finished processing.

    label is the office name or the vacancy number, whichever the phase works
    on. count is how many records it produced, and None means the item failed
    and the run continued without it.
    """

    phase: Phase
    index: int
    total: int
    label: str
    count: int | None


@dataclass(frozen=True, slots=True)
class PhaseFinished:
    """A phase is over.

    total is the number of records collected, not the number of items
    processed. failed counts the items that produced no result because the
    query could not be completed.
    """

    phase: Phase
    total: int
    failed: int = 0


Event = PhaseStarted | ItemCompleted | PhaseFinished


class Reporter(Protocol):
    """Receives progress events from a scraping run.

    A single method rather than one per event type: a consumer connects once
    and matches on the event, and adding an event later does not break the
    implementations that do not care about it.
    """

    def emit(self, event: Event, /) -> None: ...


class NullReporter:
    """Discards every event.

    The default for the scrapers, so they can be called from a test or a script
    without a reporter having to be built first.
    """

    def emit(self, _event: Event, /) -> None:
      return
