"""Reading Rich output the way a person reads it.

Rich colours what it writes when it believes it is attached to a terminal, and
what makes it believe that differs between a developer's machine and CI: on
GitHub Actions it colours, in a local shell running pytest it does not. The
colours are not the only difference. Rich highlights option names by styling
their parts separately, so '--datos-personales' is written as '-', '-datos' and
'-personales' with escape codes between them, and the string a test looks for
stops existing.

Assertions about what the interface says therefore run through here. None of
them are about colour, and a test that passes on one machine and fails on the
other is worse than no test.
"""

import re

# The full CSI form, not just the colour codes: a live display also moves the
# cursor, and none of that is text a person reads either.
_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def visible(text: str) -> str:
    """The characters a person sees, with the escape codes removed."""
    return _ESCAPE.sub("", text)
