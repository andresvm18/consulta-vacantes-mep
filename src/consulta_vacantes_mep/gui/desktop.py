"""Handing a file or a folder over to Windows.

Opening is asked of Qt, which hands the path to whatever the system uses for it:
Excel for a workbook, Explorer for a folder. Showing a file inside its folder is
not something Qt offers, so on Windows it is asked of Explorer directly, which
opens the folder with that one file already selected. Anywhere else the folder
is opened instead, which is the closest thing every desktop has.

Each function says whether it worked rather than raising. A file that could not
be opened is not a failure of the export that wrote it, and what the user is
told about it is the window's decision.
"""

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)


def _open_url(url: QUrl) -> bool:
    """The one call into Qt, on its own so a test can stand in for it."""
    return QDesktopServices.openUrl(url)


def open_path(path: Path) -> bool:
    """Open a file or a folder with whatever the system uses for it."""
    opened = _open_url(QUrl.fromLocalFile(str(path)))

    if not opened:
        logger.warning("The system would not open %s", path)

    return opened


def open_folder(folder: Path) -> bool:
    """Open a folder, creating it first if nothing has been written there yet.

    Created rather than refused: the button that calls this is there from the
    first launch, before any export, and an error for an empty folder that
    simply does not exist yet would read as something being broken.
    """
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.exception("The folder %s could not be created", folder)
        return False

    return open_path(folder)


def _explorer() -> Path:
    """Explorer by its full path, so no other explorer.exe on the PATH is run."""
    return Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "explorer.exe"


def show_in_folder(file: Path) -> bool:
    """Open the folder holding a file, with the file selected where possible."""
    if sys.platform != "win32":
        return open_path(file.parent)

    # "/select," and the path as two arguments rather than one. Joined, a path
    # with spaces in it gets quoted around the switch as well, and Explorer is
    # particular about how /select is quoted.
    try:
        subprocess.Popen([str(_explorer()), "/select,", str(file)])
    except OSError:
        logger.exception("Explorer could not be started for %s", file)
        return False

    return True
