"""Resolution of the directories where the application writes at runtime.

Two cases, decided by whether this is the frozen Windows build.

Run from source, everything goes under the current working directory, logs/ and
outputs/, which is where a developer is looking.

Frozen, the executable is installed under the user's AppData, where nobody goes
looking. It used to write beside itself, which stopped making sense once there
was an installer. Exported workbooks are the user's own files, so they go to a
folder in Documents named after the application; the logs are not, so they stay
in AppData, under the same name.
"""

import os
import sys
from pathlib import Path

APP_NAME = "Consulta Vacantes MEP"

# The Known Folder ID of Documents. Documents can be moved, and OneDrive moves it
# by default when it backs the folder up, so the path is asked of Windows rather
# than assumed to be a subfolder of the home directory.
_FOLDERID_DOCUMENTS = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"


def is_frozen() -> bool:
    """Whether this is the PyInstaller build rather than a run from source."""
    return bool(getattr(sys, "frozen", False))


def _windows_documents() -> Path | None:
    """Ask Windows where the user's Documents folder is, or None if it cannot say."""
    if sys.platform != "win32":
        return None

    import ctypes  # noqa: PLC0415
    import uuid  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

    class _Guid(ctypes.Structure):
        _fields_ = (
            ("data1", wintypes.DWORD),
            ("data2", wintypes.WORD),
            ("data3", wintypes.WORD),
            ("data4", wintypes.BYTE * 8),
        )

    folder_id = _Guid.from_buffer_copy(uuid.UUID(_FOLDERID_DOCUMENTS).bytes_le)
    path = ctypes.c_wchar_p()

    result = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(folder_id), 0, None, ctypes.byref(path)
    )

    try:
        if result != 0 or not path.value:
            return None

        return Path(path.value)

    finally:
        # Windows allocates the string and the caller frees it, success or not.
        ctypes.windll.ole32.CoTaskMemFree(path)


def documents_dir() -> Path:
    """The user's Documents folder, wherever Windows keeps it."""
    return _windows_documents() or Path.home() / "Documents"


def local_app_data_dir() -> Path:
    """Where per-user application data goes on Windows."""
    configured = os.environ.get("LOCALAPPDATA")

    return Path(configured) if configured else Path.home() / "AppData" / "Local"


def get_log_dir() -> Path:
    if is_frozen():
        return local_app_data_dir() / APP_NAME / "logs"

    return Path.cwd() / "logs"


def get_output_dir() -> Path:
    if is_frozen():
        return documents_dir() / APP_NAME

    return Path.cwd() / "outputs"


LOG_DIR = get_log_dir()
OUTPUT_DIR = get_output_dir()
