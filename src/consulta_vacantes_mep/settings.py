"""Application configuration.

Every tunable value lives here. Modules import from this file instead of
declaring their own constants, so a change takes effect in exactly one place.

Values can be overridden through environment variables prefixed with
CVM_ (for example, CVM_MAX_CONCURRENCY=4). This keeps the defaults safe for
end users while letting the developer tune behavior without editing code.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime


def _env_int(name: str, default: int) -> int:
    """Read an integer from the environment, falling back on any bad value."""
    raw = os.environ.get(name)

    if raw is None:
        return default

    try:
        return int(raw)
    except ValueError:
        return default


def default_year() -> int:
    """Return the year to query when the user does not specify one."""
    return datetime.now().astimezone().year


@dataclass(frozen=True)
class ScrapingSettings:
    """Timing and concurrency limits for browser automation."""

    vacancies_url: str = "https://apps.mep.go.cr/formulario"
    appointments_url: str = "https://apps.mep.go.cr/consultanombramientos/"

    # How many appointment lookups may run at once. Kept low by default:
    # this tool queries a public government site and should not behave like a
    # load test. Raise it deliberately, not casually.
    max_concurrency: int = field(
        default_factory=lambda: _env_int("CVM_MAX_CONCURRENCY", 4)
    )

    max_retries: int = field(default_factory=lambda: _env_int("CVM_MAX_RETRIES", 3))

    # Timeouts, in milliseconds.
    page_load_timeout_ms: int = 60_000
    postback_timeout_ms: int = 15_000
    selector_timeout_ms: int = 8_000
    cell_timeout_ms: int = 3_000

    # Waiting for the grid to settle after picking an office. Deliberately tight:
    # the observed wait is under a second, and the first attempt of a run always
    # fails because Blazor prerenders the markup before the app can respond to a
    # selection, so no wait on the DOM can tell a live app from a rendered one.
    # A short timeout with retries is cheaper than one long attempt, and adds up
    # to more patience overall, not less.
    grid_timeout_ms: int = 3_000

    # Only the fixture capture script still pauses blindly. The scrapers wait on
    # conditions instead: the AJAX runtime, the POST response, and the panel
    # having been patched.
    settle_ms: int = 1_500

    headless: bool = True


@dataclass(frozen=True)
class ExportSettings:
    """Excel output formatting."""

    header_fill_color: str = "1F4E78"
    header_font_color: str = "FFFFFF"
    max_column_width: int = 45
    timestamp_format: str = "%Y-%m-%d_%H-%M"


@dataclass(frozen=True)
class LoggingSettings:
    """Log verbosity and rotation."""

    level: str = field(default_factory=lambda: os.environ.get("CVM_LOG_LEVEL", "INFO"))
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 3


SCRAPING = ScrapingSettings()
EXPORT = ExportSettings()
LOGGING = LoggingSettings()
