# Implementation Plan: Bookmark Import and HTML Export

**Branch**: `002-import-html-export` | **Date**: 2026-11-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-import-html-export/spec.md`

## Summary

Add a sixth subcommand, `python -m bookmarks [--db PATH] import FILE --format csv|json`, and a
third export format, `export --format html`, to the shipped bookmark manager — without moving
a single byte of the five existing commands' behaviour (FR-028, FR-029).

`import` is **two-phase**: it reads and validates the whole file into a list of
`(url, title, tags)` records, running `add`'s own validators on each one, and only then opens
the collection and writes every record inside a single SQLite transaction. That ordering is
what makes the specification's hardest requirement — all-or-nothing import with the collection
"byte-identical to its prior state" on any fault (FR-039, SR-015) — fall out of the design
rather than needing recovery machinery: an input fault is diagnosed before `storage.connect` is
ever called, so no write is attempted and a non-existent database file is not even created.
Limits are enforced before reading (32 MiB via `os.path.getsize`) and while parsing (50,000
records, plus the inherited SR-006 per-field limits).

`export --format html` streams a fixed eight-line skeleton with one `<li>` line per bookmark,
escaped per context — `&`, `<`, `>` in element text and those plus `"` in the `href` value —
reusing the existing `join_tags()` so the HTML `TAGS` field is identical to the CSV one by
construction.

Two constraints discovered by reading the repository, not the spec, shape the whole design:
feature 001's `test_security_stdlib_only.py` pins the shipped package to **exactly five
modules** and to a **fixed import whitelist** that excludes `html`. Since SC-011 requires every
feature-001 test to pass unchanged, this feature adds **no new module** (import logic goes into
`cli.py`, HTML rendering into `output.py`, one write helper into `storage.py`) and **no new
import** beyond `csv` and `json` in `cli.py`, which the whitelist already permits. HTML
escaping is therefore four explicit `str.replace` calls rather than `html.escape`. Both choices
are recorded with their rejected alternatives in [research.md](./research.md) R1 and R2 and in
Complexity Tracking below.

Tests are `pytest`, added alongside the existing suite with no edit to any 001 test file:
17 functional and 8 security requirements, each mapped to at least one named test in
[contracts/requirements-test-matrix.md](./contracts/requirements-test-matrix.md).

## Technical Context

**Language/Version**: Python 3.11+ (verified available here: 3.13.17). No syntax or API newer
than 3.11 is used. Unchanged from feature 001.

**Primary Dependencies**: None at runtime — standard library only. This feature adds **no new
import to the package**: `cli.py` gains `csv` and `json`, both already used by `output.py` and
both already inside the whitelist asserted by
`test_security_stdlib_only.py::test_whole_package_imports_only_these_standard_modules`
(`__future__`, `argparse`, `contextlib`, `csv`, `dataclasses`, `json`, `os`, `sqlite3`, `sys`,
`typing`). `pytest` 9.1.1 for tests only. Tests may use any standard-library module, and
`html.parser` is used there for the SC-014 round-trip.

**Storage**: Unchanged. The same single SQLite file, the same two tables
(`bookmarks`, `bookmark_tags`), no new column, no new index, **no migration** (FR-029). `import`
introduces no new SQL statement — it loops over the existing `INSERT_BOOKMARK_SQL` and
`INSERT_TAG_SQL` inside one transaction.

**Testing**: `pytest`, driven through `bookmarks.cli.main(argv)` in process via the existing
`run` fixture, with `tmp_path` for both database files and import files. No subprocess, no
network, no third-party plugin. Two additive fixtures in `tests/conftest.py`
(`write_file`, `database_fingerprint`); no existing fixture is renamed or changed.

**Target Platform**: POSIX (Linux/macOS) for the full suite. The inherited `0600` file-mode
assertion stays POSIX-only; the SR-017 modification-time assertion uses `st_mtime_ns`, which is
portable.

