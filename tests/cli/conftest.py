"""Keeping the CLI tests out of a real browser.

The Typer callback runs before every subcommand and checks for Chromium by
launching one, which is right in production and wrong in a test: it costs a
second per invocation and needs a browser present to reach code that has
nothing to do with browsers.

The patch is autouse rather than something each test requests, so not
launching is the default for this directory and there is nothing to forget.

The module is fetched by name instead of imported as an attribute. The cli
package reexports the main function, which shadows the main submodule, so
'from consulta_vacantes_mep.cli import main' hands back the function. The
string form of monkeypatch.setattr has the same problem, since pytest resolves
it with getattr.
"""

import importlib

import pytest
from typer.testing import CliRunner

main_module = importlib.import_module("consulta_vacantes_mep.cli.main")


@pytest.fixture(autouse=True)
def chromium_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "chromium_is_available", lambda: True)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
