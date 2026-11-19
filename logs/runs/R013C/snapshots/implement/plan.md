# Implementation Plan: Bookmark Import and HTML Export

**Branch**: `002-import-html-export` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-import-html-export/spec.md`

**Extends**: [`001-bookmark-cli-manager`](../001-bookmark-cli-manager/plan.md). That plan's
structure decision, contracts and decisions D1–D9 stay in force; this plan adds D10–D19 and
changes nothing already built.

## Summary

Two additions to the existing five-command bookmark CLI, with every current command left
byte-identical:

1. **`import FILE --format csv|json`** — a sixth command that reads the formats `export` already
   writes and adds each bookmark exactly as `add` would (same URL rule, same verbatim title, same
   tag normalisation, store-assigned ids, `id` in the file ignored), printing `imported N`. It is
   all-or-nothing: an unreadable file, a file of the wrong shape, or a single URL `add` would
   reject makes the whole command fail with status 2 and leaves the store — including the highest
   id ever used — exactly as it was.
2. **`export --format html`** — a third export format printing a fixed, minimal page: DOCTYPE,
   a one-line `<head>` declaring UTF-8 and the title `Bookmarks`, `<body>`, `<ul>`, one
   `<li><a href="URL">TITLE</a> <small>TAGS</small></li>` per bookmark in ascending id order,
   then the closing tags.

Technical approach: `import` is a strictly ordered read → validate → insert pipeline (whole file
into memory, fully validated, then one `executemany` in a single transaction), so no insert is
reachable while a rejection is still possible and all-or-nothing needs no recovery path; file
read errors are caught at the read site so they exit 2 while an unusable store still exits 1; the
URL check is the existing `validate_url` and the tag rules are the existing `normalise_tags`, so
`import` cannot drift from `add`; the HTML page is a fixed list of lines escaping exactly `&`,
`<`, `>` and `"` (not the apostrophe, which FR-042 requires verbatim), and `html` joins
`--format`'s `choices` so rejecting any other format stays argparse's job. Runtime code adds only
`io` and `html` to the existing standard-library imports; `pytest` remains the sole development
dependency. Every decision and the alternatives rejected are in [research.md](./research.md).

## Technical Context

No NEEDS CLARIFICATION remains: the specification, the existing code and the planning input
(Python 3.11+, standard library only, the specified interface exactly, `pytest` for tests) fix
every choice.

