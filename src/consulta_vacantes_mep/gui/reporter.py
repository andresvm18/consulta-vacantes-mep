"""Carrying scraping progress across into Qt.

The scrapers emit events from whichever thread is doing the work, and Qt forbids
touching a widget from anywhere but the thread that owns it. A signal is the
crossing: Qt queues the delivery and runs the slot on the receiver's thread, so
a window can update itself from an event that was born in a Playwright worker.

Only QtCore is involved. There is no widget here and no application object
needed, which keeps this testable without a display.
"""

from PySide6.QtCore import QObject, Signal, SignalInstance

from consulta_vacantes_mep.events import Event


class _Signals(QObject):
    """The signal, in the one object that has to be a QObject.

    Signals can only live on a QObject, and QtReporter deliberately is not one:
    the Reporter protocol requires a method called emit, and QObject already has
    one. Overriding it is not the harmless shadowing it looks like. QObject.emit
    is bound to C++ and emits a signal named by its signature, and calling it
    with arguments that do not match aborts the interpreter rather than raising,
    so a reporter that answered to that name would be one stray call away from a
    crash with no traceback.
    """

    progressed = Signal(object)


class QtReporter:
    """Reports scraping progress as a Qt signal.

    One signal carrying the event, rather than one signal per event type, for
    the same reason the Reporter protocol has one method: a consumer connects
    once and matches on what it gets, and an event added later does not oblige
    every consumer to grow a slot for it.
    """

    def __init__(self) -> None:
        self._signals = _Signals()

    @property
    def progressed(self) -> SignalInstance:
        """The signal to connect a window to.

        Connect from the thread that owns the widgets being updated. Qt decides
        queued or direct delivery from where the receiver lives, not from where
        emit was called.
        """
        return self._signals.progressed

    def emit(self, event: Event, /) -> None:
        """Hand one event to Qt. Safe to call from any thread."""
        self._signals.progressed.emit(event)
