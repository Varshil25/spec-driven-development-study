<!--
SYNC IMPACT REPORT (scratch material for amendment review; remove before committing)

Version change: [CONSTITUTION_VERSION] (unfilled template) → 1.0.0
Bump rationale: Initial ratification. The previous file was an unpopulated scaffold with no
governance in force, so this is the first concrete version rather than an amendment.

Modified principles:
- [PRINCIPLE_1_NAME] → I. Standard Library Only (NON-NEGOTIABLE)
- [PRINCIPLE_2_NAME] → II. Fail Loudly
- [PRINCIPLE_3_NAME] → III. Every Requirement Is Testable
- [PRINCIPLE_4_NAME] → IV. Simplicity
- [PRINCIPLE_5_NAME] → removed (user specified exactly four principles)

Added sections:
- Additional Constraints (was [SECTION_2_NAME])
- Development Workflow & Quality Gates (was [SECTION_3_NAME])
- Governance rules populated (was [GOVERNANCE_RULES])

Removed sections:
- Fifth principle slot, dropped to match the four principles supplied.

Follow-up TODOs:
- None. PROJECT_NAME was inferred generically ("Python Project") because the repository
  contains no README or packaging metadata declaring a name; rename on first amendment if a
  product name is chosen.
-->

# Python Project Constitution

## Core Principles

### I. Standard Library Only (NON-NEGOTIABLE)

Runtime code MUST import only the Python standard library. No third-party package may be a
runtime dependency, and the shipped project MUST run on a bare CPython installation of the
supported version with no install step beyond obtaining the source.

Test and development tooling is the single exception: `pytest` MAY be used as a
development-only dependency (see Principle III). Code under test MUST NOT import `pytest` or
any other development tool, so removing the dev environment never changes runtime behavior.

Rationale: a dependency-free project is installable anywhere, cannot break from upstream
releases or yanked versions, and has no supply-chain surface. At this project's size, the
convenience a library buys rarely exceeds that cost.

### II. Fail Loudly

Invalid input, unmet preconditions, and unreachable states MUST produce a clear, specific
diagnostic naming what was wrong and what was expected. Failures MUST be observable:

- Command-line entry points MUST write the diagnostic to stderr and exit non-zero.
- Library and API surfaces MUST raise an exception or return an explicit error result.
- Bare `except:` and `except Exception: pass` are forbidden. Catching an exception is
  permitted only to re-raise, to wrap it with added context, or to convert it into an
  explicit error result.
- Silent fallbacks, coerced defaults that mask bad input, and partial results returned as if
  complete are forbidden.

A silent wrong answer is the worst possible outcome and MUST never be a code path.

Rationale: a loud failure costs one debugging session; a quiet wrong answer costs trust in
every result the project has ever produced.

### III. Every Requirement Is Testable

Every functional requirement in a specification MUST map to at least one automated `pytest`
test, and that mapping MUST be explicit — the test name or docstring names the requirement
it covers.

- A requirement that cannot be expressed as a test is not yet specified; it MUST be rewritten
  until it can be, or dropped.
- Error paths required by Principle II MUST be tested, not only success paths.
- The full suite MUST pass before any change is considered complete.

Rationale: an untestable requirement cannot be verified or defended against regression, so it
is an intention rather than a requirement.

### IV. Simplicity

Implementations MUST be the smallest design that satisfies the specification.

- Build only what a current requirement demands. Speculative extension points,
  configurability, and abstraction layers added for anticipated future needs are forbidden.
- Prefer functions and plain data (`dict`, `list`, `dataclass`) over class hierarchies;
  prefer one module over several until a concrete reason to split appears.
- Any structure beyond the obvious solution MUST be justified in the plan by the requirement
  that forces it. "It is more flexible" is not a justification.

Rationale: every unneeded element must be read, tested, and maintained forever, and complexity
added for imagined futures is usually wrong about them.

## Additional Constraints

- **Language**: Python 3.11 or newer; code MUST NOT rely on features unavailable in the
  declared minimum version.
- **Dependencies**: runtime imports from the standard library only (Principle I). The only
  permitted development dependency is `pytest`; adding any other requires an amendment.
- **Structure**: source and tests live in the repository under clearly separated directories,
  with tests discoverable by `pytest` from the repository root without configuration beyond a
  single config file.
- **Interfaces**: command-line tools follow the stdin/args → stdout convention, with
  diagnostics on stderr and meaningful exit codes (0 success, non-zero failure).
- **No hidden state**: no implicit global mutable state, no network calls, and no writes
  outside paths the caller supplied.

## Development Workflow & Quality Gates

1. **Specify**: write or update the specification; each functional requirement is stated so a
   test could falsify it (Principle III).
2. **Plan**: record the chosen design and justify any complexity against the requirement
   forcing it (Principle IV). A plan that introduces a third-party runtime dependency is
   rejected unless accompanied by a constitution amendment.
3. **Implement with tests**: write tests covering each requirement, including its error
   behavior, alongside the implementation.
4. **Gate before completion**, all of which MUST hold:
   - `pytest` passes with no skipped tests covering in-scope requirements.
   - No runtime module imports a non-standard-library package.
   - Every functional requirement has an identifiable covering test.
   - No swallowed exceptions or silent fallbacks introduced.
5. **Review**: every change is checked against these four principles. A violation blocks the
   change until the code is fixed or the constitution is amended.

## Governance

This constitution supersedes all other development practices for this project. Where a
convention, tool default, or reviewer preference conflicts with it, this document wins.

**Amendment procedure**: amendments MUST be proposed as an edit to this file stating the
principle changed, the rationale, and the migration required for existing code. An amendment
takes effect only once this file is updated and the version and dates below are bumped. Code
that violates a newly adopted principle MUST be brought into compliance or listed in the
amendment as an accepted, time-bounded exception.

**Versioning policy**: semantic versioning applies to this document.

- MAJOR: a principle is removed or redefined in a backward-incompatible way.
- MINOR: a principle or section is added, or guidance is materially expanded.
- PATCH: clarifications, wording, and typo fixes with no change in obligation.

**Compliance review**: every change under review MUST be verified against the four principles
using the quality gates above. Violations are fixed, not waived; a persistent exception
requires an amendment that records it explicitly.

**Version**: 1.0.0 | **Ratified**: 2026-11-14 | **Last Amended**: 2026-11-14
