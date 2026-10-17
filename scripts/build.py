"""Build the Windows executable, with the browser it needs inside it.

Two steps, and the order is the point. Playwright is told to install the
headless Chromium into its own package directory instead of the user's profile,
and only then is PyInstaller run, so the browser is collected as package data
and travels with the executable. The spec refuses to build without it, since
a frozen build has nowhere to download one to and could not run a search.

Only the headless shell is installed. The application never shows a browser
window, and the full Chromium would be a second copy of the same engine that
nothing here starts.

Usage, from the repository root with the virtual environment active:
    pip install -e ".[build]"
    python scripts/build.py

The result is dist/ConsultaVacantesMEP/, a folder to be distributed whole. It
holds two executables over one _internal: "Consulta Vacantes MEP.exe", the
window, with no console; and consulta-vacantes-mep.exe, the subcommands, for a
terminal.

The licenses go beside them, at the top of the folder where a person looks
rather than inside _internal: this project's own, the NOTICE, and what the LGPL
asks of anyone distributing Qt, which is its text, the GPL text it builds on,
and where to get the source of the exact version bundled. That last one is
written here rather than kept in the repository, because the version is only
known once the build has picked it up.
"""

import os
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "ConsultaVacantesMEP.spec"
OUTPUT = ROOT / "dist" / "ConsultaVacantesMEP"

# .txt on the copies, so a double click opens them on Windows.
PROJECT_LICENSES = {"LICENSE": "LICENSE.txt", "NOTICE": "NOTICE.txt"}
THIRD_PARTY_LICENSES = ROOT / "licenses"

QT_NOTICE = """\
Qt for Python: PySide6-Essentials {pyside} and shiboken6 {shiboken}

This application uses Qt for Python, the official Python bindings for the Qt
toolkit, under the GNU Lesser General Public License version 3. The full text
of that license, and of the GNU General Public License version 3 it builds on,
are in this folder as LGPL-3.0.txt and GPL-3.0.txt.

The Qt libraries are the DLL and PYD files in _internal\\PySide6 and
_internal\\shiboken6. They are loaded at run time, have not been modified, and
may be replaced with your own build of the same or a compatible version.

The source code of this version of Qt for Python is published by The Qt
Company at:

    https://download.qt.io/official_releases/QtForPython/
    https://code.qt.io/cgit/pyside/pyside-setup.git/ (tag v{pyside})

and of the Qt libraries it is built on, Qt {pyside}, at:

    https://download.qt.io/official_releases/qt/
"""


def _run(*args: str, env: dict[str, str] | None = None) -> None:
    """Run a module of this interpreter, stopping the build if it fails."""
    command = [sys.executable, "-m", *args]
    print(f"\n> {' '.join(command[1:])}", flush=True)
    subprocess.run(command, check=True, cwd=ROOT, env=env)


def _size_in_megabytes(folder: Path) -> float:
    total = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
    return total / (1024 * 1024)


def _ship_licenses() -> None:
    """Put the licenses at the top of the built folder, beside the executables."""
    for source, name in PROJECT_LICENSES.items():
        shutil.copyfile(ROOT / source, OUTPUT / name)

    target = OUTPUT / "licenses"
    target.mkdir(exist_ok=True)

    for text in sorted(THIRD_PARTY_LICENSES.glob("*.txt")):
        shutil.copyfile(text, target / text.name)

    notice = QT_NOTICE.format(
        pyside=version("PySide6-Essentials"), shiboken=version("shiboken6")
    )
    (target / "Qt-source.txt").write_text(notice, encoding="utf-8")


def main() -> int:
    # 0 means "inside the playwright package", which is where collect_all looks.
    # Set for the install only: the developer's own runs keep using the
    # browsers in their profile.
    install_env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": "0"}

    try:
        _run("playwright", "install", "--only-shell", "chromium", env=install_env)
        _run("PyInstaller", "--noconfirm", "--clean", str(SPEC))

    except subprocess.CalledProcessError as error:
        print(f"\nThe build failed at: {' '.join(error.cmd[1:])}", file=sys.stderr)
        return 1

    _ship_licenses()

    print(f"\nBuilt {OUTPUT} ({_size_in_megabytes(OUTPUT):.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
