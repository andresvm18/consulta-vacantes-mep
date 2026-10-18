# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-10-18

The first release meant to be installed rather than run from source.

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
- Vacancy results are cached for the duration of a session, so a second search
  reuses them instead of scraping every regional office again.
- Tests for the bookkeeping that guarantees one result per vacancy number
  whatever the worker threads did.
- Progress events emitted by the scrapers, so a run can be drawn by a terminal,
  a GUI, or nothing at all. The scrapers no longer decide how they look.
- An application layer owning the search sequence and the vacancy cache. The
  two ways of searching ran the same steps and differed only in whether a
  specialty narrowed the vacancies down. It now has two consumers, which is
  what it was built for.
- Subcommands `buscar` and `vacantes` for scripted runs.
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
- A desktop window, built on PySide6 and the second consumer of the application
  layer. It searches every specialty or one of them, lists vacancies and
  appointments in two tabs, rescrapes the vacancy list, and exports, driving the
  same `Session` the subcommands drive.
- Progress during a run reaches the window as Qt signals. The scrapers already
  emitted events for whoever was listening; a reporter forwards each one, and Qt
  queues it onto the thread that owns the widgets.
- Searches run on a thread of their own, so a run that takes half a minute no
  longer stops the interface repainting.
- A startup sequence shared by both interfaces: check for a browser, say a
  download is about to start, install, report what happened. The wording is each
  interface's own, as a printed line or as a dialog.
- Test coverage for everything stage 9 added, and for the entry point's choice
  between the two interfaces, which had none at all. The suite went from 187
  tests to 323.
- A Windows installer, built with Inno Setup. It installs for the current user
  under AppData, so it asks for no administrator rights, and adds a Start menu
  entry, an optional desktop shortcut and an uninstaller. An update clears the
  previous runtime before copying the new one, so no file a newer build stopped
  shipping is left behind. It measures 125 MB.
- The headless Chromium ships inside the build. `scripts/build.py` installs it
  into the Playwright package and then runs PyInstaller, and the spec refuses to
  build without it. A frozen build points Playwright there on its own, so no
  runtime hook is needed, and a machine with no browser installed runs a search.
- Two executables over one runtime: `Consulta Vacantes MEP.exe`, the window,
  with no console at all, and `consulta-vacantes-mep.exe` for the subcommands.
  A console-less executable has no standard output, and a terminal does not
  wait for one, so the subcommands needed their own.
- An application icon, a silhouette of Costa Rica drawn from Natural Earth's
  public domain boundaries, in seven sizes from 16 to 256 pixels. It is set on
  the application before any dialog, since Qt does not read the executable's.
- After an export, the window offers to open the workbook or show it selected
  in Explorer, and a button that is never disabled opens the export folder,
  creating it if nothing has been exported yet.
- The build carries the license of everything it bundles: the LGPL v3 and GPL
  v3 texts and where to get the source of the exact Qt version shipped, and
  each dependency's own license files, copied from the installed distributions
  along with Chromium's and Python's. A dependency with no license file to copy
  fails the build.
- Test coverage for everything stage 10 added or fixed. The suite went from 323
  tests to 388, a few of which run only on Windows or only elsewhere.

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
- `utils/console.py` was removed. Nothing under `src/` prints any more, so the
  linter exemptions for `print` are gone rather than relocated.
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
- Running the command with no subcommand opens the window rather than a menu.
  The subcommands are unchanged and remain the scriptable half.
- The CLI entry module is `cli/entry.py`. As `cli/main.py` it was shadowed by
  the function the package reexports under that name, so importing the module
  handed back the function and reaching it needed `importlib`. A smoke test
  pins the two apart, since the broken form still imports something callable.
- `prepare_browser` no longer holds both the sequence and the Spanish it says
  about it. The sequence moved to the application layer, which is what lets the
  window reuse it with a dialog instead of a printed line.
- The rule for naming an exported workbook moved into the export layer. Both
  interfaces want the same answer, and a user who exports from the window one
  day and from a command the next should not find two naming schemes in one
  folder.
