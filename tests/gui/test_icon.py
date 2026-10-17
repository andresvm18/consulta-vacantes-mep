"""The application icon: that it is there, that it is usable, and that it is set.

A missing or unreadable icon fails silently. QIcon takes a path that does not
exist and hands back an empty icon, and the window opens with Qt's generic one
in the title bar, which nobody connects to a file that moved.

The file is checked for the sizes Windows asks for, since a single small image
is accepted everywhere and only looks wrong in the places that show it large:
the desktop, Explorer's large icon view, a high resolution screen.
"""

import struct
from pathlib import Path

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from consulta_vacantes_mep.gui import entry as entry_module
from consulta_vacantes_mep.gui.entry import ICON_FILE, main

# What Windows picks from, depending on where the icon is drawn. 256 is stored
# as 0 in the directory entry, since the field is one byte.
REQUIRED_SIZES = {16, 24, 32, 48, 256}


def _sizes_in(path: Path) -> list[tuple[int, int]]:
    """Read the image sizes from an ICO directory, without an imaging library."""
    data = path.read_bytes()

    _reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert kind == 1, "not an icon file"

    sizes: list[tuple[int, int]] = []

    for index in range(count):
        width, height = struct.unpack("<BB", data[6 + 16 * index : 8 + 16 * index])
        sizes.append((width or 256, height or 256))

    return sizes


def test_the_icon_is_in_the_package() -> None:
    assert ICON_FILE.is_file()


def test_every_image_in_it_is_square() -> None:
    """Windows stretches or pads one that is not."""
    assert all(width == height for width, height in _sizes_in(ICON_FILE))


def test_it_carries_the_sizes_windows_asks_for() -> None:
    widths = {width for width, _ in _sizes_in(ICON_FILE)}

    assert widths >= REQUIRED_SIZES


def test_qt_can_read_it() -> None:
    """The check that matters at run time. An empty icon here is exactly what
    a wrong path or a missing image plugin would produce."""
    icon = QIcon(str(ICON_FILE))

    assert not icon.isNull()
    assert icon.availableSizes()


def test_the_application_carries_it_before_any_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Set before the browser check, so even the dialog saying the window cannot
    open shows it. Run down that path so no window is built."""
    monkeypatch.setattr(entry_module, "prepare_browser", lambda: False)

    main()

    app = QApplication.instance()

    assert isinstance(app, QApplication)
    assert not app.windowIcon().isNull()
