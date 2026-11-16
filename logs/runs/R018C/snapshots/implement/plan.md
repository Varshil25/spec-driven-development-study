# Implementation Plan: Import and HTML Export

**Branch**: `002-import-html-export` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-import-html-export/spec.md`

## Summary

Add two capabilities to the working bookmark manager, without changing anything it already does:
an `import FILE --format csv|json` command that bulk-loads bookmarks from the same two file
shapes `export` writes, and a third export format, `--format html`, that renders the collection
as one fixed, byte-predictable HTML page.

The technical approach is deliberately small — three files touched, one file added:

- **`importer.py` (new)** reads the file with `encoding="utf-8-sig"` (which gives UTF-8 decoding
  and the byte-order-mark rule in one step), parses it with `csv.reader` or `json.loads`, and
  validates the shape by hand so every failure can name what was wrong and what was expected.
  It opens no database.
- **Atomicity comes from ordering, not rollback**: the file is read, parsed and fully validated —
  including the URL scheme check on every record — *before* `store.open_store` is called. Since
  opening the store is what creates the store file, this is the only design that delivers
  "a failed import creates no store file" (FR-011), and it also keeps file failures (status 2)
  structurally separate from store failures (status 1).
- **`store.add_bookmarks`** shares one insert path with the existing `add_bookmark`, so
  "added exactly as `add` would add it" (FR-003) is guaranteed structurally rather than by
  inspection, and commits once so 1,000 bookmarks do not cost 1,000 fsyncs.
- **`render_html`** uses `html.escape(value, quote=False)` plus an explicit `"` → `&quot;` inside
  the `href`, which is exactly FR-014's closed set of four substitutions and leaves the
  apostrophe literal. Registering it in the existing `RENDERERS` dict gives dispatch, the
  `--format` choices and the invalid-format exit 2 for free, and leaves the CSV and JSON paths
  literally untouched (FR-015).

## Technical Context

**Language/Version**: Python 3.11+ (declared once in `pyproject.toml` as `requires-python =
">=3.11"`, unchanged). Development and verification on 3.13.17.

**Primary Dependencies**: None at runtime. Standard library only: `argparse`, `csv`, `json`,
`sqlite3`, `sys`, `html` (new to this feature), `pathlib`. `pytest` remains the only development
dependency and is never imported by shipped code.

**Storage**: The existing SQLite store, schema **unchanged** — no migration, no new table, no new
column (FR-016). Default path `bookmarks.db`, overridable with the existing global `--db`.

**Testing**: pytest. Two new files, `tests/test_import.py` and `tests/test_html_export.py`, plus
additions to `tests/test_performance.py`; every test name identifies the requirement it covers.
No existing test file is modified (FR-020, SC-006). CLI behaviour is exercised through the
existing `run_cli` subprocess fixture, because the exit statuses are process statuses.

**Target Platform**: Any platform with CPython 3.11+; developed and verified on Linux.

**Project Type**: Single-project command-line tool (existing `src/bookmarks/` package).

**Performance Goals**: Import of 1,000 bookmarks in under 5 seconds; HTML export of a
1,000-bookmark collection in under 1 second (SC-005). Met by one commit for the whole import
(research R-106) and by reusing the existing single-query read path for the page.

**Constraints**: Byte-exact output — the HTML page is asserted byte-for-byte, and CSV/JSON output
must be byte-identical to the previous version (FR-013, FR-014, FR-015, SC-004, SC-006). Strict
stream split: results on stdout, diagnostics on stderr, no partial stdout from a failing command
(FR-018). Exit-status map extended, never redefined: 0/1/2/3 as before, with every import-file
failure landing on 2 (FR-017). All-or-nothing import, with no store file created on failure
(FR-011).

**Scale/Scope**: One new command, one new export format, one new module (~90 lines), two new
functions in `store.py`, one renderer plus one handler and subparser in `cli.py`. Collections of
a few thousand bookmarks; single user, single machine, no concurrent access.

No `NEEDS CLARIFICATION` items remain: the spec's five clarifications settled the escaping set,
the quoted CSV header, the byte-order mark, the blank-line rule and the empty-store-on-success
question, and [research.md](./research.md) resolves every technical unknown (R-101 … R-110).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against [constitution](../../.specify/memory/constitution.md) v1.0.0.

