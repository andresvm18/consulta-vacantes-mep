"""Checks on configuration loading and environment overrides."""

from datetime import datetime

import pytest

from consulta_vacantes_mep.settings import ScrapingSettings, default_year


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