- `ItemCompleted.index` has a documented meaning. Both emitters agreed that it
  counts what has finished, which is what a progress bar wants, but nothing said
  so and the only consumer ignored it.
- CI installs the three libraries Qt links that a bare runner lacks. They were
  measured rather than remembered, and the test suite asks for Qt's offscreen
  platform itself so a developer's machine and CI behave the same.
- Installed, the application writes workbooks to `Documents\Consulta Vacantes
  MEP` and logs to `%LOCALAPPDATA%\Consulta Vacantes MEP\logs`, instead of
  beside the executable, which the installer puts in a folder nobody opens.
  Documents is asked of Windows, so a folder moved by OneDrive is found. Runs
  from source still write under the working directory.
- The subcommands' failure messages name the real path of the error log on a
  line of their own, instead of a fixed `logs/errors.log` that is wrong once
  installed.
- The build leaves out what the application never uses: NumPy, which openpyxl
  imports if it can; Qt's software OpenGL renderer and translations; and
  Playwright's ffmpeg and Chromium's interface languages other than English and
  Spanish. The application folder went from 509 MB to 420.
- PyInstaller moved to a `build` extra, apart from the development tools.
- Python 3.14 joins the CI matrix and the classifiers, since it is what
  development runs on.
- The README starts with installing and using the release, and documents how to
  build the installer.

### Removed

- The interactive console menu, and `cli/menu.py` with it. Everything it
  offered the window offers better, and it was the one part of the interface
  nothing tested.

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
- A run that could not read the vacancies page is reported as a failure instead
  of as no vacancies. The first wait after navigation shared the grid's three
  second timeout and had no retry, so a slow first load ended the run; the error
  was then logged and swallowed, and the terminal said nothing had been found.
  The first load now has its own timeout and is retried as a whole. The
  subcommands say in Spanish that the site could not be read, exit with code 1,
  and write no workbook; the window, which already handled a failed run, is now
  told about one.
- Network failures are classified as transient. A machine without a connection
  fails with `net::ERR_NAME_NOT_RESOLVED`, which contains "resolve", so the
  selector heuristic read it as the site having changed: the failure was not
  retried, and the log sent whoever read it to the selectors for a machine that
  was offline. Chromium's `net::ERR_` prefix is now checked first.
- Tracebacks no longer reach the terminal. A failed run printed forty lines of
  one ahead of the Spanish sentence explaining it. The screen shows the log
  message alone, and both log files keep the full traceback.
- A workbook that could not be written is explained in the subcommands as it
  already was in the window. Excel locks a file it has open, and a second export
  within the same minute writes to the same name; the `PermissionError` escaped
  as a traceback after the results had been shown. The subcommands now say to
  close the file and try again, and exit with code 1.
- The retry warning states the delay before the next attempt. It logged the
  total slept so far, so the second retry of a run said three seconds before
  sleeping two.
- `NOTICE` lists every component the build bundles, with copyrights taken from
  each one's own license file. colorama, which Typer needs on Windows, and the
  copy of Click that Typer vendors were missing, and Node.js and the headless
  Chromium are now named under Playwright.

### Known issues

- Names are not removed from log output. No pattern can tell one from an
  institution or a regional office name, so the only defence is not logging a
  row that carries one. Nothing does today.
- A run cannot be cancelled once it has started. The scrapers have no point at
  which they ask whether they should stop, so a cancel would mean abandoning a
  thread with a browser open in it.
- The first regional office of a run sometimes fails its first attempt, costing
  about three seconds. Blazor prerenders the markup, so no condition on the DOM
  distinguishes a live app from a rendered one. Recorded as always happening
  until a run on the first of October did not reproduce it.
- The installer is not code-signed, so Windows may show a SmartScreen warning
  for a copy downloaded from the internet.
- The installer is built on a developer's machine; CI checks the code but does
  not build it. Inno Setup cannot read a path of 260 characters or more, and
  Chromium's files sit deep enough that the checkout has to be at a short path.
  The build checks this before packing.
- Whether a cédula ever reaches a log file has been tested against redacted
  fixtures, not against the live registry: no appointment was recorded against
  the vacancies published while this release was being tested.

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