### Initial check (pre-Phase 0) — PASS

| Principle | Assessment |
| --------- | ---------- |
| **I. Standard Library Only** | PASS. `csv`, `json`, `html` are standard library; the only new import anywhere is `html`. No third-party runtime dependency is contemplated (FR-019). |
| **II. Fail Loudly** | PASS. FR-010 requires a specific stderr diagnostic naming the file, what was invalid and what was expected, plus exit 2, for every file fault. FR-011 forbids skipping a bad record to keep going, and the spec's Assumptions explicitly rule out a partial-success mode — which is Principle II's "MUST NOT … skip a bad record" stated as a requirement. |
| **III. Every Requirement Is Testable (NON-NEGOTIABLE)** | PASS. FR-020 requires a pytest test per functional requirement, identified by name; every FR here is observable at the CLI boundary (bytes on a stream plus an exit status). |
| **IV. Simplicity** | PASS. One new module, two new store functions, one renderer. Scope is bounded by the spec's own exclusions (no `--continue-on-error`, no dry run, no merging, no `import --format html`, no page styling), all of which are recorded as Assumptions and none of which will be built. |

### Additional Constraints

| Constraint | Assessment |
| ---------- | ---------- |
| Python floor declared once | PASS — `pyproject.toml`, unchanged. No syntax newer than 3.11 is used. |
| pytest as the only dev dependency | PASS — no new tooling. |
| Results to stdout, diagnostics to stderr | PASS — FR-018; the new command adds nothing to stdout on failure. |
| No hidden global state or env-driven behaviour | PASS — behaviour comes from `FILE`, `--format` and `--db` only. `--format` is authoritative, and the file's name, extension and contents are never consulted (FR-008). |

### Post-design re-check (after Phase 1) — PASS

Re-evaluated against the generated design. No violation introduced, and three design choices
tightened compliance:

| Principle | Post-design finding |
| --------- | ------------------- |
| **I** | Confirmed: the design adds exactly one import, `html`, used for `html.escape` only (research R-107). |
| **II** | **Strengthened.** `utf-8-sig` with no `errors=` parameter was chosen specifically so undecodable bytes raise rather than becoming U+FFFD — the "silent wrong answer" the principle ranks highest in severity (R-101). `csv.DictReader` was rejected because it would silently absorb a wrong header and a wrong field count (R-102). The validate-before-open ordering means no failure can be misreported as a store error (R-105). Every FR-010 cause has a drafted message naming the file, the fault and the expectation, listed in the contract. |
| **III** | Confirmed: the contract enumerates each failure cause as a separately observable outcome, and the test plan (R-110) maps FR-001…FR-014 to two new files with requirement-named tests. The pre-existing suite — the 131-passed baseline — is the evidence for FR-015/SC-006 and is not modified. |
| **IV** | **Strengthened.** Registering `render_html` in the existing `RENDERERS` dict means the invalid-`--format` path, the help text and the dispatch need no new code (R-108). Sharing `_insert_bookmark` removes a would-be second insert path (R-106). Rejected as speculative generality: a schema-validation layer for JSON (R-103), a second tag normaliser for the JSON list form (R-104), an `html.py` module (R-108), a new exception type for file errors (R-109), and rollback machinery (R-105). |

**Complexity Tracking**: not required — no violations to justify.

One judgment call worth recording for the Gate 5 reviewer: `importer.py` is a *third* module in a
package the constitution would otherwise keep flat at two. It is justified against FR-006/FR-007
(two file shapes with a dozen distinct failure diagnostics, ~60 lines of parsing) and by the
spec's own Key Entities, which place the import file outside the collection that `store.py` owns;
folding it into `cli.py` or `store.py` would make that module about two things (R-109). The layout
stays flat — three modules, no subpackages.

## Project Structure

### Documentation (this feature)

