<!--
SYNC IMPACT REPORT (temporary scratch material for amendment review; remove before commit)

Version change: [CONSTITUTION_VERSION] (unfilled template) → 1.0.0

Rationale: Initial ratification. The previous file was the unpopulated scaffold with no
concrete governance content, so this is the first real adoption rather than an amendment.
MAJOR bump to 1.0.0 per semantic versioning for a first ratified governance document.

Principles defined (template slot → ratified principle):
- [PRINCIPLE_1_NAME] → I. Standard Library Only
- [PRINCIPLE_2_NAME] → II. Fail Loudly
- [PRINCIPLE_3_NAME] → III. Every Requirement Is Testable
- [PRINCIPLE_4_NAME] → IV. Simplicity
- [PRINCIPLE_5_NAME] → REMOVED (user specified exactly four principles)

Added sections:
- Core Principles (4 principles)
- Technology Constraints (was [SECTION_2_NAME])
- Development Workflow & Quality Gates (was [SECTION_3_NAME])
- Governance

Removed sections:
- Fifth principle slot, removed because the ratified principle set is exactly four.

Follow-up TODOs:
- TODO(PROJECT_NAME): No project name was supplied and none could be inferred from the
  repository (no README, no package metadata, no remote project name). The document uses the
  placeholder title "Python Project Constitution". Replace the title when the project is named.
-->

# Python Project Constitution

## Core Principles

### I. Standard Library Only

The project MUST NOT acquire third-party runtime dependencies. All runtime behavior MUST be
implemented using the Python standard library and the project's own modules. Any import at
runtime MUST resolve to either a stdlib module or a first-party module in this repository.

Development-time and test-time tooling (for example `pytest`) is exempt from this rule, but such
tooling MUST NOT be imported by runtime code paths, and the shipped program MUST run correctly in
an environment where only the standard library is installed.

Rationale: a zero-dependency runtime removes supply-chain exposure, version-pinning churn, and
install friction, which matters more than convenience for a project of this size.

### II. Fail Loudly

Invalid input, unmet preconditions, and unrecoverable states MUST produce a clear, specific
diagnostic message identifying what was wrong. A silent wrong answer is never an acceptable
outcome.

- Command-line entry points MUST write the diagnostic to stderr and exit with a non-zero status.
- Library and API surfaces MUST raise an exception or return an explicit error response; they
  MUST NOT return a default, empty, or partial result in place of signalling failure.
- Exceptions MUST NOT be swallowed. A bare `except:` or an `except Exception: pass` that hides a
  failure from the caller is prohibited.
- Error messages MUST name the offending value or condition. "Invalid input" alone is
  insufficient.

Rationale: a wrong answer that looks right is the most expensive defect class, because it
propagates downstream before anyone notices. Loud failure converts that into an immediate,
localized, cheap-to-fix signal.

### III. Every Requirement Is Testable

Each functional requirement in a specification MUST map to at least one automated `pytest` test
that fails when the requirement is unmet. A requirement that cannot be expressed as an automated
test MUST be rewritten until it can be, or removed from the specification.

- Requirements MUST be stated in observable terms: given an input or state, an asserted output,
  error, or exit status.
- The mapping from requirement to covering test MUST be traceable, by test name, docstring, or an
  explicit requirement identifier in the test.
- Error paths from Principle II are requirements and MUST be covered: tests MUST assert the
  diagnostic and the non-zero exit status or raised error, not merely that something failed.
- The full `pytest` suite MUST pass before any change is considered complete.

Rationale: an untestable requirement cannot be verified or defended against regression, so it is
an intention rather than a commitment. Forcing testability at specification time is what makes
later verification mechanical instead of a matter of opinion.

### IV. Simplicity

The implementation MUST be the smallest design that satisfies the specification. Scope is bounded
by the specification; anything beyond it is out of scope until specified.

- Speculative generality is prohibited: no abstraction, configuration hook, plugin seam, or
  extension point without a current specified requirement that needs it.
- Prefer a function to a class, a module to a package, and a plain data structure to a custom
  type, unless the specification demands otherwise.
- When two designs both satisfy the specification, the one with fewer moving parts MUST be chosen.
- Any deviation that adds structure beyond the minimum MUST be justified in writing in the plan,
  citing the specific requirement that forces it.

Rationale: in a small project, incidental complexity costs more than the flexibility it buys, and
unused flexibility still has to be read, tested, and maintained.

## Technology Constraints

- Language: Python 3. Runtime code MUST rely only on the standard library (Principle I).
- Test framework: `pytest`. Tests live under a `tests/` directory and are runnable with a bare
  `pytest` invocation from the repository root.
- Packaging MUST NOT introduce runtime dependency declarations. Test-only tooling MUST be
  declared separately from any runtime requirements.
- Command-line programs MUST follow the text protocol: input via arguments or stdin, normal
  output to stdout, diagnostics to stderr, exit status 0 on success and non-zero on failure.

## Development Workflow & Quality Gates

1. Specification first. Functional requirements are written in observable, testable form before
   implementation begins (Principle III).
2. Tests accompany implementation. No functional requirement is marked complete without a
   `pytest` test that covers it, including its error path.
3. Quality gate before completion. All of the following MUST hold:
   - The full `pytest` suite passes.
   - Every functional requirement has at least one covering test, traceable to the requirement.
   - Runtime code imports only stdlib and first-party modules.
   - Every specified invalid-input case produces a clear diagnostic and a non-zero exit status or
     an explicit error response.
   - No structure exists that is not required by the specification, or any such structure is
     justified in writing.
4. Review. Changes are reviewed against the five gate conditions above. A change that fails any
   gate is not merged until the gate passes or the constitution is amended.

## Governance

This constitution supersedes conflicting practices, conventions, and preferences in this project.
Where a plan, specification, or review comment conflicts with a principle here, the principle wins
until the constitution is amended.

**Amendment procedure**: Amendments MUST be proposed as a written change to this file stating the
principle or section affected, the rationale, and the migration impact on existing code, specs,
and tests. An amendment takes effect only once this file is updated and the version and
`Last Amended` date are bumped in the same change.

**Versioning policy**: Semantic versioning applies to this document.

- MAJOR: a principle is removed or redefined in a backward-incompatible way, or governance rules
  change such that previously compliant work becomes non-compliant.
- MINOR: a principle or section is added, or existing guidance is materially expanded.
- PATCH: clarification, wording, or typo fixes that do not change what is required.

**Compliance review**: Every change MUST be checked against the quality gates in
*Development Workflow & Quality Gates* before completion. Complexity beyond the specification MUST
be justified in writing or removed (Principle IV). Violations are fixed, granted a documented and
time-bounded exception, or resolved by amending this constitution — never left silently in place.

**Version**: 1.0.0 | **Ratified**: 2026-11-05 | **Last Amended**: 2026-11-05
