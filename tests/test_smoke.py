"""Minimal checks that the package is importable and correctly installed."""

import inspect

import consulta_vacantes_mep
from consulta_vacantes_mep import cli


def test_package_exposes_version() -> None:
    assert consulta_vacantes_mep.__version__


def test_entry_point_is_importable() -> None:
    from consulta_vacantes_mep.cli import main  # noqa: PLC0415

    assert callable(main)


def test_the_entry_module_does_not_collide_with_the_reexport() -> None:
    """The cli package reexports main, so a submodule of that name is shadowed
    by it: importing consulta_vacantes_mep.cli.main used to hand back the
    function, and reaching the module needed importlib. Naming the module entry
    is what keeps a plain import working, and renaming it back would break that
    again quietly, since the broken form still imports something callable.
    """
    assert inspect.isfunction(cli.main)
    assert inspect.ismodule(cli.entry)
