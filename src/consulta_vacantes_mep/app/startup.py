"""What has to be true before a run can start.

The CLI ran this sequence inline, mixed into its own console output, and a
second interface would have been a second copy of it: check for a browser,
announce a download, install, report what happened. The sequence lives here and
the interface decides only how each step reads.
"""

from collections.abc import Callable

from consulta_vacantes_mep.utils.playwright_setup import (
    ChromiumCheck,
    ChromiumStatus,
    chromium_is_available,
    install_chromium,
)


def ensure_chromium(
    *, before_install: Callable[[], None] | None = None
) -> ChromiumCheck:
    """Make Chromium usable, and report what that took.

    before_install runs only when a download is actually about to start, and
    before it starts. That ordering is the reason this is a callback rather
    than something in the return value: the download takes about a minute, and
    an interface that explains it afterwards has left the user watching nothing.

    A browser that was already present and one that was just downloaded are
    both reported as INSTALLED. The difference mattered while the sequence was
    being carried out; once it is over, ready is ready.
    """
    if chromium_is_available():
        return ChromiumCheck(ChromiumStatus.INSTALLED)

    if before_install is not None:
        before_install()

    return install_chromium()
