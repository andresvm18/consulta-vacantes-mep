# Consulta Vacantes MEP

[![CI](https://github.com/andresvm18/consulta-vacantes-mep/actions/workflows/ci.yml/badge.svg)](https://github.com/andresvm18/consulta-vacantes-mep/actions/workflows/ci.yml)

Unofficial desktop tool that collects teaching vacancies and appointments
published by the Ministerio de Educación Pública (MEP) of Costa Rica, enriches
them, and exports the result to a formatted Excel workbook.

The application interface is in Spanish. Source code, documentation, and commit
messages are in English.

> **Status: alpha.** The project is being modernized in stages. Stages 1 to 9
> are complete: running the command opens a desktop window, the subcommands
> remain for scripted runs, both drive the same application layer, the workbook
> is written without pandas and leaves personal data out unless asked for, and
> every push runs the linter, the type checker, and 323 tests.
> What is left is packaging; see [CHANGELOG.md](CHANGELOG.md) for detail.

## What it does

- Scrapes open teaching vacancies from every MEP regional office
- Cross-references each vacancy against the public appointments registry
- Filters by specialty using accent-insensitive text matching
- Exports vacancies and appointments to a styled two-sheet Excel workbook

## Requirements

- Python 3.12 or newer
- Chromium (installed automatically through Playwright on first run)

On Linux, Qt links a few libraries a minimal installation may not carry:
`libegl1`, `libgl1` and `libxkbcommon0`. The test suite asks for Qt's offscreen
platform, so running the tests needs them but needs no display.

## Development setup

```bash
git clone https://github.com/andresvm18/consulta-vacantes-mep.git
cd consulta-vacantes-mep

python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -e ".[dev]"
playwright install chromium
```

The three checks CI runs, in the order it runs them:

```bash
ruff check .
mypy
pytest
```

The suite needs no network. Tests that would query the live MEP site carry the
`e2e` marker and are excluded by default; run them with `pytest -m e2e`.

## Usage

With no subcommand, the desktop window opens:

```bash
consulta-vacantes-mep
```

The window searches every specialty or one of them, lists the vacancies and the
appointments made against them in two tabs, rescrapes the vacancy list, and
exports. A search takes about half a minute and reports what it is doing while
it runs.

The subcommands are the scriptable half, and answer on standard output:

```bash
# Vacancies and the appointments recorded against them
consulta-vacantes-mep buscar --especialidad "Frances" --anio 2026

# Only what is published, without querying appointments
consulta-vacantes-mep vacantes --especialidad "Matematica"
```

`buscar` writes the workbook by default; pass `--sin-exportar` to skip it.
`vacantes` does the opposite and only writes one when asked with `--exportar`.
Specialty matching ignores accents and case.

The workbook leaves out the cédula and the name unless asked for:

```bash
consulta-vacantes-mep buscar --datos-personales
```

In the window, the same choice is a checkbox beside the export button.
`CVM_EXPORT_PERSONAL_DATA=1` sets the default for both.

Neither interface ever shows a cédula on screen, and the log files carry no
identification numbers at all.

Generated workbooks are written to `outputs/`. Runtime logs are written to
`logs/`. Both directories are excluded from version control.

## Roadmap

| Stage | Scope |
|-------|-------|
| 1 | `src/` layout migration |
| 2 | Centralized configuration, paths, and logging |
| 3 | Typed domain models and header-based table parsing |
| 4 | Explicit exception hierarchy and retry policy |
| 5 | Thread-per-browser concurrency and condition-based waits |
| 6 | Application layer with progress events, plus Typer CLI |
| 7 | Test suite and continuous integration |
| 8 | pandas-free export layer and personal-data redaction |
| 9 | PySide6 desktop interface, replacing the interactive menu |
| 10 | PyInstaller distribution with bundled Chromium |

## Privacy and legal

This is an independent project with no affiliation to the MEP or any government
body. It reads publicly accessible pages only.

The appointments registry publishes a cédula and a full name with every record.
Neither reaches an exported workbook unless asked for, and no identification
number reaches a log file. See [NOTICE](NOTICE) for the full data-handling
statement and third-party attributions.

## License

Apache License 2.0. See [LICENSE](LICENSE).