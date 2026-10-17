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
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "ConsultaVacantesMEP.spec"
OUTPUT = ROOT / "dist" / "ConsultaVacantesMEP"


def _run(*args: str, env: dict[str, str] | None = None) -> None:
    """Run a module of this interpreter, stopping the build if it fails."""
    command = [sys.executable, "-m", *args]
    print(f"\n> {' '.join(command[1:])}", flush=True)
    subprocess.run(command, check=True, cwd=ROOT, env=env)


def _size_in_megabytes(folder: Path) -> float:
    total = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
    return total / (1024 * 1024)


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

    print(f"\nBuilt {OUTPUT} ({_size_in_megabytes(OUTPUT):.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