**Project Type**: Single-project CLI tool, package `bookmarks` under `src/`, runnable as
`python -m bookmarks` with `src/` on `PYTHONPATH`. **The shipped file list does not change.**

**Performance Goals**: HTML export of 10,000 bookmarks under one second; import of 10,000
records under ten seconds (SC-013). HTML export peak memory independent of collection size;
import peak memory independent of collection size and bounded by the SR-014 input limits
(SR-019).

**Constraints**: Standard library only, and additionally no import outside the existing
whitelist and no sixth shipped module (SC-011). No network, no subprocess, no shell, no
environment-driven configuration (SR-010, SR-016). `FILE` is opened read-only and nothing on
the filesystem is written except the database and its own transient files (SR-017). One import
commits as one unit or not at all (SR-015). Exit statuses stay exactly 0/1/2/3, with every
import input fault being 2 and every collection fault 1. Every expected failure is one line on
stderr with no traceback, no SQL text and no internal path (SR-018) — which, because the
inherited disclosure test forbids the substring `line `, is why positions are reported as
`row N` / `record N`.

**Scale/Scope**: One new subcommand, one new export format, zero new tables, zero new modules.
Roughly 120 lines of shipped code across three existing files. Tested to 50,000 bookmarks and a
50,000-record import. 17 functional requirements (FR-028…FR-044) and 8 security requirements
(SR-012…SR-019) to cover, on top of feature 001's 38, which keep their existing tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0. The Plan gate requires this plan to name, for each principle, the specific
commitment. It does.

### I. Standard Library Only — PASS

No runtime dependency is added, and in fact no *import* is added to the package: `cli.py` gains
`csv` and `json`, which are already in the package's import set. The capabilities this feature
needs are all in the standard library — `csv` for RFC 4180 reading, `json` for parsing, `os.path`
for the file gate, and plain `str.replace` for HTML escaping. Mechanically checked by the
inherited SC-015/SR-010 AST test, which is *not* edited and which asserts both the five-module
file list and the whitelist subset. `pytest` remains test-only; no test exercises a runtime path
through a third-party package.

### II. Fail Loudly — PASS

