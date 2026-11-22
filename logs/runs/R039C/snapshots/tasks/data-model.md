# Phase 1 Data Model: Phone Redaction and Output Folder

**Feature**: 002-phone-redaction-out-dir | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

This feature adds no new *type*. It extends two of feature 001's six entities and introduces four
more that are plain values. Per Principle IV, an entity is given a class only if the specification
demands one; none does, so every entity below is a `str`, an `int`, a `dict`, a tuple, or an open
file object.

Feature 001's model is in [../001-log-data-redaction-cli/data-model.md](../001-log-data-redaction-cli/data-model.md)
and remains authoritative for anything not restated here.

## Entity overview

| Entity | Representation | Status vs 001 | Lives in |
|---|---|---|---|
| Options | `argparse.Namespace` | **extended** — gains `out_dir` | `cli.build_parser` |
| InputSource | `(name: str, stream)` yielded pair | unchanged | `cli._iter_sources` |
| Line | `str` | unchanged | `cli._consume` |
| RedactionRule | module-level pattern + placeholder constants | **extended** — fourth rank | `redact` |
| Match | `(start: int, end: int, placeholder: str)` | unchanged | `redact.redact_line` |
| Counts | `dict[str, int]` | **extended** — fourth key | `redact`, `cli` |
| OutputDestination | `None` \| `str` (the DIR value) | **new** | `cli.main` |
| OutputFolder | `str` path + created-component list | **new** | `cli._make_out_dir` |
| OutputFile | `(path: str, stream)` | **new** | `cli._open_output` |
| WrittenTally | `int` | **new** | `cli.main` |

---

## 1. Options *(extended)*

| Field | Type | Default | Source | Validation |
|---|---|---|---|---|
| `count` | `bool` | `False` | `--count`, any position | none needed |
| `out_dir` | `str \| None` | `None` | `--out-dir DIR` / `--out-dir=DIR`, any position, last wins | rejected when `""`; rejected when `files` is empty |
| `files` | `list[str]` | `[]` | every non-option argument, in order | none at parse time; each is validated when opened |

**Three-state `out_dir`** (research.md D-106): `None` = stream to stdout exactly as feature 001 does
(FR-017); `""` = reject with a usage diagnostic and exit 2 (SC-008); any other string = the output
folder.

**Validation happens at the boundary** (SR-012), inside `main`'s parse block and therefore before
stdin is read, before any FILE is opened, and before DIR is touched:

| Condition | Action | Requirement |
|---|---|---|
| `out_dir == ""` | `parser.error` → usage on stderr, exit 2 | SC-008, SR-012 |
| `out_dir is not None and not files` | `parser.error` → usage on stderr, exit 2 | FR-012, US4-3 |

No value is ever coerced or substituted (Principle II): there is no fallback to stdout, to reading
stdin, or to a default folder name.

---

## 2. RedactionRule *(extended to four ranks)*

Still not an object — a rule is the pairing of a module-level pattern constant with a placeholder
constant and its position in the pipeline (001 data-model §4).

| Rank | Category | Placeholder | Recognition | Implemented by |
|---|---|---|---|---|
| 1 | email | `[EMAIL]` | 001 FR-004 grammar | `EMAIL_OR_IP` alternation, `email` group |
| 2 | IPv4 | `[IP]` | 001 FR-005 grammar | `EMAIL_OR_IP` alternation, `ip` group |
| 3 | card | `[CARD]` | 001 FR-006/FR-007 + Luhn | `find_card_spans`, over rank 1–2 gaps |
| 4 | **phone** | **`[PHONE]`** | **FR-001/FR-002** | **`_PHONE` pattern, over rank 1–3 gaps** |

**Phone recognition** (authoritative statement in
[contracts/redaction-rules.md](./contracts/redaction-rules.md)):

```python
PHONE_PLACEHOLDER = "[PHONE]"
_PHONE = r"\+[0-9]{8,15}(?![0-9])"
```

