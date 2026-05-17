import sys
from pathlib import Path
from datetime import datetime


def get_app_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = get_app_root()

LOG_DIR = PROJECT_ROOT / "logs"

LOG_FILE = LOG_DIR / "scraper.log"
ERROR_FILE = LOG_DIR / "errors.log"


def write_log(message):
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def write_error(message):
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(ERROR_FILE, "a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] ERROR: {message}\n")