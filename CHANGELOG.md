# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Project README with roadmap and development setup instructions, and this
  changelog.
- `src/` layout with a real `consulta_vacantes_mep` package. The project is now
  installable, and the version is read from installed metadata so
  `pyproject.toml` remains the single source of truth.
- Centralized settings module collecting the constants that were scattered
  across modules, with environment variable overrides prefixed `CVM_`.
- Typed domain models (`Vacancy`, `Appointment`) with English field names, and a
  single definition of the Spanish labels shown to users.
- HTML fixtures captured from both MEP sites, with personal data redacted, so
  the parser can be tested without network access.
- Explicit exception hierarchy separating transient from permanent scraping
  failures, with exponential backoff via tenacity.
- Detection of the Cloudflare bot challenge the appointments site can serve.
- `AppointmentQuery` records why a query returned no rows, so a vacancy with no
  appointments is distinguishable from a query that failed. The run summary
  reports how many queries could not be completed.
- Test suite covering table parsing, settings, the retry policy, and error
  classification.

### Changed

- Unified project naming across `NOTICE`, `pyproject.toml`, and the PyInstaller
  spec. The canonical distribution name is `consulta-vacantes-mep`, the Python
  package is `consulta_vacantes_mep`, and the distributed executable is
  `Consulta Vacantes MEP`. The console script was renamed to match.
- Replaced hand-rolled file logging with the standard library logging module:
  rotating handlers, log levels, an error-only file, and stderr output for
  warnings. Configuration happens once from the entry point so the planned GUI
  can supply its own handlers.
- Lowered default concurrency from 10 to 4. This tool queries a public
  government site and should not behave like a load test.
- A regional office that fails permanently no longer aborts the run. If every
  office fails identically, the run aborts instead of exporting an empty
  workbook that would look like a legitimate result.
- Raised the minimum Python version to 3.12. mypy could not analyze the project
  at all under a 3.11 target because numpy's stubs use PEP 695 syntax.
- `NOTICE` data-handling section now describes current behavior rather than
  planned behavior. The redaction and export-exclusion guarantees will be
  restored once implemented.

### Fixed

- Runtime path resolution is centralized. Under the `src/` layout, walking up
  from `__file__` no longer reaches the project root, so non-frozen runs anchor
  output to the current working directory.
- The query year was hardcoded in three places and passed as a type object
  rather than a value at both call sites. It is now derived from the current
  date, prompted once, and required explicitly by the scrapers.
- Table extraction maps cells by the column attribute each cell declares instead
  of by position. Vacancy rows contain two hidden cells that positional slicing
  skipped only by coincidence.
- Rows missing a required column are logged with the column name instead of
  being discarded silently. This closes the silent loss of appointment rows
  containing an empty cell.
- Exported cell values are whitespace-normalized. The source pads several fields
  with trailing spaces and non-breaking spaces, which previously reached the
  workbook verbatim.
- Waiting for a row to exist after switching regional office matched the
  previous office's rows, which the grid keeps in the DOM while it re-renders.
  A settle delay is restored until stage 5 replaces it with a wait on the
  render itself.
- Retries no longer nest a Playwright context per attempt, and the browser is
  closed exactly once.

### Known issues

- Appointment lookups still launch one Chromium instance per vacancy number.
- Vacancy results are not cached between menu selections, so consecutive
  searches re-scrape every regional office.
- Postback completion is inferred from a fixed delay rather than the response
  itself, so an empty result and a query that never ran remain hard to tell
  apart at the source.
- The PyInstaller spec does not bundle Playwright browser binaries.

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
- Postback timeouts are swallowed, so a slow response is reported as "no
  appointments found" and is indistinguishable from a genuine empty result.
- Vacancy results are not cached between menu selections, so consecutive
  searches re-scrape all regional offices.
- One Chromium instance is launched per vacancy number, costing roughly 80
  seconds of startup overhead before the first result.
- The PyInstaller spec does not bundle Playwright browser binaries.