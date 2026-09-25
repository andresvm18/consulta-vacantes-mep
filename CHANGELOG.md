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
- Vacancy results are cached for the duration of a session, so consecutive menu
  selections reuse them instead of scraping every regional office again.
- Tests for the bookkeeping that guarantees one result per vacancy number
  whatever the worker threads did.
- Progress events emitted by the scrapers, so a run can be drawn by a terminal,
  a GUI, or nothing at all. The scrapers no longer decide how they look.
- An application layer owning the search sequence and the vacancy cache. The
  two menu options ran the same steps and differed only in whether a specialty
  narrowed the vacancies down.
- Subcommands `buscar` and `vacantes`. Running with no subcommand still opens
  the interactive menu.
- Menu option to refresh the cached vacancy list within a session.
- Continuous integration: ruff, mypy, and the test suite run on every push and
  pull request, on the lowest supported Python version and on 3.13.
- Test coverage for the layers stage 6 introduced and left unverified: the
  session cache, the Rich reporter, the Chromium check and installer, and the
  Typer subcommands. The suite went from 26 tests to 110 and still needs no
  network, since the browser-facing pieces run against captured HTML or
  doubles.
- Tests describing the exported workbook rather than the code that writes it,
  so removing pandas in stage 8 is verifiable instead of a leap of faith.
- Detection of client-side pagination in the vacancies grid. MudBlazor keeps
  later pages out of the DOM entirely, so an office spanning more than one page
  would have been read as a subset with nothing to indicate it. Every office
  observed so far fits on one page; a run that finds otherwise now says so.

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
- Scraping waits on conditions rather than fixed delays throughout. A full run
  dropped from roughly 143 seconds to under 25. Normalized, because the site
  publishes a different number of vacancies from one hour to the next: about
  1.6 seconds per regional office down to 0.3, and about 1.7 seconds per
  vacancy number down to 0.3.
- Appointment lookups run on four worker threads pulling from a shared queue,
  each owning one browser for the whole run. Playwright's sync API binds a
  browser to the thread that started it, so a shared one is not an option;
  four launches per run replaces one per vacancy number.
- The console interface is drawn with Rich: one progress bar per phase instead
  of a line per result, which four concurrent workers made unreadable. Log
  warnings share the same console, since a second writer tears a live display.
- The Chromium check returns a status the caller renders instead of printing
  its own messages, and the installer runs without opening a console window
  and with its output captured into the log. A windowed build has no standard
  output: a print would raise before the interface appeared.
- The menu moved into the `cli` package and `utils/console.py` was removed.
  Nothing under `src/` prints any more, so the linter exemptions for `print`
  are gone rather than relocated.
- Tables are read in a single browser evaluation instead of one round trip per
  cell. Measured against the captured fixture, 250 milliseconds per table down
  to 7.5, and the gap widens with the number of rows. Speed is the smaller
  half: every one of those reads hit a DOM Blazor can re-render between any two
  of them, so a row could be counted under one office and read under the next.
- Type annotations are required across the codebase. The list of exempt modules
  that mirrored the linter's is now empty: the export layer was the last entry,
  and removing it exposed two annotations pandas had been hiding behind it.
- Regional office dropdown entries carry a `TypedDict` instead of a bare
  `dict`. The name and the value the select expects were interchangeable
  strings; confusing them selects nothing while the grid keeps showing the
  previous office's rows.
- The workbook is written with openpyxl directly. pandas built two frames and
  handed them to a writer that used openpyxl underneath, and every sheet was
  reopened afterwards to be formatted by hand, so its only job here was turning
  a list of dicts into rows. It and NumPy measure about a hundred megabytes
  installed, which the frozen build has to carry. Both writers were run over
  the same records and compared cell by cell: values, cell types, dimensions,
  column widths, frozen panes, autofilter range and header styling all match.
- Search results are shown as a table of six columns rather than all thirteen
  fields of every appointment, one per line. Fifty appointments made seven
  hundred lines of terminal, and the cédula was among them. The name stays,
  since whether a post was filled and by whom is the question being asked.
- `DTZ005` is gone from the linter ratchet, which now has four entries. The
  rule was silenced in stage 1 and the code it pointed at was fixed in stage 3,
  but the line stayed, so the check was off for three stages with nothing left
  to report.

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
  The scraper waits for the row content to actually change.
- Postback completion is observed instead of guessed: the scraper waits for the
  POST response and then for the UpdatePanel to finish applying it. The response
  status is what separates an empty result from a query that never ran, since
  the page renders nothing in either case and shows no message to read.
- A worker thread that fails unexpectedly no longer ends the run. Only the
  vacancy number it had taken is reported as failed; the rest stay queued for
  the other workers.
- Retries no longer nest a Playwright context per attempt, and the browser is
  closed exactly once.
- A regional office that could not be read is reported as a failure instead of
  as zero vacancies, and counted separately in the run summary.
- The stderr log handler is only attached when there is a stderr to write to.
- The export prompt no longer appears when the search found nothing.
- The appointments sheet names its columns even when a search finds vacancies
  nobody has been appointed to. A frame built from rows alone carries no
  columns, so there was no heading row to write and the result read as a
  damaged file rather than an empty table.
- `NOTICE` lists Typer, Rich and tenacity among the components a distribution
  bundles. They had been under planned dependencies since stage 6, alongside
  pydantic-settings and httpx, which were never adopted and are now removed.

### Known issues

- Names are not removed from log output. No pattern can tell one from an
  institution or a regional office name, so the only defence is not logging a
  row that carries one. Nothing does today.
- `NOTICE` does not list the transitive dependencies a frozen build bundles
  through Typer and Rich: Click, Pygments, markdown-it-py, mdurl, shellingham,
  annotated-doc, and typing_extensions through pyee.
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
- Personal data is left out of exported workbooks unless asked for. The
  appointments sheet carries neither the cédula nor the name by default, since
  a workbook is a file that gets forwarded and the other eleven columns already
  answer whether a post was filled. `--datos-personales` asks for them, and
  `CVM_EXPORT_PERSONAL_DATA` sets the default for every interface, so the
  planned GUI inherits the policy rather than reimplementing it.
- National identification numbers are removed from everything written to the
  log files and the terminal, tracebacks included. A log file outlives the run
  that produced it, and the registry attaches a cédula to every record.
- Test coverage for the three modules that decide what may leave the program:
  the labels, the redaction pattern, and the logging configuration that applies
  it. The suite went from 110 tests to 187.

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
- The first regional office of a run always fails its first attempt. Blazor
  prerenders the markup, so no condition on the DOM can tell a live app from a
  rendered one, and a selection made before the app connects goes unanswered.
  The retry covers it at a cost of about four seconds per run.