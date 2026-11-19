<!--
SYNC IMPACT REPORT (temporary scratch material for amendment review; remove before commit)

Version change: (unfilled template, no prior version) → 1.0.0
Bump rationale: MAJOR/initial — first ratification of a concrete constitution. The previous
file content was the unreplaced scaffold with no governance in force, so this establishes
the baseline rather than amending it.

Principle count: template ships 5 principle slots; user specified 4. Reduced to 4 as instructed.

Modified principles (template slot → ratified principle):
- [PRINCIPLE_1_NAME] → I. Standard Library Only
- [PRINCIPLE_2_NAME] → II. Fail Loudly
- [PRINCIPLE_3_NAME] → III. Every Requirement Is Testable
- [PRINCIPLE_4_NAME] → IV. Simplicity
- [PRINCIPLE_5_NAME] → (removed; unused slot)

Added sections:
- Additional Constraints (resolves the stdlib-only vs. pytest tension; Python baseline)
- Development Workflow & Quality Gates
- Governance (amendment procedure, versioning policy, compliance review)

Removed sections:
- Fifth principle slot [PRINCIPLE_5_NAME] / [PRINCIPLE_5_DESCRIPTION]

Follow-up TODOs:
- TODO(PROJECT_NAME): The project has no README, package metadata, or specified feature yet.
  The title below is derived from the repository directory name (R009). Replace it with the
  real project name once the first feature is specified via /speckit-specify.
- TODO(RATIFICATION_DATE): Recorded as 2026-11-11, the date this constitution was first
  filled in. If the project was adopted earlier, correct this to the true adoption date.
-->

# R009 Constitution

## Core Principles

### I. Standard Library Only

The runtime code MUST depend only on the Python standard library. No third-party package may be
imported by any module that executes in production or in normal user-facing operation. There MUST
be no runtime dependency declarations (no `install_requires`, no non-empty `dependencies` table,
no runtime `requirements.txt` entries). A new third-party runtime dependency MUST NOT be added by
a pull request; it requires a constitution amendment first.

Rationale: a stdlib-only runtime installs and runs anywhere Python runs, has no supply-chain
surface, and never breaks because of an upstream release. For a small project the cost of
re-implementing a thin helper is lower than the cost of carrying a dependency.

### II. Fail Loudly

Invalid input, unmet preconditions, and unreachable states MUST produce an explicit, human-readable
error that names what was wrong and MUST surface as a failure signal: a non-zero exit status for
command-line entry points, or an error response/raised exception for library and service entry
points. Returning a plausible-but-wrong value, silently coercing invalid input, substituting a
default for a malformed required field, and swallowing an exception with a bare `except`/`pass` are
all prohibited. Error messages MUST go to stderr for CLI paths and MUST NOT be the sole content of
stdout on a successful run.

Rationale: a silent wrong answer is the most expensive defect class — it propagates and is
discovered late, far from its cause. A loud failure is cheap to diagnose.

### III. Every Requirement Is Testable

Every functional requirement in a specification MUST map to at least one automated `pytest` test,
and that mapping MUST be explicit (the test name or a comment references the requirement
identifier). A requirement that cannot be expressed as an automated test MUST be rewritten until it
can be, or removed from the specification. A feature MUST NOT be marked complete while any of its
functional requirements has no covering test. Each error path required by Principle II MUST have a
test asserting both the message content and the failure signal.

Rationale: an untestable requirement is an unverifiable claim. Requiring the mapping up front
forces specifications to be concrete and keeps the test suite an accurate inventory of behavior.

### IV. Simplicity

The design MUST be the smallest one that satisfies the specification. Abstractions, configuration
options, extension points, and layers of indirection MUST NOT be introduced for anticipated future
needs; they are added when a current requirement demands them. Where two designs both meet the
specification, the one with fewer modules, fewer public functions, and less state MUST be chosen.
Any deviation — an added layer, a generalization beyond the stated requirements — MUST be justified
in the plan against the specific requirement that forces it.

Rationale: speculative generality is the dominant source of accidental complexity in small
projects, and complexity added for a hypothetical requirement is rarely a fit when the real
requirement arrives.

## Additional Constraints

- **Language baseline**: Python 3 only, using a version currently receiving upstream security
  support. No compiled extensions, no code generation step.
- **Test tooling exemption**: `pytest` is the mandated test runner under Principle III and is a
  development-time dependency. Principle I governs runtime code only. Development and test
  dependencies MUST be declared separately from runtime dependencies and MUST NOT be importable
  from any runtime module. The exemption is narrow: `pytest` and the standard library. Adding any
  other development dependency requires the same amendment process as a runtime dependency.
- **Project layout**: source and tests live in separate directories. Tests MUST be runnable with a
  bare `pytest` invocation from the repository root with no environment setup beyond installing the
  test dependencies.
- **No hidden I/O**: modules MUST NOT perform network access, write outside explicitly provided
  paths, or read ambient configuration that is not named in the specification.

## Development Workflow & Quality Gates

1. **Specify before building.** A feature begins with a specification whose functional requirements
   are individually identified so Principle III's mapping is possible.
2. **Plan declares compliance.** The implementation plan MUST state, explicitly: which standard
   library modules it uses (Principle I), which inputs are validated and how each failure is
   signalled (Principle II), the requirement-to-test mapping (Principle III), and a justification
   for any abstraction beyond the minimum (Principle IV).
3. **Gate on the suite.** `pytest` MUST pass with zero failures before a change is considered
   complete. A change that leaves a test skipped MUST record why in the skip reason.
4. **Gate on dependencies.** Any diff that adds an import of a non-stdlib module to runtime code,
   or adds a runtime dependency declaration, MUST be rejected absent a prior amendment.
5. **Review verifies the four principles by name.** A review that does not check all four has not
   been completed.

## Governance

This constitution supersedes all other development practices, conventions, and preferences in this
project. Where a tool default, template, or habit conflicts with a principle above, the principle
wins.

**Amendment procedure**: amendments are made by updating this file and no other way — a principle
is not relaxed by an exception granted in a plan, a pull request, or a code comment. An amendment
MUST state the principle changed, the rationale, and the migration consequence for existing code.
Amendments take effect on merge and apply to all subsequent work; existing code that violates a new
principle MUST either be brought into compliance or recorded as a known deviation with a remediation
owner.

**Versioning policy**: this constitution is versioned MAJOR.MINOR.PATCH.

- MAJOR: a principle is removed, or redefined in a way that permits what it previously forbade (or
  forbids what it previously permitted).
- MINOR: a principle or governed section is added, or existing guidance is materially expanded.
- PATCH: clarification, wording, or typographical change that does not alter what is required.

**Compliance review**: every pull request MUST verify compliance with all four principles, per the
Development Workflow gates above. Complexity MUST be justified against a stated requirement, not
against convenience. Violations found after merge MUST be filed and fixed; they MUST NOT be
normalized by precedent. Spec Kit commands read this constitution at runtime and MUST treat it as
binding input to specification, planning, and task generation.

**Version**: 1.0.0 | **Ratified**: 2026-11-11 | **Last Amended**: 2026-11-11