Every invalid input case has a named message, destination and exit status. The complete mapping
is the failure contract in
[contracts/cli-contract.md](./contracts/cli-contract.md#failure-contract), summarised:

| Case | Stream | Status |
|---|---|---|
| Missing `FILE`, missing `--format`, `--format` not `csv`/`json` (import) or not `csv`/`json`/`html` (export) | stderr | 2 |
| `FILE` not a readable regular file; unreadable; over 32 MiB; not valid UTF-8 | stderr | 2 |
| `FILE` not valid CSV of the required shape (header, field count, blank row) | stderr | 2 |
| `FILE` not valid JSON of the required shape (not an array, element not an object, missing or mistyped `url`/`title`/`tags`, nested too deeply) | stderr | 2 |
| More than 50,000 records; a record `add` would reject | stderr | 2 |
| Collection unusable or corrupt | stderr | **1** |
| Success, including `imported 0` and an empty HTML page | stdout only | 0 |

No `except` block in the design swallows an error, substitutes a default, or truncates data.
Specifically, and against each temptation the specification names:

- **No silent skip.** A single bad record fails the whole import (spec Assumption 1). There is
  no "imported 99, skipped 1" path, because the constitution forbids reporting partial success
  as success and `imported N` must stay trustworthy.
- **No defaulting.** A JSON element missing `title` is rejected, not defaulted to `""`; missing
  `tags` is rejected, not defaulted to `[]`.
- **No coercion.** `"tags": "a,b"` (a string, not an array) is rejected rather than parsed.
  `"url": 42` is rejected rather than stringified.
- **No encoding fallback.** Invalid UTF-8 is rejected rather than decoded with replacement
  characters; a byte-order mark is rejected rather than stripped.
- **No format guessing.** The format comes from `--format` alone; the extension and content are
  never consulted (FR-031).
- **An empty input file is a success, not an error** — `imported 0` (FR-038). That is specified
  behaviour, not a silent wrong answer, and it is distinguishable from a failure by its status.
- **`RecursionError` on deep JSON is caught and reported as a one-line failure**, not allowed to
  surface as a traceback and not suppressed into an empty import.

### III. Every Requirement Is Testable — PASS

Every FR and SR maps to at least one named `pytest` test. The full matrix is
[contracts/requirements-test-matrix.md](./contracts/requirements-test-matrix.md): **25
requirements, 25 mapped, 0 unmapped, 0 planned skips.** Acceptance scenarios from User Stories
1–3 map to one integration module per story. Every success criterion SC-008…SC-015 also has a
named test, including SC-011 itself — `test_feature_001_test_files_are_unmodified` digests the
001 test modules so that an accidental edit fails the suite rather than passing quietly.

### IV. Simplicity — PASS

Smallest design that satisfies the spec: **zero new modules, zero new tables, zero new SQL
statements, zero new classes, zero new configuration.** The additions are one argparse
subparser, one command function, two parsing functions, one storage helper, one renderer and
two escape helpers. `add` and `import` share the row+tags insert through one private
`_insert_bookmark()` so the write exists once. `import` reuses `validate_url`, `parse_tags`,
`_check_length` and the SR-006 constants verbatim rather than restating FR-008 and FR-012 —
which is also what makes FR-035's "indistinguishable from `add`" true by construction.
`export --format html` reuses `join_tags()`, so FR-042's "identical to the `tags` field of
`export --format csv`" needs no separate sort.

Deliberately rejected in [research.md](./research.md): a sixth `importer.py` module (R1),
`csv.DictReader` and `csv.Sniffer` (R7), a hand-written incremental JSON parser (R8),
`executemany` and `SAVEPOINT` nesting (R4), `sys.setrecursionlimit` (R8), building the page with
`ElementTree` (R2), a dataclass for an import record (data-model.md), a provenance column
(data-model.md), and any dry-run, progress or per-record reporting option (spec Assumptions).

Three entries appear in Complexity Tracking below. Two are *reductions* in generality forced by
SC-011, and one is a bounded-memory consequence of the standard library's JSON API; none is an
added component.

### V. Secure By Default (NON-NEGOTIABLE) — PASS

The spec states 8 security requirements (SR-012…SR-019) derived from OWASP Top 10 A03/A04/A05
and ASVS V5/V7/V12, on top of feature 001's SR-001…SR-011, which continue to apply to the new
command and format. Each maps to a baseline control and at least one negative test:

| Baseline control | Feature requirement | Design commitment | Negative test |
|---|---|---|---|
| Untrusted input, allow-list | SR-013 | CSV: header must **equal** `output.CSV_HEADER`, every row exactly 4 fields. JSON: top level must be a `list`, every element a `dict`, `url`/`title` present and `str`, `tags` present and a `list` of `str`. Extra keys dropped. `--format` restricted by argparse `choices`. Nothing is coerced, defaulted or skipped. | `test_security_import_shape.py` — 14 malformed shapes incl. reordered/re-cased header, 3- and 5-field rows, top-level object, non-object element, `tags` as string, `tags` holding a number, invalid UTF-8, a BOM, a zero-byte file |
| No string-built interpretation | SR-012, SR-016 | HTML written with per-context escaping (`&`/`<`/`>` in text; those plus `"` in `href`), `&` replaced first. SQL still fixed strings with `?` placeholders — no new statement. `FILE`'s content is never executed, imported, evaluated or templated, and no reference inside it is followed. | `test_security_html_escaping.py` (`<script>`, `" onmouseover=x`, `"`+`&` in a URL, plus an `html.parser` round-trip); `test_security_import_no_execution.py` (shell metacharacters, traversal sequences and an unreachable URL stored as literal text, with `socket` and `posix_spawn` monkeypatched to fail the test if called) |
| Path containment | n/a — documented deviation, extending 001's | `FILE` is a first-party operator argument exactly like `--db`, with no allowed base directory to confine it to (spec Assumptions). It is used only as a filesystem path, never as a shell word; no component comes from stored data or the environment; it is opened **read-only**. Expiry condition: revisit if any path is ever derived from stored, imported or remote input — note that a path appearing *inside* an import file is already covered, since SR-016 forbids following any reference in `FILE`. | `test_security_import_no_execution.py` asserts `../../etc/passwd` inside a field is stored as text and not resolved; `test_import_contract.py` asserts an unreadable path errors (exit 2) rather than importing nothing silently |
| Credential storage | n/a | No credentials, passwords, tokens or secrets exist in this feature | — |
| Randomness and comparison | n/a | No tokens, salts or secret comparisons; identifiers remain SQLite `AUTOINCREMENT` sequence values, not security tokens | — |
| Resource limits | SR-014, SR-019 | `FILE` ≤ 32 MiB checked by `os.path.getsize` **before** opening; ≤ 50,000 records checked as records accumulate; per-field limits inherited from SR-006 unchanged (URL 8192, title 4096, tag text 4096, ≤ 64 tags of ≤ 128 chars). `RecursionError` from deeply nested JSON is caught and reported, so parsing cannot exhaust the stack. HTML export streams from the lazy cursor. | `test_security_import_limits.py` (32 MiB + 1; 50,001 records; one character over each field limit; 100,000-deep JSON); `test_security_html_streaming.py` (`tracemalloc` peak at 50,000 within the 5,000 ceiling) |
| Access control | n/a | Single-user local tool; OS file permissions on the database remain the access control (SR-005, unchanged). The two-phase design also removes a time-of-check-to-time-of-use gap: the file is read **once**, not validated and then re-read (research.md R3) | — |
| File permissions | SR-005 (inherited), SR-017 | A database created by `import` is created by the **same** `os.open(..., O_CREAT\|O_EXCL, 0o600)` path as any other command — `import` adds no file-creating code. `FILE` is opened `"r"` only; nothing else on the filesystem is created, truncated, modified or deleted. | `test_security_import_readonly.py` (FILE's bytes, size and `st_mtime_ns` unchanged after a successful **and** a failed import; database directory holds only the database file); `test_cli_surface_v2.py::test_import_creates_missing_database` asserts mode `0600` |
| Output hygiene | SR-018 | Every expected failure is one line through the existing `main()` → `BookmarksError` path, so the new command inherits the guarantee rather than reimplementing it. Message vocabulary is chosen against the inherited disclosure test: positions are `row N`/`record N` (never `line N`), paths are rendered `{path!r}` (never `file "..."`), and no exception class name or SQL text appears. | `test_security_import_messages.py` — every documented status-2 failure plus the unusable- and corrupt-database cases, asserting one line, ≥ 3 words, and none of the forbidden substrings |
| — (atomicity, extends SR-009) | SR-015 | Input faults are decided before the collection is opened, so no write is attempted and a missing database file is not created. Storage faults roll back one `with connection:` transaction covering every insert. The `AUTOINCREMENT` high-water mark in `sqlite_sequence` rolls back with it — **verified empirically** (research.md R4), which is what satisfies "the identifier issued by the next successful `add` is unaffected". | `test_security_import_atomicity.py` — 100 records with the last invalid adds none; an injected mid-write storage failure leaves zero new rows and no orphan tag row; the next `add`'s identifier is unaffected |

**Carried-over deviation, restated as the compliance review requires:** feature 001's
documented deviation that **CSV output is not spreadsheet-hardened** still stands and now
applies in both directions — `import` reads back exactly what `export` wrote, so hardening one
side would break FR-032's round-trip clause and SC-009. Expiry condition unchanged: revisit if
a requirement ever targets a spreadsheet macro engine as a consumer. This feature adds no new
deviation of its own.

**HTML is hardened, not excepted.** The spec's own Assumptions anticipate the opposite reading
and settle it: the skeleton in FR-041 shows bare `URL` and `TITLE` placeholders, but the
constitution's "encode output for the context it is written into" control is non-negotiable and
cannot be weakened by a feature, and the description's worked example is unaffected because
`https://docs.python.org` and `Python docs` contain no escapable character. FR-043 is therefore
implemented as written and US2 scenario 2 still holds byte-for-byte.

**Post-Design re-check (after Phase 1): PASS.** The Phase 1 artifacts introduced no new
dependency, no new module, no new table, no new SQL statement and no new error-handling path —
`main()`'s existing `BookmarksError` mapping carries every new failure. The two design questions
that could have added complexity were both resolved against the standard library and verified
empirically rather than assumed: `AUTOINCREMENT` rollback semantics (research.md R4) and
`json.loads`' behaviour on 100,000-deep input (R8). Phase 1 also *removed* a planned component —
the sixth module — once the feature-001 test constraints were read (R1). No gate changes status.

## Project Structure

### Documentation (this feature)

```text
specs/002-import-html-export/
├── plan.md                              # This file (/speckit-plan command output)
├── research.md                          # Phase 0 output
├── data-model.md                        # Phase 1 output
├── quickstart.md                        # Phase 1 output
├── contracts/                           # Phase 1 output
│   ├── cli-contract.md                  # Delta contract: `import`, `export --format html`
│   └── requirements-test-matrix.md      # FR/SR → test mapping (Principle III)
├── checklists/                          # Pre-existing
│   └── requirements.md
└── tasks.md                             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

No file is added or removed. `M` marks a modified file; everything else is untouched.

```text
src/
└── bookmarks/
    ├── __init__.py            # unchanged
    ├── __main__.py            # unchanged
    ├── cli.py            (M)  # + MAX_IMPORT_BYTES / MAX_IMPORT_RECORDS constants
    │                          # + `import` subparser; "html" added to export's choices tuple
    │                          # + _read_csv_records() / _read_json_records() / _validate_record()
    │                          # + cmd_import(); COMMANDS gains "import"
    │                          # + `import csv`, `import json` (both already in the whitelist)
    ├── output.py         (M)  # + HTML_PROLOGUE / HTML_EPILOGUE constants
    │                          # + _escape_text() / _escape_attr() / write_html()
    └── storage.py        (M)  # + _insert_bookmark() private helper, used by both writers
                               # + add_bookmarks() — one transaction for a whole import
                               #   (add_bookmark refactored onto the helper; behaviour identical)

tests/
├── conftest.py           (M)  # + write_file(name, text_or_bytes), database_fingerprint(path)
│                              #   purely additive; no existing fixture renamed or changed
├── contract/
│   ├── test_cli_surface.py            # unchanged (001)
│   ├── test_output_formats.py         # unchanged (001)
│   ├── test_exit_statuses.py          # unchanged (001)
│   ├── test_cli_surface_v2.py    (new)  # FR-030, FR-031, FR-040
│   ├── test_import_contract.py   (new)  # FR-038, FR-039, SC-012
│   └── test_html_format.py       (new)  # FR-041, FR-042, FR-044
├── integration/
│   ├── test_story1…4, test_persistence.py, test_performance.py   # unchanged (001)
│   ├── test_story5_import.py     (new)  # US1 AS1–AS7, FR-034, FR-036, FR-037
│   ├── test_story6_html_export.py(new)  # US2 AS1–AS5
│   ├── test_story7_roundtrip.py  (new)  # US3 AS1–AS4, SC-008, SC-009
│   ├── test_compatibility.py     (new)  # FR-028, FR-029, SC-011, US2 AS6
│   └── test_performance_v2.py    (new)  # SC-013 (marked slow)
├── security/
│   ├── test_security_*.py (12 files)    # unchanged (001) — incl. stdlib_only, no_traceback
│   ├── test_security_html_escaping.py        (new)  # SR-012, SC-014
│   ├── test_security_import_shape.py         (new)  # SR-013
│   ├── test_security_import_limits.py        (new)  # SR-014 (marked slow where large)
│   ├── test_security_import_atomicity.py     (new)  # SR-015
│   ├── test_security_import_no_execution.py  (new)  # SR-016
│   ├── test_security_import_readonly.py      (new)  # SR-017
│   ├── test_security_import_messages.py      (new)  # SR-018
│   └── test_security_html_streaming.py       (new)  # SR-019 (marked slow)
└── unit/
    ├── test_tag_parsing.py, test_url_validation.py, test_formatting.py   # unchanged (001)
    ├── test_import_records.py    (new)  # FR-032, FR-033, FR-035
    └── test_html_escaping.py     (new)  # FR-043

pytest.ini                       # unchanged — `pythonpath = src`, `slow` marker already defined
```

**Structure Decision**: Single project, unchanged layout. The `src/bookmarks` package keeps
exactly its five shipped modules and the test suite keeps its
`contract/` + `integration/` + `security/` + `unit/` split, with new modules added and none
edited. This is not merely the convenient choice: feature 001's
`test_security_stdlib_only.py::test_shipped_files_are_the_five_planned_modules` asserts the
shipped file list, so SC-011 ("every test written for feature 001 passes unchanged") makes the
five-module layout a hard requirement rather than a preference. Placement within those five
follows the existing separation of concerns — untrusted input is validated in `cli.py`,
bookmarks are rendered in `output.py`, SQL lives in `storage.py`.

## Complexity Tracking

> Filled because the constitution's compliance review requires every deviation and every
> complexity beyond the minimum to be documented with a justification and an expiry condition.
> The first two rows are *reductions* in generality, recorded because they are the non-obvious
> choice a reviewer would otherwise question; the third is a bounded memory cost.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Import logic lives in `cli.py` rather than a dedicated `importer.py`, making `cli.py` the largest module | SC-011 requires every feature-001 test to pass unchanged, and `test_shipped_files_are_the_five_planned_modules` asserts the shipped file list is exactly five names. A sixth module fails that test. The addition is ~90 lines in the module that already owns untrusted-input validation. | The "simpler alternative" here is the *new module*, and it is rejected only by SC-011. **Expiry condition:** if the user chooses to amend that one assertion's expected list, move the reader and validator into `src/bookmarks/importer.py` unchanged — the functions are already independent of the rest of `cli.py`. Recorded in research.md R1. |
| HTML escaping by four explicit `str.replace` calls instead of `html.escape` | `test_whole_package_imports_only_these_standard_modules` (feature 001) asserts the package's import set is a subset of a list that does not include `html`; importing it fails that test and breaks SC-011. The replacements implement exactly FR-043's stated minimum, per context. | `html.escape(value, quote=True)` is the obvious and more conventional answer, and this plan would use it absent the whitelist. The hand-rolled version's one real hazard — replacing `&` after `<`, producing `&amp;lt;` — is pinned by `test_ampersand_is_escaped_first`, and SR-012 plus SC-014 add a negative test and an `html.parser` round-trip. **Expiry condition:** if `html` is ever added to that whitelist, replace both helpers with `html.escape(v)` and `html.escape(v, quote=True)` and delete the ordering test. Recorded in research.md R2. |
| JSON import materialises the parsed document in memory (peak ≈ a few × the file size, bounded by the 32 MiB file limit) rather than streaming records | The standard library has no incremental JSON array parser, and SR-019 explicitly permits import memory to be "bounded by the limits of SR-014 rather than by the collection's size" — which this is: peak is independent of how many bookmarks the collection already holds, and capped by the 32 MiB input gate checked before any read. | Writing an incremental JSON parser would mean several hundred lines of new, security-relevant, hand-rolled parsing code — far more risk and maintenance than the memory it saves, and squarely against Principle IV. Switching the CSV path to streaming instead is *already* done (`csv.reader` over the open handle). **Expiry condition:** revisit if the input limit is ever raised above 32 MiB, or if a requirement ever asks for a fixed memory ceiling independent of input size. Recorded in research.md R8. |
