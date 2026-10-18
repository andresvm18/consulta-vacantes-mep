# Consulta Vacantes MEP

[![CI](https://github.com/andresvm18/consulta-vacantes-mep/actions/workflows/ci.yml/badge.svg)](https://github.com/andresvm18/consulta-vacantes-mep/actions/workflows/ci.yml)

Unofficial desktop tool that collects teaching vacancies and appointments
published by the Ministerio de Educación Pública (MEP) of Costa Rica, enriches
them, and exports the result to a formatted Excel workbook.

The application interface is in Spanish. Source code, documentation, and commit
messages are in English.

> **Status: alpha.** The ten stages of the modernization are complete. The
> application ships as a Windows installer with its own browser inside it, and
> every push runs the linter, the type checker, and the test suite on Python
> 3.12, 3.13 and 3.14. See [CHANGELOG.md](CHANGELOG.md) for detail.

## What it does

- Scrapes open teaching vacancies from every MEP regional office
- Cross-references each vacancy against the public appointments registry
- Filters by specialty using accent-insensitive text matching
- Exports vacancies and appointments to a styled two-sheet Excel workbook

## Installing

For Windows 10 and 11, 64-bit.

1. Download `Instalar-Consulta-Vacantes-MEP-<version>.exe` from the
   [Releases](https://github.com/andresvm18/consulta-vacantes-mep/releases) page.
2. Run it. It installs for the current user only and does not ask for
   administrator rights. A desktop shortcut is offered as an option.
3. Open **Consulta Vacantes MEP** from the Start menu.

The installer is not code-signed, so Windows may show a SmartScreen warning
the first time. Choose "More info" ("Más información"), then "Run anyway"
("Ejecutar de todas formas").

Nothing else needs installing: the browser the application drives is inside it.

| What | Where |
|------|-------|
| Exported workbooks | `Documents\Consulta Vacantes MEP` |
| Log files | `%LOCALAPPDATA%\Consulta Vacantes MEP\logs` |
| The application | `%LOCALAPPDATA%\Programs\Consulta Vacantes MEP` |

To remove it, use Settings → Apps → Installed apps. Uninstalling leaves the
exported workbooks and the logs where they are.

## Using it

The window searches every specialty or one of them, lists the vacancies and the
appointments made against them in two tabs, rescrapes the vacancy list, and
exports. A search takes about half a minute and reports what it is doing while
it runs.

After an export, the window offers to open the workbook or show it in its
folder. The "Abrir carpeta de exportados" button opens that folder at any time.

The workbook leaves out the cédula and the name unless the "Incluir cédula y
nombre" box is checked. Neither interface ever shows a cédula on screen, and
the log files carry no identification numbers at all.

### From a terminal

The installer also puts `consulta-vacantes-mep.exe` in the application folder,
for scripted runs. It is not added to the `PATH`:

```powershell
& "$env:LOCALAPPDATA\Programs\Consulta Vacantes MEP\consulta-vacantes-mep.exe" vacantes
```

The subcommands answer on standard output:

```bash
# Vacancies and the appointments recorded against them
consulta-vacantes-mep buscar --especialidad "Frances" --anio 2026

# Only what is published, without querying appointments
consulta-vacantes-mep vacantes --especialidad "Matematica"
```

`buscar` writes the workbook by default; pass `--sin-exportar` to skip it.
`vacantes` does the opposite and only writes one when asked with `--exportar`.
Specialty matching ignores accents and case. `--datos-personales` includes the
cédula and the name, and `CVM_EXPORT_PERSONAL_DATA=1` sets that default for
both interfaces.

## Development

### Requirements

- Python 3.12 or newer
- Chromium, installed automatically through Playwright on first run

On Linux, Qt links a few libraries a minimal installation may not carry:
`libegl1`, `libgl1` and `libxkbcommon0`. The test suite asks for Qt's offscreen
platform, so running the tests needs them but needs no display.

### Setup

```bash
git clone https://github.com/andresvm18/consulta-vacantes-mep.git
cd consulta-vacantes-mep

python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -e ".[dev]"
playwright install chromium
```

Run from source, the command opens the window, and the subcommands work as
above:

```bash
consulta-vacantes-mep
consulta-vacantes-mep buscar --sin-exportar
```

Workbooks go to `outputs/` and logs to `logs/` under the working directory. Both
are excluded from version control.

### Checks

The three checks CI runs, in the order it runs them:

```bash
ruff check .
mypy
pytest
```

The suite needs no network. Tests that would query the live MEP site carry the
`e2e` marker and are excluded by default; run them with `pytest -m e2e`.

### Building the installer

On Windows, with [Inno Setup](https://jrsoftware.org/isinfo.php) 6.3 or newer
installed:

```powershell
winget install --id JRSoftware.InnoSetup -e   # once
pip install -e ".[build]"
python scripts/build.py
```

The script downloads the headless Chromium into the Playwright package, runs
PyInstaller, copies every bundled component's license into the result, and
packs it with Inno Setup. It produces:

- `dist\ConsultaVacantesMEP\`, the application folder, with the window
  executable, the terminal one, and the licenses.
- `dist\Instalar-Consulta-Vacantes-MEP-<version>.exe`, the installer, which is
  what gets distributed.

`--no-installer` stops at the folder.

Keep the repository at a short path, such as `C:\Projects\consulta-vacantes-mep`.
Chromium's files sit deep inside the package, and Inno Setup cannot read a path
of 260 characters or more. The script checks this before packing and says so,
but a checkout under a long OneDrive path will not build.

## Roadmap

| Stage | Scope | Status |
|-------|-------|--------|
| 1 | `src/` layout migration | Done |
| 2 | Centralized configuration, paths, and logging | Done |
| 3 | Typed domain models and header-based table parsing | Done |
| 4 | Explicit exception hierarchy and retry policy | Done |
| 5 | Thread-per-browser concurrency and condition-based waits | Done |
| 6 | Application layer with progress events, plus Typer CLI | Done |
| 7 | Test suite and continuous integration | Done |
| 8 | pandas-free export layer and personal-data redaction | Done |
| 9 | PySide6 desktop interface, replacing the interactive menu | Done |
| 10 | Windows installer with bundled Chromium | Done |

## Privacy and legal

This is an independent project with no affiliation to the MEP or any government
body. It reads publicly accessible pages only.

The appointments registry publishes a cédula and a full name with every record.
Neither reaches an exported workbook unless asked for, and no identification
number reaches a log file. See [NOTICE](NOTICE) for the full data-handling
statement and third-party attributions.

The installed application carries the license of every component it bundles,
in the `licenses` folder beside it, including the LGPL v3 for Qt and where to
obtain Qt's source.

## License

Apache License 2.0. See [LICENSE](LICENSE).
