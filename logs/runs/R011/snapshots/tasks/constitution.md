<!--
SYNC IMPACT REPORT (temporary scratch material for amendment review; remove before commit)

Version change: unversioned template → 1.0.0
Rationale: Initial ratification. The previous file was an unfilled scaffold with no
concrete principles, so this is the first governing version (MAJOR baseline).

Modified principles:
- [PRINCIPLE_1_NAME] (placeholder) → I. Standard Library Only
- [PRINCIPLE_2_NAME] (placeholder) → II. Fail Loudly
- [PRINCIPLE_3_NAME] (placeholder) → III. Every Requirement Is Testable
- [PRINCIPLE_4_NAME] (placeholder) → IV. Simplicity
- [PRINCIPLE_5_NAME] (placeholder) → REMOVED (user specified exactly four principles)

Added sections:
- Additional Constraints (was [SECTION_2_NAME])
- Development Workflow & Quality Gates (was [SECTION_3_NAME])
- Governance rules, versioning policy, compliance review

Removed sections:
- Fifth principle slot (not required by the specified four-principle set)

Deferred TODOs:
- TODO(PROJECT_NAME): The repository has no README, package metadata, or declared
  project name. The generic title "Python Project" is a placeholder; rename the
  document title once the project has an official name. This is a PATCH-level edit.
-->

# Python Project Constitution

## Core Principles

### I. Standard Library Only

The runtime MUST depend only on the Python standard library. No third-party package may be
imported by shipped code, and the project MUST remain installable and runnable on a bare
Python interpreter with no `pip install` step. `pytest` is permitted as a development and
test-time dependency only; it MUST NOT be imported by any module outside the test suite.
Any proposal to add a runtime dependency MUST be rejected or escalated as a constitutional
amendment, never adopted silently.

Rationale: A zero-dependency runtime removes installation friction, supply-chain exposure,
and version-conflict maintenance for a project of this size.

### II. Fail Loudly

Invalid, malformed, or out-of-range input MUST produce a clear, specific diagnostic message
and a failure signal: a non-zero exit status for command-line entry points, or an explicit
error response or raised exception for library and service interfaces. Code MUST NOT return a
plausible-looking result derived from input it could not validate. Broad exception handlers
that swallow errors are prohibited; `except` clauses MUST be narrow and MUST either recover
meaningfully or re-raise. Diagnostics MUST name what was wrong and which input caused it.

Rationale: A silent wrong answer is the most expensive failure mode, because it is
indistinguishable from a correct one until it has already caused harm downstream.

### III. Every Requirement Is Testable

Every functional requirement in a specification MUST map to at least one automated `pytest`
test that fails when the requirement is unmet. Requirements MUST be written so that such a
test can be expressed; a requirement that cannot be tested automatically MUST be rewritten or
dropped before implementation begins. Each error path required by Principle II MUST have its
own test asserting both the failure signal and the diagnostic. The full suite MUST pass before
any change is considered complete.

Rationale: An untestable requirement cannot be verified or defended against regression, so it
is not a requirement — it is an aspiration.

### IV. Simplicity

Implementations MUST be the smallest design that satisfies the specification. Abstractions,
configuration options, indirection layers, and extension points MUST NOT be added for
anticipated future needs; they are added when a current requirement demands them. Where two
designs both meet the specification, the one with fewer moving parts MUST be chosen. Any
deviation MUST be justified in the plan against a specific stated requirement.

Rationale: Unused flexibility is pure cost — it must be read, tested, and maintained while
delivering nothing the specification asked for.

## Additional Constraints

- **Language and runtime**: Python 3. The minimum supported version MUST be stated in the
  project's plan and MUST NOT be raised without a recorded reason.
- **Test framework**: `pytest` is the single test framework. Tests live under a `tests/`
  directory and are runnable with a bare `pytest` invocation from the repository root.
- **Interfaces**: Command-line entry points follow a text in/out contract — results to
  `stdout`, diagnostics to `stderr`, exit status `0` on success and non-zero on failure.
- **No hidden state**: Behaviour MUST be determined by explicit inputs. Dependence on
  ambient environment state is permitted only where a requirement names it.

## Development Workflow & Quality Gates

1. **Specify** — Functional requirements are written in testable form (Principle III) before
   implementation.
2. **Plan** — The plan states the minimal design (Principle IV) and confirms no runtime
   dependency is introduced (Principle I).
3. **Implement** — Code and its tests land together. Error paths are implemented with explicit
   diagnostics and failure signals (Principle II).
4. **Gate** — A change MUST NOT be merged unless all of the following hold:
   - `pytest` passes in full.
   - Every new or changed functional requirement has at least one covering test.
   - No third-party runtime import was added.
   - Every new failure mode produces a diagnostic and a non-zero exit status or error response.
   - Added complexity is justified against a stated requirement, or removed.

## Governance

This constitution supersedes all other development practices, conventions, and preferences for
this project. Where other guidance conflicts with it, this document wins.

**Amendment procedure**: Amendments MUST be proposed as an explicit edit to this file,
accompanied by the rationale for the change and, where the change invalidates existing code or
specifications, a migration note describing what must be brought into compliance. Amendments
take effect when merged.

**Versioning policy**: This document is versioned as MAJOR.MINOR.PATCH.
- MAJOR — a principle is removed or redefined in a backward-incompatible way, or governance
  rules change incompatibly.
- MINOR — a principle or section is added, or existing guidance is materially expanded.
- PATCH — clarifications, wording, and non-semantic refinements.

**Compliance review**: Every review MUST verify the quality gates above. Reviewers MUST reject
changes that violate a principle rather than granting one-off exceptions; a principle that
genuinely needs an exception needs an amendment instead. Agent-specific operational guidance
lives in `.claude/` and MUST remain consistent with this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-11-13 | **Last Amended**: 2026-11-13
