"""Keeping the CLI tests out of a real browser.

The Typer callback runs before every subcommand and checks for Chromium by
launching one, which is right in production and wrong in a test: it costs a
second per invocation and needs a browser present to reach code that has
nothing to do with browsers.

The patch is autouse rather than something each test requests, so not launching
is the default for this directory and there is nothing to forget.

It is applied to app.startup, where the check is now called from, rather than
to the CLI module that used to call it. One seam covers every interface that
goes through the startup sequence, which is the point of the sequence living
there.
"""

import pytest
from typer.testing import CliRunner

from consulta_vacantes_mep.app import startup


@pytest.fixture(autouse=True)
def chromium_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(startup, "chromium_is_available", lambda: True)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
