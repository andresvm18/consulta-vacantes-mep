# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project README with roadmap and development setup instructions.
- This changelog.

### Changed
- Unified project naming across `NOTICE`, `pyproject.toml`, and the PyInstaller
  spec. The canonical distribution name is `consulta-vacantes-mep`, the Python
  package is `consulta_vacantes_mep`, and the distributed executable is
  `Consulta Vacantes MEP`.
- Console script renamed from `mep-vacantes` to `consulta-vacantes-mep` so the
  command matches the package.
- `NOTICE` data-handling section now describes current behavior rather than
  planned behavior. The redaction and export-exclusion guarantees will be
  restored once implemented.

## [0.3.0] - 2026-08-03

Baseline snapshot of the pre-modernization codebase, tagged as `v0.3.0-legacy`.

### Added
- Vacancy scraper covering all MEP regional offices.
- Appointment scraper with threaded lookup per vacancy number.
- Accent-insensitive specialty filtering.
- Excel export with styled headers, frozen panes, and auto-fit columns.
- Interactive console menu.
- PyInstaller spec for Windows distribution.

### Known issues
- The package layout declared in `pyproject.toml` does not exist; the project is
  not installable.
- Appointment rows containing an empty cell are silently discarded.
- One Chromium instance is launched per vacancy number.
- The PyInstaller spec does not bundle Playwright browser binaries.