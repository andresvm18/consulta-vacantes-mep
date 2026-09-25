"""Removing national identification numbers from text.

The appointments registry publishes a cédula with every record, so anything
that quotes a row, a cell, or a failure involving one can carry it into a log
file that outlives the run. This module holds the pattern and the substitution;
utils/logger.py applies it to everything the handlers write.

The pattern is deliberately narrow. Redacting too eagerly would eat the vacancy
numbers a log is read for, and those are the whole point of the file.

Names are not covered, and cannot be by a pattern: any run of capitalised words
would match, including the institution and regional office names that make a
log readable. Today nothing logs one, because the only place that quotes raw
markup is parse_vacancies and a vacancy row names no person. Anything added
later that logs an appointment row would put a name in the file, and the fix
for that is not to log the row.
"""

import re

REDACTED = "[redacted]"

# Two shapes, and only two.
#
# Nine to twelve consecutive digits: what the site publishes. A cédula is nine
# (000000000 in the captured fixtures), a DIMEX for a foreign resident eleven or
# twelve. Nothing else this program logs reaches nine digits in a row: vacancy
# numbers are seven (1536996), institution codes four (4045), timeouts five
# (60000), and the timestamp in the log format is broken up by dashes and
# colons.
#
# One or two digits, then three or four, then four, hyphenated: not what the
# site publishes, but what a person types when they paste one into a bug
# report. Kept distinct from the date in the log prefix, which starts with four.
NATIONAL_ID = re.compile(
    r"\b\d{1,2}-\d{3,4}-\d{4}\b"
    r"|\b\d{9,12}\b"
)


def redact_national_ids(text: str) -> str:
    """Replace anything shaped like a national id.

    Applying this twice is the same as applying it once, which matters because
    one record is written by several handlers.
    """
    return NATIONAL_ID.sub(REDACTED, text)
