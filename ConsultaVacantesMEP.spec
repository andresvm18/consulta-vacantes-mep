# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows build.

Build through scripts/build.py rather than calling PyInstaller directly. The
script first downloads the headless Chromium into the Playwright package, which
is the only place this spec looks for it.
"""
from pathlib import Path

import playwright
from PyInstaller.utils.hooks import collect_all

# Where `playwright install` puts browsers when PLAYWRIGHT_BROWSERS_PATH is 0:
# inside the package, so collect_all picks them up as package data. A frozen
# build sets that variable for itself (playwright/_impl/_transport.py), so at
# run time the driver looks in the same place without any help from here.
LOCAL_BROWSERS = Path(playwright.__file__).parent / 'driver' / 'package' / '.local-browsers'

shells = (
    sorted(LOCAL_BROWSERS.glob('chromium_headless_shell-*')) if LOCAL_BROWSERS.is_dir() else []
)

if not shells:
    raise SystemExit(
        f'No headless Chromium in {LOCAL_BROWSERS}. '
        'Build with: python scripts/build.py'
    )

# Modules that reach the analysis only because they happen to be installed.
# openpyxl imports NumPy if it can, to recognise its number types, and works the
# same without it; pandas left with stage 8 but can linger in an old virtual
# environment. Together they measured 26 MB of a 509 MB build.
EXCLUDED_MODULES = ['numpy', 'pandas']

# Chromium's interface languages. The browser is never shown, so only the
# fallback and the language of the site it reads are kept.
KEPT_LOCALES = {'en-US.pak', 'es.pak', 'es-419.pak'}


def _unwanted(destination: str) -> bool:
    """Whether a collected file is something the application never uses.

    Each rule names what it removes and why it is safe to, so a build that
    breaks after a Playwright or Qt upgrade has a short list to look at.
    """
    path = destination.replace('\\', '/')

    # The full Chromium. Headless runs use the shell; nothing starts this one.
    if '/.local-browsers/chromium-' in path:
        return True

    # Playwright's ffmpeg, which only records video of a session.
    if '/.local-browsers/ffmpeg-' in path:
        return True

    # Interface languages of a browser nobody looks at.
    if '/.local-browsers/chromium_headless_shell-' in path and '/locales/' in path:
        return path.rsplit('/', 1)[-1] not in KEPT_LOCALES

    # Qt's software OpenGL renderer, 20 MB. Widgets paint without OpenGL.
    if path == 'PySide6/opengl32sw.dll':
        return True

    # Qt's own translations. Nothing installs a QTranslator, so none is loaded.
    return path.startswith('PySide6/translations/')


datas = [('src/consulta_vacantes_mep/assets/icon.ico', 'consulta_vacantes_mep/assets')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('playwright')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['src/consulta_vacantes_mep/__main__.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_MODULES,
    noarchive=False,
    optimize=0,
)

# Filtered after the analysis rather than before it, so files added by
# PyInstaller's own hooks for PySide6 and Playwright go through the same rules.
a.datas = [entry for entry in a.datas if not _unwanted(entry[0])]
a.binaries = [entry for entry in a.binaries if not _unwanted(entry[0])]

pyz = PYZ(a.pure)

# Two executables over one analysis, sharing _internal. The window is built
# without a console, so double clicking it shows nothing but the window: a
# console-less executable has no standard output either, and a terminal does
# not even wait for one to finish. The subcommands therefore get their own,
# with a console, under the same name the pip install gives them.
window = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Consulta Vacantes MEP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['src/consulta_vacantes_mep/assets/icon.ico'],
)
terminal = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='consulta-vacantes-mep',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['src/consulta_vacantes_mep/assets/icon.ico'],
)
coll = COLLECT(
    window,
    terminal,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ConsultaVacantesMEP',
)
