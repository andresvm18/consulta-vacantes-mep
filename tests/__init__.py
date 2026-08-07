"""Marks the test suite as a package.

Without it, tests/conftest.py and tests/cli/conftest.py are both the top level
module 'conftest', and mypy refuses to resolve two modules to one name.
"""
