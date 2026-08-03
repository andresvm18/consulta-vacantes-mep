"""Minimal checks that the package is importable and correctly installed."""

import consulta_vacantes_mep


def test_package_exposes_version() -> None:
    assert consulta_vacantes_mep.__version__


def test_entry_point_is_importable() -> None:
    from consulta_vacantes_mep.cli import main

    assert callable(main)