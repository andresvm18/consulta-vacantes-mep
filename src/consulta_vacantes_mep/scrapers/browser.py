"""A browser shared across concurrent queries.

Launching Chromium costs roughly one second and several hundred megabytes. The
previous design paid that cost once per vacancy number, which dominated the
runtime. One browser is launched per run, and each worker thread gets its own
context: contexts are cheap, isolate cookies and storage, and Playwright's sync
API requires that a given page is only driven from the thread that created it.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from consulta_vacantes_mep.settings import SCRAPING
from consulta_vacantes_mep.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserPool:
    """Owns one browser and hands out a context per calling thread.

    Playwright's sync API binds objects to the thread that created them, so a
    context is created lazily per thread and reused for every query that thread
    runs. With a thread pool of N workers this means N contexts total, rather
    than one browser per query.
    """

    def __init__(self, headless: bool = SCRAPING.headless) -> None:
        self._headless = headless
        self._local = threading.local()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        logger.info("Browser launched (headless=%s)", self._headless)

    def stop(self) -> None:
        """Tear down the browser, and with it every context it handed out.

        Contexts are deliberately not closed one by one. Each one belongs to
        the worker thread that created it, and Playwright's sync API rejects
        calls made from another thread, so closing them from here is what would
        fail. Closing the browser releases them all.
        """
        if self._browser is not None:
            self._browser.close()
            self._browser = None

        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

        logger.info("Browser closed")
   
   
    def _context(self) -> BrowserContext:
        """Return this thread's context, creating it on first use."""
        context: BrowserContext | None = getattr(self._local, "context", None)

        if context is None:
            if self._browser is None:
                message = "BrowserPool.start() was not called"
                raise RuntimeError(message)

            with self._lock:
                context = self._browser.new_context()

            self._local.context = context

        return context

    @contextmanager
    def page(self) -> Iterator[Page]:
        """Yield a fresh page on this thread's context."""
        page = self._context().new_page()

        try:
            yield page
        finally:
            page.close()