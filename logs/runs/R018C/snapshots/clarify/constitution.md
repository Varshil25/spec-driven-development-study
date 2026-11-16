<!--
Sync Impact Report (temporary scratch material for amendment review; remove before commit)

Version change: [CONSTITUTION_VERSION] (unfilled template) → 1.0.0
Bump rationale: Initial ratification. The prior file was an unpopulated scaffold with no
defined principles, so this is the first governing version rather than an amendment.

Modified principles:
  - [PRINCIPLE_1_NAME] → I. Standard Library Only
  - [PRINCIPLE_2_NAME] → II. Fail Loudly
  - [PRINCIPLE_3_NAME] → III. Every Requirement Is Testable (NON-NEGOTIABLE)
  - [PRINCIPLE_4_NAME] → IV. Simplicity
  - [PRINCIPLE_5_NAME] → (removed; user specified exactly four principles)

Added sections:
  - Additional Constraints (replaces [SECTION_2_NAME])
  - Development Workflow & Quality Gates (replaces [SECTION_3_NAME])

Removed sections:
  - Principle 5 slot, removed because the user specified exactly four principles.

Follow-up TODOs:
  - TODO(PROJECT_NAME): The project name was inferred from the repository directory (R018).
    No README, package metadata, or remote name supplied a product name. Replace "R018" in the
    title with the real project name when it is chosen; this is a PATCH-level edit.
-->

# R018 Constitution

## Core Principles

### I. Standard Library Only

The runtime MUST depend only on the Python standard library. No third-party package may be
imported by any module that ships as part of the product. Adding a runtime dependency requires
a constitution amendment, not a code review approval.

Test and development tooling (for example pytest) is exempt from this rule, but MUST NOT be
imported by runtime code. A module that cannot be executed with a bare Python interpreter
violates this principle.

**Rationale**: A standard-library-only runtime installs anywhere Python exists, has no supply
chain to audit, and cannot break because of an upstream release.

### II. Fail Loudly

Invalid input MUST produce a clear, specific diagnostic message and a failure signal. A silent
wrong answer is a defect of the highest severity, outranking crashes.

- CLI entry points MUST write the diagnostic to stderr and exit with a non-zero status.
- Library and API entry points MUST raise an exception or return an explicit error result.
- Diagnostics MUST name what was invalid and what was expected. "Error" or "invalid input"
  alone is insufficient.
- Code MUST NOT substitute a default, coerce, truncate, or skip a bad record in order to keep
  running, unless the specification explicitly requires that recovery behavior.
- Broad exception handlers MUST NOT swallow errors. Catching an exception is permitted only to
  re-raise it or to convert it into a clearer diagnostic.

**Rationale**: A loud failure costs one debugging session. A silent wrong answer propagates into
downstream decisions and may never be detected.

### III. Every Requirement Is Testable (NON-NEGOTIABLE)

Every functional requirement in a specification MUST map to at least one automated pytest test,
and that mapping MUST be explicit — the test name or a comment identifies the requirement it
covers.

- A requirement that cannot be expressed as an automated test MUST be rewritten until it can be,
  or removed from the specification.
- Error paths required by Principle II are themselves requirements and MUST carry tests that
  assert the message content and the exit status or raised exception type.
- The test suite MUST pass before any change is considered complete.
- A requirement with no corresponding test is treated as unimplemented, regardless of the state
  of the code.

**Rationale**: An untested requirement is an opinion about the code, not a fact about it. Explicit
mapping makes coverage gaps visible instead of assumed.

### IV. Simplicity

The implementation MUST be the smallest design that satisfies the specification. Scope beyond the
specification is a defect, not a bonus.

- Build only what a current requirement demands. Speculative generality, unused parameters,
  unreached branches, and extension points without a caller MUST NOT be added.
- Prefer functions and plain data structures. Introduce a class, an abstraction layer, or a
  design pattern only when a concrete requirement cannot be met without it.
- Prefer a flat module layout. Add packages and subpackages only when module count makes a flat
  layout genuinely unnavigable.
- When two designs both satisfy the specification, the one with fewer moving parts wins.
- Any deviation MUST be justified in writing against a specific requirement during review.

**Rationale**: Every line of code is maintained, read, and debugged forever. The cheapest code is
the code that was never written.

## Additional Constraints

- **Language**: Python 3. The minimum supported version MUST be declared once in the project
  and honored by all code; syntax and library features newer than that version are prohibited.
- **Test framework**: pytest. It is the single permitted development dependency category
  alongside the interpreter itself.
- **Interfaces**: Command-line entry points follow the convention that results go to stdout and
  diagnostics go to stderr, so that output remains machine-consumable under Principle II.
- **Configuration**: Behavior is driven by explicit arguments and documented inputs. Hidden
  global state and implicit environment-based behavior switches MUST NOT be introduced.

## Development Workflow & Quality Gates

A change is complete only when all of the following hold:

1. **Specification traceability** — Every functional requirement the change addresses has at
   least one automated pytest test, per Principle III.
2. **Suite green** — The full pytest suite passes locally before the change is submitted.
3. **Dependency check** — No new third-party import appears in runtime code, per Principle I.
4. **Failure-path check** — Every new input boundary has a test asserting a clear message and a
   non-zero exit status or raised error, per Principle II.
5. **Simplicity review** — The reviewer confirms no code exists that no requirement demands, per
   Principle IV. Unjustified complexity is grounds for rejection on its own.

Gates 1 through 4 are objectively verifiable and MUST NOT be waived. Gate 5 is a judgment call
resolved by the amendment process when reviewer and author disagree.

## Governance

This constitution supersedes all other development practices, conventions, and preferences in
this project. Where a style guide, tool default, or habit conflicts with a principle here, the
principle wins.

**Amendment procedure**: Amendments MUST be proposed as a written change to this file stating
the principle affected, the rationale, and the migration impact on existing code. An amendment
takes effect when it is merged. Code that an amendment renders non-compliant MUST be brought
into compliance or explicitly grandfathered in the amendment text.

**Versioning policy**: This document is versioned with semantic versioning.

- **MAJOR** — A principle is removed or redefined in a way that invalidates previously compliant
  code or governance.
- **MINOR** — A principle or section is added, or existing guidance is materially expanded.
- **PATCH** — Clarifications, wording, and typo fixes that do not change what is required.

**Compliance review**: Every review MUST verify the change against the five quality gates above.
Violations block the change. A reviewer who approves a change that violates a principle shares
responsibility for the violation. Compliance is a property of the delivered code, not of the
author's intent.

**Version**: 1.0.0 | **Ratified**: 2026-11-16 | **Last Amended**: 2026-11-16