```text
specs/002-import-html-export/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification (input)
├── research.md          # Phase 0 output: R-101 … R-110
├── data-model.md        # Phase 1 output: import record shapes + HTML projection
├── quickstart.md        # Phase 1 output: six end-to-end validation scenarios
├── contracts/
│   └── cli-contract-002.md   # Phase 1 output: the new CLI surface, byte-exact
├── checklists/          # Pre-existing (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/bookmarks/
├── __init__.py          # unchanged
├── __main__.py          # unchanged
├── cli.py               # MODIFIED: + render_html, + handle_import, + import subparser,
│                        #   + "html" in RENDERERS
├── importer.py          # NEW: file reading, the two parsers, record validation
└── store.py             # MODIFIED: + add_bookmarks, + _insert_bookmark (extracted from
                         #   add_bookmark, whose behaviour is unchanged)

tests/
├── conftest.py          # unchanged (db, run_cli, seed, seed_many fixtures reused)
├── test_add.py          # unchanged
├── test_cli_contract.py # unchanged
├── test_delete.py       # unchanged
├── test_export.py       # unchanged — the FR-015/SC-006 evidence
├── test_list_search.py  # unchanged
├── test_store.py        # unchanged
├── test_performance.py  # MODIFIED: + the two SC-005 budgets
├── test_import.py       # NEW: FR-001 … FR-011, plus the round trip (User Story 3)
└── test_html_export.py  # NEW: FR-012, FR-013, FR-014

pyproject.toml           # unchanged
```

**Structure Decision**: The existing single-project layout is kept exactly as it is — `src/` for
the package, `tests/` flat beside it, `src/` reached via `pythonpath = ["src"]` in
`pyproject.toml`. This feature is an extension of a working tool, so the structure question is
settled by precedent; the only addition is one module inside the existing package, justified in
the Constitution Check above. No new directory is created anywhere outside `specs/`.

## Phase 0: Outline & Research — complete

Output: [research.md](./research.md). Ten decisions, each with rationale and rejected
alternatives; the findings marked **verified** were confirmed by running the standard library
during this phase (BOM stripping, the blank-line-yields-`[]` behaviour, embedded newlines in
quoted fields, `IsADirectoryError`, `UnicodeDecodeError`, and both branches of `html.escape`).

| ID | Decision |
| --- | --- |
| R-101 | Read with `encoding="utf-8-sig", newline=""`; `OSError`/`UnicodeDecodeError` → status 2 |
| R-102 | `csv.reader` with default dialect; compare the parsed header record; require exactly 4 fields |
| R-103 | `json.loads` plus explicit structural checks, in a fixed order |
| R-104 | Both shapes reach the existing `store.normalise_tags`; JSON joins its array with `,` |
| R-105 | Validate the entire file before `open_store` — the source of every atomicity guarantee |
| R-106 | One shared insert path; `add_bookmarks` commits once |
| R-107 | `html.escape(quote=False)` + an explicit `"` → `&quot;` in `href` only |
| R-108 | `render_html` registered in the existing `RENDERERS` dict; CSV/JSON paths untouched |
| R-109 | New module `importer.py` (not `import.py` — a reserved word); reuse `store.BookmarkError` |
| R-110 | Two new test files, requirement-named tests, byte-for-byte page assertions |

## Phase 1: Design & Contracts — complete

| Artifact | Contents |
| --- | --- |
| [data-model.md](./data-model.md) | The transient `ImportRecord`, both file shapes field by field, the worked tag-normalisation cases, the validation order with its five atomicity consequences, and the HTML projection with FR-014's closed escaping table. States plainly that the stored schema does not change. |
| [contracts/cli-contract-002.md](./contracts/cli-contract-002.md) | The complete new CLI surface: the `import` grammar, success output, the accepted shapes, a table of every failure cause with a drafted diagnostic, the atomicity rules, the extended `export --format` with the exact page bytes and two worked escaping examples, the extended exit-status map, and the internal module contract. Written as an extension to the `001` contract, which stays valid. |
| [quickstart.md](./quickstart.md) | Six runnable validation scenarios: both shapes into a fresh store, thirteen kinds of damaged file checked for the stderr/empty-stdout/status-2 triple plus the no-store-file rule, the HTML page including the characters that must stay literal, the round trip through both shapes with awkward values, the two performance budgets, and the regression gate (`git status --short tests/` showing no modified test). |

Entities were extracted from the spec's Key Entities and FR-003 … FR-009; the interface contract
from FR-001 … FR-014 and the exit-status map of FR-017. A contract is warranted here because the
project's external interface *is* a CLI, and this feature's requirements are stated in bytes and
exit statuses.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations. The table is intentionally empty.