| Property | Value | Why |
|---|---|---|
| anchor | a literal `+`; the preceding character is never examined | FR-001, Assumptions |
| digits | ASCII `0`–`9` only, written out explicitly | FR-002 (`\d` would admit non-ASCII digits) |
| length | 8–15 inclusive, greedy (longest) | FR-001 |
| right boundary | `(?![0-9])` — a 16th contiguous digit rejects the whole candidate | FR-002, SR-002 |
| quantifier | bounded, no nesting | SR-004 |
| placeholder | fixed literal, no length hint, padding, hash, or counter | SR-001 |

---

## 3. Counts *(extended)*

```python
{"emails": 0, "ips": 0, "cards": 0, "phones": 0}
```

| Property | Rule | Requirement |
|---|---|---|
| keys | exactly those four, always present | FR-004 |
| value | number of **replacements**, not lines and not distinct values | FR-004, US3-3 |
| accumulation | `_consume` adds each line's deltas into the run-wide dict | FR-004 |
| scope | totalled across every input source, including every FILE of an `--out-dir` run | FR-016, US3-5 |
| reporting | one line on stderr, `--count` only, success only | FR-004, FR-016, US4-8 |
| rendering | `emails=N ips=N cards=N phones=N\n`, that field order, single spaces, no padding | FR-004 |

The dict carries integers only, so no input-derived text can reach stderr through it (SR-001).

---

## 4. OutputDestination *(new)*

A run has **exactly one** destination for its redacted stream.

| Value of `out_dir` | Destination of redacted lines | stdout also carries | Created on disk |
|---|---|---|---|
| `None` | standard output | nothing else | **nothing at all** (FR-017, SR-008) |
| a path | one file per FILE inside that folder | only `wrote N files` | DIR, its missing parents, the output files — and nothing else |

The destination is not an object: `main` passes either stdout or the current output file's stream as
`_consume`'s `out` argument. `_consume` is unchanged and unaware of which it has (research.md D-112).

**State transition** — there is one, and it is per-FILE, not per-run:

```text
                        (--out-dir given)
  FILE reached ──▶ input opened ──▶ output file opened ──▶ lines streamed ──▶ output closed ──▶ input closed
                        │                  │                     │                  │
                        └── OSError ───────┴── OSError ──────────┴── OSError ───────┘
                                              │
                                              ▼
                               diagnostic on stderr, exit 2,
                               no tally, no summary, later FILEs never opened
```

At most one output file exists in the open state at any moment (SR-011).

---

## 5. OutputFolder *(new)*

| Field | Type | Meaning |
|---|---|---|
| value | `str` | the `--out-dir` argument, **used as given** — not resolved, not rebased (Assumptions) |
| created components | `list[str]` | the path components that did not exist and were created by this run |

| Rule | Requirement |
|---|---|
| Created with every missing parent, before any output file is opened | FR-008 |
| Each component the tool creates: `mkdir(0o700)` then `chmod(0o700)` | SR-007, SC-007 |
| Components that already exist are used as-is and **not** re-permissioned | SR-008 |
| An existing regular file at the path is a loud failure, not a silent reuse | SC-008, Principle II |
| Never created when `--out-dir` is absent, or when no FILE was given | FR-017, FR-012 |
| It is the containment base every output path is verified against | SR-005 |

---

## 6. OutputFile *(new)*

One per FILE argument, derived **only** from that FILE's final path component.

| Field | Type | Derivation |
|---|---|---|
| name | `str` | `os.path.basename(FILE)` |
| path | `str` | `os.path.join(out_dir, name)` |
| stream | text file object | `os.open(...)` + `io` wrapper, see below |

### Derivation and validation order (SR-005, SR-006, SR-008)

