"""Opening the window.

Assembles what the window needs and hands it an event loop. The pieces are the
same ones the terminal interface uses: a Session over the scrapers, a worker to
keep the search off this thread, and a reporter to carry progress back.

The browser is checked before the window is shown rather than after. The check
costs about three quarters of a second and an install costs a minute, and
neither is something to do behind a window that is already up and looking
responsive.
"""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from consulta_vacantes_mep.app.session import Session
from consulta_vacantes_mep.app.startup import ensure_chromium
from consulta_vacantes_mep.gui.reporter import QtReporter
from consulta_vacantes_mep.gui.window import MainWindow
from consulta_vacantes_mep.gui.worker import SearchWorker
from consulta_vacantes_mep.utils.logger import configure_logging, get_logger
from consulta_vacantes_mep.utils.playwright_setup import ChromiumStatus

logger = get_logger(__name__)

# What a failed startup means to someone looking at a dialog. Deliberately not
# shared with the terminal's wording: the same fact reads differently in a box
# with an OK button than on a line of output, and one of these is the only thing
# the user will see before the application gives up.
CHROMIUM_MESSAGES = {
    ChromiumStatus.NOT_INSTALLABLE: (
        "La aplicación debería incluir el navegador que necesita y no lo trae.\n\n"
        "Vuelva a instalarla."
    ),
    ChromiumStatus.FAILED: (
        "No se pudo descargar el navegador que la aplicación necesita.\n\n"
        "Revise su conexión y vuelva a abrirla. Si el problema sigue, instálelo "
        "desde una terminal con:\n\npython -m playwright install chromium"
    ),
}

DOWNLOAD_TITLE = "Falta el navegador"
DOWNLOAD_MESSAGE = (
    "La aplicación necesita descargar el navegador que usa para consultar el "
    "sitio del MEP.\n\nLa descarga empieza al aceptar y puede tardar un minuto."
)

FAILURE_TITLE = "No se puede continuar"


def _tell(title: str, text: str) -> None:
    """Show something the user has to acknowledge.

    Wrapped so a test can replace it. A modal dialog under the offscreen
    platform waits for a click that is never coming, and what is worth checking
    here is which message was chosen, not that Qt can draw a box.
    """
    QMessageBox.information(None, title, text)


def _complain(title: str, text: str) -> None:
    QMessageBox.critical(None, title, text)


def prepare_browser() -> bool:
    """Make sure a browser is there, and say so in a dialog if it is not.

    The sequence is app/startup.py, shared with the terminal interface. What is
    here is the wording and the fact that it arrives in a box.
    """
    result = ensure_chromium(
        before_install=lambda: _tell(DOWNLOAD_TITLE, DOWNLOAD_MESSAGE)
    )

    if result.ok:
        return True

    _complain(FAILURE_TITLE, CHROMIUM_MESSAGES[result.status])
    return False


def build_window() -> MainWindow:
    """Wire up a window and everything behind it.

    One Session for the life of the window, because the vacancy cache lives in
    it and that is what makes a second search cheap.
    """
    reporter = QtReporter()

    return MainWindow(SearchWorker(Session(reporter=reporter)), reporter)


def main() -> int:
    """Run the window, and return what the process should exit with."""
    # Reused rather than always created. Qt allows one application object per
    # process and raises on a second, so taking the existing one keeps this
    # callable from a test and from anything that already set Qt up.
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)

    # No console is passed: there is no terminal the user is reading, and a
    # windowed build has no standard output to fall back on. Warnings go to the
    # log files, which is where a windowed application's user is pointed.
    configure_logging()

    if not prepare_browser():
        logger.error("The window was not opened: no usable browser")
        return 1

    window = build_window()
    window.show()

    return app.exec()
