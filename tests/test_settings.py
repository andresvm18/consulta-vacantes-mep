"""Checks on configuration loading and environment overrides."""

from datetime import datetime

import pytest

from consulta_vacantes_mep.settings import (
    ExportSettings,
    ScrapingSettings,
    default_year,
)


def test_default_year_is_current_year() -> None:
    assert default_year() == datetime.now().astimezone().year


def test_concurrency_reads_environment_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CVM_MAX_CONCURRENCY", "7")
    assert ScrapingSettings().max_concurrency == 7


def test_concurrency_ignores_non_numeric_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CVM_MAX_CONCURRENCY", "not-a-number")
    assert ScrapingSettings().max_concurrency == 4


def test_settings_are_immutable() -> None:
    settings = ScrapingSettings()

    with pytest.raises(AttributeError):
        settings.max_retries = 99  # type: ignore[misc]


# ── The personal data switch ──────────────────────────────────────────────────
def test_personal_data_is_left_out_unless_configured() -> None:
    """The safe default is the one nobody has to remember to choose."""
    assert ExportSettings().include_personal_data is False


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on"])
def test_personal_data_reads_environment_override(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CVM_EXPORT_PERSONAL_DATA", raw)
    assert ExportSettings().include_personal_data is True


@pytest.mark.parametrize("raw", ["0", "false", "no", "off"])
def test_personal_data_can_be_turned_back_off(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CVM_EXPORT_PERSONAL_DATA", raw)
    assert ExportSettings().include_personal_data is False


@pytest.mark.parametrize("raw", ["", "  ", "maybe", "2", "sí"])
def test_an_unrecognised_value_does_not_turn_it_on(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typo in an environment variable must not be what publishes a cédula."""
    monkeypatch.setenv("CVM_EXPORT_PERSONAL_DATA", raw)
    assert ExportSettings().include_personal_data is False
