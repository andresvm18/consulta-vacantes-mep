"""Exceptions raised by this application.

A bare Exception tells the caller nothing about whether retrying is worthwhile.
These types separate the failures that a retry might fix from the ones it never
will, and from the case where the query succeeded but returned nothing.
"""


class ConsultaVacantesError(Exception):
    """Base class for every error this application raises deliberately."""


class ScrapingError(ConsultaVacantesError):
    """A query against a MEP page did not complete."""


class TransientScrapingError(ScrapingError):
    """The query failed for a reason that may not recur.

    Network timeouts, a page that did not finish rendering, a temporarily
    unavailable site. Retrying is reasonable.
    """


class PermanentScrapingError(ScrapingError):
    """The query failed for a reason a retry will not fix.

    A selector that no longer exists, a form field the site removed, a change
    in page structure. Retrying only wastes time and adds load.
    """


class BotChallengeError(TransientScrapingError):
    """The site served a bot challenge instead of the requested page.

    Transient in the sense that it may pass, but the correct response is to
    slow down rather than retry immediately.
    """
