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

The result is dist/ConsultaVacantesMEP/, a folder holding two executables over
one _internal: "Consulta Vacantes MEP.exe", the window, with no console; and
consulta-vacantes-mep.exe, the subcommands, for a terminal.

That folder is then packed into dist/Instalar-Consulta-Vacantes-MEP-<version>.exe
by Inno Setup, which is what gets distributed: it gives the user a Start menu
entry, an optional desktop shortcut and an uninstaller, without asking for
administrator rights. Inno Setup 6.3 or newer has to be installed, for example
with `winget install --id JRSoftware.InnoSetup -e`. Pass --no-installer to stop
at the folder.

The licenses go beside the executables, at the top of the folder where a person
looks rather than inside _internal: this project's own, the NOTICE, and what the LGPL
asks of anyone distributing Qt, which is its text, the GPL text it builds on,
and where to get the source of the exact version bundled. That last one is
written here rather than kept in the repository, because the version is only
known once the build has picked it up.

The other components bundled are MIT, BSD, ISC, PSF and Apache licensed, and
those licenses ask for their text to travel with a binary, not just a name in
a NOTICE. Their license files are copied from the installed distributions, so
they always match the versions in the build. A distribution with no license
file to copy fails the build rather than shipping without one.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, distribution, version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "ConsultaVacantesMEP.spec"
OUTPUT = ROOT / "dist" / "ConsultaVacantesMEP"
INSTALLER_SCRIPT = ROOT / "installer" / "ConsultaVacantesMEP.iss"

# Windows' classic limit on a path, the terminating character included. Inno
# Setup is held to it, and Chromium's files nest deep enough inside the
# Playwright package to cross it from a long checkout path: from the OneDrive
# desktop the longest came to 265, and the compiler failed with nothing but
# "the system cannot find the path specified".
MAX_PATH = 260

# .txt on the copies, so a double click opens them on Windows.
PROJECT_LICENSES = {"LICENSE": "LICENSE.txt", "NOTICE": "NOTICE.txt"}
THIRD_PARTY_LICENSES = ROOT / "licenses"

# Every distribution whose code PyInstaller's analysis put in the build, by its
# name on PyPI. Click is not here because Typer vendors it, license included.
# Qt is not here either: its wheels carry only the commercial license, and the
# LGPL texts and source notice are shipped separately.
BUNDLED_DISTRIBUTIONS = (
    "annotated-doc",
    "colorama",
    "et_xmlfile",
    "greenlet",
    "markdown-it-py",
    "mdurl",
    "openpyxl",
    "playwright",
    "pyee",
    "pygments",
    "pyinstaller",
    "rich",
    "shellingham",
    "tenacity",
    "typer",
    "typing_extensions",
)

# Matched against the file name only, from the start, so a module that merely
# mentions licenses in its name is not taken for one.
LICENSE_FILE = re.compile(
    r"^(licen[cs]e|copying|notice|authors|thirdpartynotices)", re.IGNORECASE
)

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

It can also be requested from the author of this application, through
https://github.com/andresvm18/consulta-vacantes-mep/issues, for at least three
years after this copy was distributed.
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


def _ship_dependency_licenses() -> list[str]:
    """Copy each bundled distribution's license files, and name any without one.

    A file inside the dist-info keeps its own name. One elsewhere in the
    package, such as the license of the Click that Typer vendors, is prefixed
    with its folder, so two files called LICENSE do not overwrite each other.
    """
    target = OUTPUT / "licenses" / "third-party"
    missing: list[str] = []

    for name in BUNDLED_DISTRIBUTIONS:
        try:
            dist = distribution(name)
        except PackageNotFoundError:
            missing.append(name)
            continue

        files = [
            file
            for file in dist.files or []
            if LICENSE_FILE.match(file.name) and file.suffix not in {".py", ".pyc"}
        ]

        if not files:
            missing.append(name)
            continue

        folder = target / f"{dist.metadata['Name']}-{dist.version}"
        folder.mkdir(parents=True, exist_ok=True)

        for file in files:
            inside_metadata = ".dist-info" in str(file.parent)
            copy_name = file.name if inside_metadata else f"{file.parent.name}-{file.name}"
            shutil.copyfile(Path(str(file.locate())), folder / copy_name)

    # The browser is downloaded by `playwright install`, not installed with the
    # package, so its license is not in any distribution's file list. It is in
    # the build already, deep in _internal; this puts a copy where it is seen.
    try:
        browsers = Path(
            str(distribution("playwright").locate_file("playwright/driver/package/.local-browsers"))
        )
    except PackageNotFoundError:
        browsers = Path()

    shell_licenses = sorted(browsers.glob("chromium_headless_shell-*/*/LICENSE*"))

    if shell_licenses:
        folder = target / shell_licenses[0].parent.parent.name
        folder.mkdir(parents=True, exist_ok=True)

        for license_file in shell_licenses:
            shutil.copyfile(license_file, folder / license_file.name)
    else:
        missing.append("Chromium headless shell")

    python_license = Path(sys.base_prefix) / "LICENSE.txt"

    if python_license.is_file():
        folder = target / f"Python-{sys.version.split()[0]}"
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(python_license, folder / "LICENSE.txt")
    else:
        missing.append("Python")

    return missing


