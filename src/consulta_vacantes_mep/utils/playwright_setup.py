"""Making sure a usable Chromium is present before a run starts.

This module reports facts and never writes to the screen. It used to print its
own Spanish messages, which tied it to a terminal and would break a windowed
build outright: a frozen executable built with console=False has no standard
output on Windows, and print raises on the first call.

Installing is kept separate from checking so the caller can say something
before a download that takes a minute, instead of this module guessing how to
say it.
"""

import subprocess
import sys
from dataclasses import dataclass
from enum import Enum

from playwright.sync_api import sync_playwright

from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)

# Windows only. Without it the installer flashes a console window over the
# interface. getattr keeps the call portable: subprocess reads 0 as no flags.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ChromiumStatus(Enum):
    """The outcome of trying to make Chromium available."""
    INSTALLED = "installed"
    NOT_INSTALLABLE = "not_installable"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ChromiumCheck:
    """What happened, and the technical detail worth logging.

    detail is English and meant for the log. How the outcome reads to the user
    is the caller's decision, which is the whole point of returning this
    instead of printing.
    """

    status: ChromiumStatus
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.status is ChromiumStatus.INSTALLED


def chromium_is_available() -> bool:
    """Report whether a Chromium this installation can drive is present.

    Launching a browser and closing it proves more than looking for the file,
    and on Windows it measured the same: 0.71s, against 0.66s for a check that
    only reads the path. Reading the path is faster on its own, 0.43s, but it
    leaves the driver's init unfinished, and asyncio reports the cancelled task
    and its unretrieved exception when the process exits.
    """
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()

    except Exception:
        logger.warning("Chromium is not available", exc_info=True)
        return False

    return True


def install_chromium() -> ChromiumCheck:
    """Download Chromium, unless this is a build that cannot download it.

    A frozen executable is expected to ship the browser inside the package, so
    a missing Chromium there is a packaging defect rather than something to fix
    at runtime. Downloading into a temporary extraction directory would also be
    lost on the next start.
    """
    if getattr(sys, "frozen", False):
        logger.error("Chromium is missing from a frozen build")
        return ChromiumCheck(
            ChromiumStatus.NOT_INSTALLABLE, "the executable does not ship a browser"
        )

    logger.info("Installing Chromium")

    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            text=True,
            creationflags=_NO_WINDOW,
        )

    except subprocess.CalledProcessError as error:
        logger.error("Chromium installation failed: %s", error.stderr)
        return ChromiumCheck(ChromiumStatus.FAILED, error.stderr)

    except Exception as error:
        logger.exception("Chromium installation failed")
        return ChromiumCheck(ChromiumStatus.FAILED, str(error))

    logger.info("Chromium installed")
    return ChromiumCheck(ChromiumStatus.INSTALLED)