**Language/Version**: Python 3.11+ (declared minimum 3.11; local interpreter 3.13.17). No syntax
or library feature newer than 3.11 is used — in particular the file is read with
`open(..., newline="")` rather than `Path.read_text(newline=...)`, which arrived in 3.13
([research.md D15](./research.md#d15-the-file-is-read-as-utf-8-and-its-read-errors-become-status-2--never-status-1)).

**Primary Dependencies**: none at runtime — standard library only. Existing: `argparse`,
`sqlite3`, `csv`, `json`, `sys`. Added by this feature: `io` (one `StringIO` for CSV parsing) and
`html` (one `escape` call). Development: `pytest` (9.1.1 available locally), never imported by
runtime code.

**Storage**: the same single SQLite file and the same one-table schema as feature 001, unchanged —
no migration, no new column, no new table (FR-046). `import` appends rows; the HTML export is
read-only.

**Testing**: `pytest`, run as `pytest` from the repository root (`pythonpath = ["src"]` already in
`pyproject.toml`). Four new modules reusing the existing `conftest.py` fixtures; the five existing
test modules and `conftest.py` are not edited, which is how FR-045/SC-014 are demonstrated.
Import files are written into pytest's `tmp_path`.

**Target Platform**: any OS with CPython 3.11+ (developed and verified on Linux); terminal /
script invocation, no network access.

**Project Type**: single-package command-line tool (`bookmarks` package under `src/`) plus a test
suite — unchanged from feature 001.

**Performance Goals**: importing 1,000 bookmarks and exporting 1,000 bookmarks as HTML each
complete in under five seconds end-to-end including interpreter start-up (SC-015); the single
transaction makes the import one commit rather than 1,000 (D10).

**Constraints**: standard library only at runtime (Principle I); no network access; no writes
outside the caller-supplied store path, and in particular `import` never writes to the file it
reads; no implicit global mutable state; a failed import leaves the store byte-identical *and*
leaves the id high-water mark unchanged (FR-037, SC-010); every existing command keeps its
arguments, output bytes, stderr behaviour and exit status (FR-045); exit status 2 means "an input
value was refused" and 3 still belongs to `delete` alone (FR-047).

**Scale/Scope**: single user, one invocation at a time, no concurrent access; files of thousands
of bookmarks read entirely into memory (spec Assumptions); 24 new functional requirements
(FR-024…FR-047); one new command plus one new export format; ~170 added lines of runtime code
(`cli.py` ~430 total, `storage.py` ~85 total).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0 (ratified 2026-11-14), four principles.

| Gate | Requirement | Pre-Phase-0 | Post-Phase-1 |
|------|-------------|-------------|--------------|
| **I. Standard Library Only** (NON-NEGOTIABLE) | No third-party runtime import; runs on bare CPython 3.11+; `pytest` is the only dev dependency and is never imported by runtime code | **PASS** — the spec and the planning input both constrain the tool to the stdlib; `csv`, `json`, `io`, `html`, `sqlite3` cover every requirement, so no HTML templating or validation library is needed | **PASS** — the final import list is `argparse`, `csv`, `html`, `io`, `json`, `sqlite3`, `sys`; `pytest` appears solely under `tests/`. No new file in `pyproject.toml`'s dependency surface (there is none to add to) |
| **II. Fail Loudly** | Specific diagnostic naming the problem on stderr + non-zero exit; no bare `except`, no `except Exception: pass`; no silent fallbacks or masked defaults | **PASS** — FR-034…FR-037, FR-044 and SC-011 already demand a named diagnostic, a documented status and an untouched store for every failure | **PASS** — every rejection path has a row in [contracts/import-command.md](./contracts/import-command.md#diagnostics-stderr) naming the value it reports; the new `except` clauses catch `OSError`, `UnicodeDecodeError`, `csv.Error` and `json.JSONDecodeError` **narrowly** and only to re-raise them wrapped as `ImportRejected` with the file name and problem (D12), which the principle permits explicitly; the shape checks reject rather than default (no padded CSV rows, no missing-key defaults, no `errors="replace"` decoding), and a wrong field count or missing key is a rejection, not a coerced value (D13, D14, D15) |
| **III. Every Requirement Is Testable** | Every FR maps to ≥1 `pytest` test whose name or docstring names it; error paths tested; full suite green | **PASS** — all 24 new FRs are observable through stdout bytes, stderr, exit status, or a later `list` invocation; SC-013 already requires the named mapping | **PASS** — the Testing Strategy table maps FR-024…FR-047 to a named test in one of four new modules, including all nine rejection paths (missing file, directory, non-UTF-8, bad CSV header, wrong field count, non-array JSON, missing key, ill-typed `tags`, bad URL) and the two unchanged-behaviour requirements; the parsers and `render_html` are pure functions, so each is testable without a store or a captured stream |
| **IV. Simplicity** | Smallest design that satisfies the spec; no speculative extension points; plain functions and data; one module until a reason to split appears; extra structure justified by the requirement forcing it | **PASS** — nothing in the two features suggests an abstraction: two input formats, one output format, no configurability requested and several extensions explicitly out of scope (`--dry-run`, `--skip-invalid`, HTML import, export to file) | **PASS** — no new module (parsers sit beside the exporters they mirror, D11), no new class except the three-line `ImportRejected` exception forced by FR-034…FR-036 needing one conversion point (D12), records passed as plain tuples rather than model objects, one new storage function (`add_bookmarks`) forced by D10's single transaction, and a two-branch `if` rather than a format registry. The HTML page is a list of literal lines, not a template engine (D17) |

**Gate result**: PASS at both checkpoints. The Complexity Tracking table below is empty — no
violation requires justification. No constitution amendment is needed: the plan introduces no
third-party runtime dependency, so the Principle I rejection rule in the Development Workflow does
not apply.

Two points where a plausible design would have violated a principle, recorded because the gate
turns on them:

- Using `html.escape`'s default `quote=True` would rewrite `'` as `&#x27;`, breaking FR-042's
  "text free of those characters MUST appear verbatim" — a silent corruption of stored text, which
  Principle II treats as the worst outcome. The design escapes exactly four characters (D16).
- Letting `main()`'s existing `OSError` handler report an unreadable *file* would exit 1 where
  FR-034 requires 2 and would name the store instead of the file — a misleading diagnostic. The
  design catches file errors at the read site (D15).

## Project Structure

### Documentation (this feature)

```text
specs/002-import-html-export/
├── plan.md                   # This file (/speckit-plan command output)
├── spec.md                   # Feature specification
├── research.md               # Phase 0 output — design decisions D10–D19
├── data-model.md             # Phase 1 output — transient shapes, validation order, effects
├── quickstart.md             # Phase 1 output — nine runnable validation scenarios
├── contracts/                # Phase 1 output
│   ├── import-command.md     #   import surface, CSV/JSON input shapes, diagnostics, statuses
│   └── html-export.md        #   exact HTML page bytes, item format, escaping
├── checklists/               # Existing quality checklists
└── tasks.md                  # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml                 # unchanged: pytest config only (pythonpath = ["src"])
src/
└── bookmarks/
    ├── __init__.py            # unchanged (empty marker)
    ├── __main__.py            # unchanged (raise SystemExit(main()))
    ├── cli.py                 # CHANGED: + ImportRejected, parse_csv_import, parse_json_import,
    │                          #   escape_html, render_html, _import; _export gains the html
    │                          #   branch; build_parser gains the import subparser and the
    │                          #   html choice. Existing functions untouched.
    └── storage.py             # CHANGED: + add_bookmarks(conn, records) — one executemany in a
                               #   single transaction. SCHEMA and existing functions untouched.
tests/
├── conftest.py                # unchanged (db_path, run, run_cli fixtures reused as-is)
├── test_add.py                # unchanged  ┐
├── test_list_search.py        # unchanged  │ the five pre-existing modules are not edited;
├── test_delete.py             # unchanged  │ their passing unmodified is how FR-045 and
├── test_export.py             # unchanged  │ SC-014 are demonstrated
├── test_cli.py                # unchanged  ┘
├── test_import.py             # NEW: FR-024…FR-038 (surface, CSV, JSON, add-rules, rejections)
├── test_export_html.py        # NEW: FR-039…FR-044 (page bytes, items, escaping, empty, format)
├── test_roundtrip.py          # NEW: User Story 3, SC-009 (export → import equality both formats)
└── test_compatibility.py      # NEW: FR-045, FR-046, FR-047 (old commands, old store, statuses)
```

**Structure Decision**: unchanged from feature 001 — single project, runtime code in
`src/bookmarks/`, tests in `tests/`, no `models/`/`services/`/`lib/` subdivision. This feature
adds **no runtime module**: the two parsers are the mirror image of `export_csv`/`export_json` and
belong beside them in `cli.py`, which is also where every input/output and exit-status decision
already lives; the one function that issues SQL goes to `storage.py`, preserving the single seam
feature 001 drew (`storage.py` never touches `sys.stdout`, `cli.py` issues no SQL). After the
change `cli.py` is ~430 lines and `storage.py` ~85 — still one concern each, and a split would be
the speculative structure Principle IV forbids
([research.md D11](./research.md#d11-no-new-runtime-module-parsing-lives-in-clipy-one-new-query-in-storagepy)).

### New runtime surface

| Function | Module | Purpose | Requirements |
|----------|--------|---------|--------------|
| `ImportRejected(Exception)` | `cli.py` | carries a rejection diagnostic; caught once, in `_import` | FR-034…FR-036 |
| `read_import_text(path)` | `cli.py` | read the file as UTF-8 (`newline=""`); OS and decoding errors → `ImportRejected` naming the path | FR-034 |
| `parse_csv_import(text)` | `cli.py` | exact header check, four-field rows, tags via `normalise_tags` → records | FR-027…FR-029 |
| `parse_json_import(text)` | `cli.py` | array/object/key/type checks, extra keys ignored, tags joined then `normalise_tags` → records | FR-030, FR-031 |
| `escape_html(value)` | `cli.py` | escape exactly `&`, `<`, `>`, `"` | FR-042 |
| `render_html(rows)` | `cli.py` | the whole page as one string from a fixed line list | FR-040, FR-041, FR-043 |
| `_import(args)` | `cli.py` | read → parse → `validate_url` each → open store → insert → print `imported N` | FR-024…FR-026, FR-032, FR-036…FR-038 |
| `add_bookmarks(conn, records)` | `storage.py` | one `executemany` + one `commit`; returns the number inserted | FR-025, FR-032, FR-033, FR-037 |

## Testing Strategy

Per Principle III each test names the requirement it covers in its name or docstring (e.g.
`def test_import_rejects_whole_file_for_one_bad_url():  """FR-036, FR-037"""`). Coverage map:

| Requirement | Covering test module | Observable checked |
|-------------|---------------------|--------------------|
| FR-024 | `test_import.py` | `import FILE --format csv` and `--format json` accepted via `python -m bookmarks`; `FILE` required; `--format` required and limited to those two values (any other → status 1) |
| FR-025 | `test_import.py` | ids follow file order; a store with ids 1–2 continues at 3, 4 |
| FR-026 | `test_import.py` | stdout is exactly `imported 2\n` and nothing else; status 0 |
| FR-027 | `test_import.py` | exact header accepted; `url,title,tags`, `id, url, title, tags` and an empty file rejected; a 3- and a 5-field row rejected; the id column ignored |
| FR-028 | `test_import.py` | `" python , , docs "` and `"notes,notes"` → `docs,python` / `notes`; empty field → no tags |
| FR-029 | `test_import.py` | a row whose title holds a comma, a doubled quote and a newline reads back as the original value |
| FR-030 | `test_import.py` | array of objects accepted; object top level, scalar top level, non-object element, missing `url`/`title`/`tags`, non-string `url`/`title`, `tags` not an array, `tags` holding a number → status 2 |
| FR-031 | `test_import.py` | an element carrying `id` and an unknown key imports, the `id` ignored |
| FR-032 | `test_import.py` | imported bookmark equals the `add`-created one field for field (URL rule, verbatim title incl. blank and non-ASCII, tag rules, duplicate URLs kept) |
| FR-033 | `test_import.py` | ids `99`/`100` in the file produce ids 3/4; after a `delete` of the highest id, a later import does not reuse it |
| FR-034 | `test_import.py` | missing path, a directory, an unreadable file and non-UTF-8 bytes → stderr names the path, stdout empty, status 2; a store that did not exist is **not** created |
| FR-035 | `test_import.py` | each malformed-shape case → stderr names the problem, stdout empty, status 2, nothing added |
| FR-036 | `test_import.py` | a valid file whose second bookmark is `ftp://…` → stderr names that URL, status 2, **neither** bookmark added |
| FR-037 | `test_import.py` | listing byte-identical across every rejection; the next `add` receives the pre-import id (SC-010) |
| FR-038 | `test_import.py` | header-only CSV and `[]` → `imported 0`, status 0, store still empty |
| FR-039 | `test_export_html.py` | `--format html` accepted; one item per bookmark in ascending id order, including when titles sort differently from ids; status 0 |
| FR-040 | `test_export_html.py` | stdout equals the documented nine-line skeleton line for line, with the trailing newline |
| FR-041 | `test_export_html.py` | each line is exactly `<li><a href="URL">TITLE</a> <small>TAGS</small></li>`; tags comma-joined alphabetically; no tags → `<small></small>` |
| FR-042 | `test_export_html.py` | `&`, `<`, `>`, `"` in URL, title and tag → `&amp;`/`&lt;`/`&gt;`/`&quot;`; apostrophe and non-ASCII verbatim; page parses with `html.parser` |
| FR-043 | `test_export_html.py` | empty store → skeleton with zero `<li>` lines, status 0 |
| FR-044 | `test_export_html.py` | `--format xml` and a missing `--format` → stderr, status 1 (not 2) |
| FR-045 | `test_compatibility.py` + the five unmodified modules | `list`, `search`, `delete`, `add` and the CSV/JSON exports compared against literal expected bytes; statuses 0/2/3 preserved; the pre-existing suite passes unedited |
| FR-046 | `test_compatibility.py` | a store built by a connection using only feature 001's schema is read and written by the new commands; after an import and an HTML export the schema (`sqlite_master`) is still exactly the one table |
| FR-047 | `test_compatibility.py` | status table: usage error 1, unusable store 1 (import with a store path that cannot be created), rejected import 2, bad `add` URL 2, absent delete id 3 |

Cross-cutting scenarios: `test_roundtrip.py` covers User Story 3 and SC-009 — store A holding a
bookmark with no tags, one with several, one whose title contains a comma and a double quote, and
one with non-ASCII text, exported in each format and imported into an empty store B, then compared
field by field ignoring ids; plus the double-import case (two independent copies, distinct ids).

Non-functional checks: SC-008 and SC-015 (1,000 bookmarks, under five seconds) are validated by
the timed scenario in [quickstart.md](./quickstart.md#scenario-9--bulk-performance-sc-008-sc-015)
rather than a wall-clock assertion in the suite, so test runs stay deterministic on shared
hardware — the same choice feature 001 made for SC-005. SC-012 (the page in a real browser) is a
manual step in [quickstart.md](./quickstart.md#scenario-6--escaping-and-non-ascii-in-the-page-fr-042-sc-012);
its machine-checkable part (escaping, well-formedness) is in `test_export_html.py`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. Both Constitution Check passes are clean, so this table is intentionally empty.
