# Consulta Vacantes MEP

Unofficial desktop tool that collects teaching vacancies and appointments
published by the Ministerio de Educación Pública (MEP) of Costa Rica, enriches
them, and exports the result to a formatted Excel workbook.

The application interface is in Spanish. Source code, documentation, and commit
messages are in English.

> **Status: alpha.** The project is being modernized in stages. Stages 1 to 6
> are complete: the package installs, the scrapers report progress instead of
> printing, and the interface is a Typer CLI over a shared application layer.
> See [CHANGELOG.md](CHANGELOG.md) for detail.

## What it does

- Scrapes open teaching vacancies from every MEP regional office
- Cross-references each vacancy against the public appointments registry
- Filters by specialty using accent-insensitive text matching
- Exports vacancies and appointments to a styled two-sheet Excel workbook

## Requirements

- Python 3.12 or newer
- Chromium (installed automatically through Playwright on first run)

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

## Usage

Without a subcommand, the interactive menu opens:

```bash
consulta-vacantes-mep
```

For scripted runs:

```bash
# Vacancies and the appointments recorded against them
consulta-vacantes-mep buscar --especialidad "Frances" --anio 2026

# Only what is published, without querying appointments
consulta-vacantes-mep vacantes --especialidad "Matematica"
```

`buscar` writes the workbook by default; pass `--sin-exportar` to skip it.
`vacantes` does the opposite and only writes one when asked with `--exportar`.
Specialty matching ignores accents and case.

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
| 9 | PySide6 desktop interface |
| 10 | PyInstaller distribution with bundled Chromium |

## Privacy and legal

This is an independent project with no affiliation to the MEP or any government
body. It reads publicly accessible pages only. The appointments registry
contains personal data; see [NOTICE](NOTICE) for the full data-handling
statement and third-party attributions.

## License

Apache License 2.0. See [LICENSE](LICENSE).