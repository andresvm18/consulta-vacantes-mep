"""Resolution of the directories where the application writes at runtime."""

import sys
from pathlib import Path


def get_app_root() -> Path:
    """Return the directory that runtime output is written under.

    When frozen by PyInstaller, the executable's own directory is used so that a
    portable install keeps its logs and exports beside itself.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path.cwd()


APP_ROOT = get_app_root()

LOG_DIR = APP_ROOT / "logs"
OUTPUT_DIR = APP_ROOT / "outputs"