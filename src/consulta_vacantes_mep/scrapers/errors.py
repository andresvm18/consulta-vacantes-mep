"""Classification of Playwright failures into the application's error types."""

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from consulta_vacantes_mep.exceptions import (
    BotChallengeError,
    PermanentScrapingError,
    TransientScrapingError,
)

# Cloudflare serves an interstitial instead of the requested page. The
# appointments site runs behind it, so this is a real possibility under load.
CHALLENGE_MARKERS = (
    "cdn-cgi/challenge-platform",
    "Just a moment",
    "Verifying you are human",
)


def detect_challenge(page: Page) -> None:
    """Raise if the current page is a bot challenge rather than real content."""
    title = page.title()

    if any(marker in title for marker in CHALLENGE_MARKERS):
        raise BotChallengeError(f"Bot challenge served (title: {title!r})")


def classify(error: Exception, context: str) -> TransientScrapingError | PermanentScrapingError:
    """Map a Playwright exception onto an application error type.

    A timeout usually means the site was slow, which a retry may fix. A missing
    selector usually means the page changed, which a retry never fixes.
    """
    if isinstance(error, PlaywrightTimeout):
        return TransientScrapingError(f"{context}: timed out ({error})")

    if isinstance(error, PlaywrightError):
        message = str(error).lower()

        if "not found" in message or "no element" in message or "resolve" in message:
            return PermanentScrapingError(f"{context}: page structure changed ({error})")

        return TransientScrapingError(f"{context}: browser error ({error})")

    return TransientScrapingError(f"{context}: unexpected error ({error})")