| Step | Check | On failure |
|---|---|---|
| 1 | `name = os.path.basename(FILE)` — directory components, `..` segments, and an absolute root are discarded here | — |
| 2 | `name not in ("", ".", "..")` | diagnostic naming FILE and DIR, exit 2 |
| 3 | `Path(join(dir, name)).resolve().parent == Path(dir).resolve()` | diagnostic naming the path, exit 2 |
| 4 | `lstat(path)`: if it exists and is not a regular file | diagnostic naming the path, exit 2 |
| 5 | `os.open(path, O_WRONLY\|O_CREAT\|O_NOFOLLOW\|O_NONBLOCK, 0o600)` — **no `O_TRUNC`** | diagnostic naming the path, exit 2 |
| 6 | `fstat(fd)` is a regular file | diagnostic, exit 2 |
| 7 | `samestat(fstat(fd), fstat(input_fd))` is **false** | diagnostic naming both paths, exit 2 |
| 8 | `fchmod(fd, 0o600)` | diagnostic, exit 2 |
| 9 | `ftruncate(fd, 0)` — the first destructive act, after every check has passed | diagnostic, exit 2 |

| Property | Rule | Requirement |
|---|---|---|
| encoding | `utf-8` / `errors="surrogateescape"` / `newline=""` — identical to stdout | FR-013 |
| content | exactly that FILE's redacted stream; no terminator added or translated | FR-013, SR-010 |
| replacement | full, by `ftruncate` — never append, no remnant of longer previous content | FR-009 |
| permissions | `0o600` after the run, whether created or replaced | SR-007, SC-007 |
| lifetime | opened after its FILE's input stream, closed before the next FILE is reached | SR-011 |
| close | a failure to write, flush, or close is reported and exits 2 | SR-009, FR-015 |
| duplicates | two FILEs with the same final component both write; the later replaces the earlier | FR-011 |

---

## 7. WrittenTally *(new)*

A single `int`, reported once as text.

| Property | Rule | Requirement |
|---|---|---|
| value | the number of FILE arguments processed — `len(options.files)` | FR-011 |
| repeats | a FILE named twice counts twice; two FILEs sharing a final component count twice | FR-011 |
| rendering | `wrote N files\n`, and `wrote 1 file\n` for exactly one | FR-010, Assumptions |
| stream | standard output, and it is the **only** thing stdout carries in an `--out-dir` run | FR-010, US2-2 |
| timing | after the last output file is closed successfully; before the `--count` summary | FR-010, FR-016 |
| suppression | never written when `--out-dir` is absent, and never on a failing run | FR-010, FR-014, FR-015 |

---

## Cross-entity invariants

Feature 001's invariants `INV-1` – `INV-6` continue to hold unchanged. This feature adds:

| ID | Invariant | Enforced by | Requirement |
|---|---|---|---|
| INV-7 | Matches within a line never overlap and are strictly ordered, across all **four** ranks: a lower rank is only ever offered the sub-slices no higher rank claimed | the stage-3 gap computation in `redact_line` | FR-003 |
| INV-8 | Placeholder text is never re-scanned and never nested; replacement text is inserted literally, never as a substitution template | rebuild from verbatim input slices + literal constants (001 design, unchanged) | FR-003, SR-001 |
| INV-9 | A character of a recognised phone number never reaches the output, and no digit of a *rejected* over-long candidate is removed | whole-span replacement + the `(?![0-9])` boundary | SR-002 |
| INV-10 | Exactly one destination per run; with `--out-dir` no redacted line reaches stdout, and without it nothing is created on disk | the single branch in `main` | FR-007, FR-017, SR-008 |
| INV-11 | Every path the tool opens for writing is a direct child of the resolved DIR, is a regular file, is not reached through a symlink, and is not an input file | OutputFile steps 1–7 | SR-005, SR-006, SR-008 |
| INV-12 | At most one output file is open at any instant | the per-FILE `finally` nesting | SR-011 |
| INV-13 | `wrote N files` and the `--count` summary appear only on a run that read all input and wrote, flushed, and closed all output successfully | every failure path returns before them | FR-010, FR-014, FR-015, FR-016, US4-8 |
| INV-14 | Nothing written to any file, and nothing written to stdout or stderr, contains an unredacted matched value | INV-8 + SR-001 diagnostics name only user-supplied paths | SR-010, SC-012 |
