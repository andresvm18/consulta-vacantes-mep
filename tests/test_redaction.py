"""What counts as a national id, and what must not be mistaken for one.

The pattern is the whole of this feature, so both halves are pinned: the shapes
it has to catch, and the values a log is read for that it has to leave alone.
"""

import pytest

from consulta_vacantes_mep.utils.redaction import REDACTED, redact_national_ids


# ── What gets removed ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text",
    [
        "000000000",  # the shape the captured fixtures carry
        "112345678",
        "1-2345-6789",  # the shape a person types into a bug report
        "12-345-6789",
        "10123456789",  # DIMEX, eleven digits
        "101234567890",  # DIMEX, twelve
    ],
)
def test_an_identifier_does_not_survive(text: str) -> None:
    assert redact_national_ids(text) == REDACTED


def test_an_identifier_inside_a_sentence_is_removed() -> None:
    assert redact_national_ids("appointment for 102340567 rejected") == (
        f"appointment for {REDACTED} rejected"
    )


def test_every_identifier_in_a_line_is_removed() -> None:
    """One row of captured HTML can carry more than one."""
    redacted = redact_national_ids("102340567 and 987654321")

    assert redacted == f"{REDACTED} and {REDACTED}"


def test_an_identifier_inside_markup_is_removed() -> None:
    """parse_vacancies logs a slice of a row's HTML when it cannot read it, and
    the appointments grid has the same shape."""
    row = '<td data-title="Cédula">000000000</td><td>PEREZ PEREZ JUAN</td>'

    assert "000000000" not in redact_national_ids(row)


# ── What survives ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("1536996", "a vacancy number, seven digits, the point of the log"),
        ("4045", "an institution code"),
        ("60000", "a timeout in milliseconds"),
        ("03/08/2026", "a date as the site publishes it"),
        ("2026-09-25 10:07:31", "the timestamp the log format writes"),
        ("MT 4", "a group"),
        ("No Consta", "an eligibility rating"),
    ],
)
def test_what_a_log_is_read_for_is_left_alone(text: str, why: str) -> None:
    assert redact_national_ids(text) == text, why


def test_a_vacancy_number_survives_next_to_an_identifier() -> None:
    """The line has to stay useful after the redaction, not just safe."""
    redacted = redact_national_ids("vacancy 1536996: appointed 102340567")

    assert redacted == f"vacancy 1536996: appointed {REDACTED}"


def test_a_whole_log_line_keeps_its_shape() -> None:
    line = "[2026-09-25 10:07:31] WARNING  consulta_vacantes_mep.parsing: 000000000"

    assert redact_national_ids(line) == (
        f"[2026-09-25 10:07:31] WARNING  consulta_vacantes_mep.parsing: {REDACTED}"
    )


# ── Applying it twice ─────────────────────────────────────────────────────────
def test_redacting_twice_changes_nothing_further() -> None:
    """One record is written by several handlers, each with its own formatter."""
    once = redact_national_ids("appointed 102340567")

    assert redact_national_ids(once) == once


def test_text_with_nothing_to_redact_comes_back_unchanged() -> None:
    assert redact_national_ids("Browser launched (headless=True)") == (
        "Browser launched (headless=True)"
    )
