<!--
SYNC IMPACT REPORT
==================
Version change: (none) → 1.0.0
Rationale: Initial ratification. Prior file held only unfilled template
placeholders; this is the first concrete adoption, hence MAJOR baseline 1.0.0.

Modified principles:
- [PRINCIPLE_1_NAME] → I. Standard Library Only
- [PRINCIPLE_2_NAME] → II. Exact Money Arithmetic
- [PRINCIPLE_3_NAME] → III. Fail Loudly
- [PRINCIPLE_4_NAME] → IV. Every Requirement Is Testable
- [PRINCIPLE_5_NAME] → V. Deterministic Output

Added sections:
- Additional Constraints (was [SECTION_2_NAME])
- Development Workflow & Quality Gates (was [SECTION_3_NAME])
- Governance (populated)

Removed sections: none

Deferred TODOs: none. All placeholders resolved.

Follow-up: This report block is scratch material for amendment review and
should be removed before the constitution is committed.
-->

# SDD Pilot Constitution

## Core Principles

### I. Standard Library Only
The tool MUST run using only the Python standard library at runtime. No
third-party runtime dependency may be added, imported, or required for the
program to execute its core function. Development-only tooling (for example the
`pytest` test runner) is permitted, but it MUST NOT be imported by shipped
runtime code. Rationale: a standard-library-only footprint keeps the tool
portable, auditable, and installable without a dependency resolver, which is
the correct posture for a small, long-lived command-line utility.

### II. Exact Money Arithmetic
All monetary values MUST be represented and computed as integer cents (or the
smallest indivisible currency unit). Floating-point types MUST NOT be used to
hold, accumulate, or compare money. No operation may lose or invent money: the
sum of outputs MUST equal the sum of inputs, and any required rounding or
splitting MUST be explicit, deterministic, and conserve the total to the cent.
Rationale: floats silently introduce representation error; integer-cent
arithmetic guarantees that every cent is accounted for and reconciles exactly.

### III. Fail Loudly
Malformed, ambiguous, or out-of-contract input MUST produce a clear,
human-readable message on stderr and terminate with a non-zero exit code. The
tool MUST NOT emit a silent wrong answer, a partial result, or a best-guess
substitution when input is invalid. Normal successful output goes to stdout;
diagnostics go to stderr. Rationale: a wrong answer that looks correct is worse
than a visible failure, especially for a tool that handles money.

### IV. Every Requirement Is Testable
Every functional requirement MUST map to at least one automated `pytest` test
that can pass or fail objectively. A requirement that cannot be expressed as an
executable test MUST be rewritten until it can be, or removed. Requirements
phrased as vague qualities ("fast", "user-friendly") are not acceptable without
a measurable, testable criterion. Rationale: untestable requirements cannot be
verified or defended against regression; testability keeps the specification
honest.

### V. Deterministic Output
Given identical input and invocation, the tool MUST produce byte-identical
output. Output MUST NOT depend on wall-clock time, random seeds, hash-ordering,
locale, environment ordering, or any other non-deterministic source unless that
input is passed in explicitly and fixed by the caller. Collections that feed
output MUST be ordered deterministically. Rationale: deterministic output makes
results reproducible, diffable, and testable by exact comparison.

## Additional Constraints

- Language & runtime: Python 3, standard library only for runtime code
  (see Principle I).
- Interface: command-line. Input arrives via stdin and/or arguments; successful
  results go to stdout; all diagnostics and errors go to stderr (see
  Principle III).
- Money representation: integer cents end to end; formatting to a
  human-readable currency string happens only at the output boundary and MUST
  NOT reintroduce floats (see Principle II).
- No network access, hidden state, or reliance on ambient environment for
  computed results; anything that affects output MUST be an explicit input
  (see Principle V).

## Development Workflow & Quality Gates

- Test-backed changes: each functional requirement MUST land with at least one
  `pytest` test; changes without corresponding tests do not satisfy Principle
  IV and MUST NOT be merged.
- Passing suite: the full `pytest` suite MUST pass before merge. Determinism is
  enforced by tests that assert exact output (see Principle V).
- Error-path coverage: malformed-input handling MUST be exercised by tests that
  assert both the stderr message and the non-zero exit code (see Principle III).
- Money invariants: tests MUST include conservation checks proving that no
  operation loses or invents money (see Principle II).
- Review: every change MUST be reviewed for compliance with all five core
  principles before merge.

## Governance

This constitution supersedes other development practices for this project. When
a practice conflicts with a principle here, the principle governs.

Amendments MUST be proposed as a documented change to this file, reviewed and
approved, and accompanied by any migration notes needed for existing code.
Versioning follows semantic versioning:
- MAJOR: backward-incompatible governance changes, principle removals, or
  redefinitions.
- MINOR: a new principle or section, or materially expanded guidance.
- PATCH: clarifications, wording, or non-semantic refinements.

Compliance review: every pull request and review MUST verify adherence to the
five core principles. Any deviation MUST be justified in writing and either
corrected or explicitly ratified as an amendment; unjustified complexity MUST
be removed.

**Version**: 1.0.0 | **Ratified**: 2026-09-17 | **Last Amended**: 2026-09-17
