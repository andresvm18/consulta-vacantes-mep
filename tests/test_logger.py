"""What actually reaches the log files.

The pattern is covered in test_redaction.py. What is covered here is the wiring,
which is the half that can be silently wrong: a correct pattern attached to
nothing redacts nothing, and the failure looks exactly like success until
somebody opens the file.

Every test configures logging against a temporary directory and takes the
handlers down afterwards, since the package logger is process-wide state.
"""

import logging
from collections.abc import Iterator
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from consulta_vacantes_mep.utils import logger as logger_module
from consulta_vacantes_mep.utils.logger import configure_logging, get_logger
from consulta_vacantes_mep.utils.redaction import REDACTED

CEDULA = "102340567"
VACANCY = "1536996"


@pytest.fixture
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point logging at a temporary directory, and leave no handlers behind."""
    package_logger = logging.getLogger("consulta_vacantes_mep")
    saved = list(package_logger.handlers)
    package_logger.handlers.clear()

    monkeypatch.setattr(logger_module, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_module, "LOG_FILE", tmp_path / "activity.log")
    monkeypatch.setattr(logger_module, "ERROR_FILE", tmp_path / "errors.log")

    yield tmp_path

    for handler in package_logger.handlers:
        handler.close()

    package_logger.handlers.clear()
    package_logger.handlers.extend(saved)


def _activity(log_dir: Path) -> str:
    return (log_dir / "activity.log").read_text(encoding="utf-8")


# ── The identifier never reaches the file ─────────────────────────────────────
def test_an_identifier_in_a_message_does_not_reach_the_file(log_dir: Path) -> None:
    configure_logging(level="DEBUG")

    get_logger("consulta_vacantes_mep.test").warning("appointed %s", CEDULA)

    written = _activity(log_dir)

    assert CEDULA not in written
    assert REDACTED in written


def test_a_child_logger_is_redacted_too(log_dir: Path) -> None:
    """Every module logs through get_logger(__name__), so the records that
    matter all arrive from children of the package logger. A filter on the
    package logger would never have seen one of them."""
    configure_logging(level="DEBUG")

    get_logger("consulta_vacantes_mep.scrapers.appointments").info(
        "vacancy %s: appointed %s", VACANCY, CEDULA
    )

    written = _activity(log_dir)

    assert CEDULA not in written
    assert VACANCY in written


def test_an_identifier_inside_a_traceback_does_not_reach_the_file(
    log_dir: Path,
) -> None:
    """The reason this is a formatter and not a filter: when a filter runs, the
    traceback has not been rendered yet."""
    configure_logging(level="DEBUG")

    try:
        message = f"row for {CEDULA} could not be read"
        raise ValueError(message)
    except ValueError:
        get_logger("consulta_vacantes_mep.test").exception("parsing failed")

    written = _activity(log_dir)

    assert "Traceback" in written
    assert CEDULA not in written


def test_an_identifier_does_not_reach_the_error_file(log_dir: Path) -> None:
    """Two file handlers are configured, and each formats the record itself."""
    configure_logging(level="DEBUG")

    get_logger("consulta_vacantes_mep.test").error("appointed %s", CEDULA)

    written = (log_dir / "errors.log").read_text(encoding="utf-8")

    assert CEDULA not in written
    assert REDACTED in written


@pytest.mark.usefixtures("log_dir")
def test_an_identifier_does_not_reach_the_console() -> None:
    """The screen handler shares the interface's Rich console, so a warning
    lands where the user can read it, and read it back later from scrollback."""
    buffer = StringIO()
    configure_logging(level="DEBUG", console=Console(file=buffer, width=200))

    get_logger("consulta_vacantes_mep.test").warning("appointed %s", CEDULA)

    assert CEDULA not in buffer.getvalue()
    assert REDACTED in buffer.getvalue()


# ── The log stays worth reading ───────────────────────────────────────────────
def test_the_rest_of_the_record_survives(log_dir: Path) -> None:
    configure_logging(level="DEBUG")

    get_logger("consulta_vacantes_mep.parsing").warning(
        "vacancy %s: discarding row", VACANCY
    )

    written = _activity(log_dir)

    assert VACANCY in written
    assert "discarding row" in written
    assert "consulta_vacantes_mep.parsing" in written
    assert REDACTED not in written


def test_a_percent_sign_in_a_message_survives_formatting(log_dir: Path) -> None:
    """The formatter runs after the arguments have been merged in, so a literal
    percent in the result is text rather than a format specifier."""
    configure_logging(level="DEBUG")

    get_logger("consulta_vacantes_mep.test").info("progress: 50%% of %s", VACANCY)

    assert "progress: 50% of" in _activity(log_dir)


# ── Configuration ─────────────────────────────────────────────────────────────
@pytest.mark.usefixtures("log_dir")
def test_configuring_twice_does_not_double_the_handlers() -> None:
    configure_logging(level="DEBUG")
    before = len(logging.getLogger("consulta_vacantes_mep").handlers)

    configure_logging(level="DEBUG")

    assert len(logging.getLogger("consulta_vacantes_mep").handlers) == before


@pytest.mark.usefixtures("log_dir")
def test_every_handler_redacts() -> None:
    """A handler added without the redacting formatter would leak, and nothing
    else here would notice."""
    configure_logging(level="DEBUG", console=Console(file=StringIO(), width=200))

    handlers = logging.getLogger("consulta_vacantes_mep").handlers
    formatters = [handler.formatter for handler in handlers]

    assert formatters
    assert all(isinstance(f, logger_module.RedactingFormatter) for f in formatters)
