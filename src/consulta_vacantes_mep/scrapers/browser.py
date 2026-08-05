"""A browser owned entirely by the thread that uses it.

Launching Chromium costs roughly a second and several hundred megabytes, so a
worker cannot afford one per query. It also cannot share one with the other
workers: Playwright's sync API drives the browser through a greenlet bound to
the thread that started it, and any call from another thread fails with
"cannot switch to a different thread". An earlier design launched one browser
on the main thread and handed contexts out to the workers; every worker died on
its first call.

The unit of reuse is therefore one browser per worker thread, created and closed
inside that thread. With four workers that is four launches per run instead of
one per vacancy number.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import BrowserContext, sync_playwright

from consulta_vacantes_mep.settings import SCRAPING
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)


@contextmanager
def browser_session(headless: bool = SCRAPING.headless) -> Iterator[BrowserContext]:
    """Yield a browser context owned by the calling thread.

    Everything opened here is closed here, on the same thread, which is what
    Playwright's sync API requires. The context isolates cookies and storage
    from the other workers.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        logger.info("Browser launched (headless=%s)", headless)

        context = browser.new_context()

        try:
            yield context
        finally:
            context.close()
            browser.close()
            logger.info("Browser closed")