"""Application logging.

Uses the standard library logging module with rotating file handlers. Two files
are written: an activity log at the configured level, and an error-only log
that isolates failures for quick inspection.

Modules obtain a logger with get_logger(__name__) and never configure handlers
themselves. Configuration happens once, from the entry point.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from consulta_vacantes_mep.settings import LOGGING
from consulta_vacantes_mep.utils.paths import LOG_DIR

LOG_FILE = LOG_DIR / "activity.log"
ERROR_FILE = LOG_DIR / "errors.log"

_FILE_FORMAT = "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_ROOT_LOGGER_NAME = "consulta_vacantes_mep"

logger = logging.getLogger(_ROOT_LOGGER_NAME)

def _build_file_handler(path, level: int) -> RotatingFileHandler:
    """Create a size-limited file handler that keeps a few old copies."""
    handler = RotatingFileHandler(
        path,
        maxBytes=LOGGING.max_bytes,
        backupCount=LOGGING.backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT))
    return handler


def configure_logging(level: str | None = None) -> None:
    """Attach handlers to the package logger. Safe to call more than once."""
    logger = logging.getLogger(_ROOT_LOGGER_NAME)

    if logger.handlers:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    resolved_level = getattr(logging, (level or LOGGING.level).upper(), logging.INFO)

    logger = logging.getLogger(_ROOT_LOGGER_NAME)
    logger.setLevel(resolved_level)

    # Do not let records climb to the root logger, which would duplicate output
    # if any dependency configures it.
    logger.propagate = False

    logger.addHandler(_build_file_handler(LOG_FILE, resolved_level))
    logger.addHandler(_build_file_handler(ERROR_FILE, logging.ERROR))

    # Warnings and above also go to stderr, so a user running the CLI sees that
    # something went wrong without opening a log file. Routine INFO records stay
    # out of the terminal: the console layer owns what the user reads.
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter("  %(levelname)s: %(message)s"))
    logger.addHandler(stderr_handler)



def get_logger(name: str) -> logging.Logger:
    """Return a logger nested under the package logger.

    Passing __name__ from a module inside the package yields the right name
    automatically, so log lines identify their origin.
    """
    if not name.startswith(_ROOT_LOGGER_NAME):
        name = f"{_ROOT_LOGGER_NAME}.{name}"

    return logging.getLogger(name)