def _longest_path(folder: Path) -> Path:
    """The file under folder whose full path is longest."""
    return max((path for path in folder.rglob("*") if path.is_file()), key=lambda p: len(str(p)))


def _paths_fit() -> bool:
    """Whether every file in the build is reachable by a tool held to MAX_PATH.

    Checked before Inno Setup is run, so a checkout that is too deep is named
    as the problem rather than surfacing as a path the compiler cannot find.
    """
    longest = _longest_path(OUTPUT)
    length = len(str(longest))

    if length < MAX_PATH:
        return True

    print(
        f"\nThe longest path in the build is {length} characters, and Inno Setup"
        f" cannot read one of {MAX_PATH} or more:\n    {longest}\n"
        "Move the repository somewhere shorter, such as C:\\Projects, and build again.",
        file=sys.stderr,
    )
    return False


def _find_inno_setup() -> Path | None:
    """The Inno Setup compiler, where an install of it puts it.

    ISCC in the environment wins, for an install somewhere unusual. Otherwise
    the machine-wide folders, and the per-user one winget uses when it cannot
    get administrator rights.
    """
    configured = os.environ.get("ISCC")
    candidates = [Path(configured)] if configured else []

    for variable, subfolder in (
        ("ProgramFiles(x86)", ""),
        ("ProgramFiles", ""),
        ("LOCALAPPDATA", "Programs"),
    ):
        base = os.environ.get(variable)

        if base:
            candidates.append(Path(base) / subfolder / "Inno Setup 6" / "ISCC.exe")

    return next((path for path in candidates if path.is_file()), None)


def _build_installer() -> Path | None:
    """Pack the built folder into the installer, or say why it could not be."""
    compiler = _find_inno_setup()

    if compiler is None:
        print(
            "\nInno Setup was not found. Install it with:\n"
            "    winget install --id JRSoftware.InnoSetup -e\n"
            "or set ISCC to the path of ISCC.exe, or pass --no-installer.",
            file=sys.stderr,
        )
        return None

    app_version = version("consulta-vacantes-mep")
    print(f"\n> {compiler.name} {INSTALLER_SCRIPT.name}", flush=True)

    try:
        subprocess.run(
            [str(compiler), f"/DAppVersion={app_version}", str(INSTALLER_SCRIPT)],
            check=True,
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        print("\nThe installer could not be built.", file=sys.stderr)
        return None

    return ROOT / "dist" / f"Instalar-Consulta-Vacantes-MEP-{app_version}.exe"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Windows executable.")
    parser.add_argument(
        "--no-installer",
        action="store_true",
        help="stop at dist/ConsultaVacantesMEP, without packing the installer",
    )
    arguments = parser.parse_args()

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
    missing = _ship_dependency_licenses()

    if missing:
        print(f"\nNo license file found for: {', '.join(missing)}", file=sys.stderr)
        return 1

    print(f"\nBuilt {OUTPUT} ({_size_in_megabytes(OUTPUT):.0f} MB)")

    if arguments.no_installer:
        return 0

    if not _paths_fit():
        return 1

    installer = _build_installer()

    if installer is None:
        return 1

    print(f"Installer {installer} ({installer.stat().st_size / (1024 * 1024):.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
