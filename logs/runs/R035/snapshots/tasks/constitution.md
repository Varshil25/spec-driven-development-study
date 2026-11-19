<!--
SYNC IMPACT REPORT (temporary scratch material for amendment review; remove before commit)

Version change: none (unfilled template) → 1.0.0
Rationale: Initial ratification. The prior file was the unpopulated core scaffold with no
project-specific values, so there is nothing to supersede and no backward-incompatible change.

Modified principles:
- [PRINCIPLE_1_NAME] (placeholder) → I. Standard Library Only
- [PRINCIPLE_2_NAME] (placeholder) → II. Fail Loudly
- [PRINCIPLE_3_NAME] (placeholder) → III. Every Requirement Is Testable
- [PRINCIPLE_4_NAME] (placeholder) → IV. Simplicity

Added sections:
- Core Principles (4 principles, populated)
- Additional Constraints (was [SECTION_2_NAME])
- Development Workflow and Quality Gates (was [SECTION_3_NAME])
- Governance (populated)

Removed sections:
- [PRINCIPLE_5_NAME] / [PRINCIPLE_5_DESCRIPTION] — the scaffold carries five principle slots;
  the ratified set defines four, as specified. No fifth principle was invented to fill the slot.

Follow-up TODOs:
- TODO(PROJECT_NAME): No project name is discoverable in the repository (no README, no package
  metadata, and `origin` points at a local path). The document is titled "Project Constitution";
  rename the heading once the project has a name. This is cosmetic and blocks nothing.
-->

# Project Constitution

## Core Principles

### I. Standard Library Only

The shipped product MUST run on a stock CPython interpreter with zero third-party packages
installed. Runtime code MUST NOT import any module outside the Python standard library.
Development and test tooling (notably `pytest`, required by Principle III) is exempt and MUST be
declared separately from runtime requirements so the distinction stays visible. Any proposal to
add a runtime dependency MUST be rejected or escalated as a constitutional amendment; "it is only
one small package" is not an exception.

Rationale: a stdlib-only runtime installs anywhere Python exists, has no supply-chain or version
drift surface, and keeps the project's total complexity bounded by code we actually own.

### II. Fail Loudly

Invalid input, unmet preconditions, and unreachable states MUST produce a clear, specific
diagnostic naming what was wrong and what was expected. Failures MUST be observable:
command-line entry points exit with a non-zero status and write diagnostics to stderr; library
and service surfaces raise an exception or return an explicit error response. Silent fallbacks,
bare `except:` blocks that swallow errors, defaulted-away bad input, and partially-written output
that looks successful are all forbidden. A wrong answer delivered without complaint is the worst
possible outcome and MUST NOT be a reachable state.

Rationale: a loud failure costs one minute of a user's time; a silent wrong answer propagates
into decisions and is often discovered only long after the damage is done.

### III. Every Requirement Is Testable

Every functional requirement in a specification MUST map to at least one automated `pytest` test
that fails when the requirement is unmet. Requirements that cannot be expressed as an executable
check MUST be rewritten until they can be, or dropped from the specification. The mapping from
requirement to covering test MUST be explicit and traceable — by requirement ID in the test name,
docstring, or marker — so coverage of the specification can be audited rather than assumed.
Error paths required by Principle II are themselves requirements and MUST carry tests asserting
both the diagnostic and the non-zero exit status or error response.

Rationale: an untestable requirement is an opinion, not a commitment; traceability is what makes
"the spec is implemented" a verifiable claim instead of a hopeful one.

### IV. Simplicity

The implementation MUST be the smallest design that satisfies the specification. Abstractions,
configuration options, plugin seams, caching layers, and generalizations MUST NOT be added for
anticipated future needs — YAGNI is binding. Where two designs both meet the specification, the
one with fewer moving parts, fewer files, and less indirection MUST be chosen. Any deviation MUST
be justified in the plan against a specific stated requirement, not against a hypothetical one.

Rationale: unused flexibility is pure cost — it must be read, tested, and maintained forever while
earning nothing, and it obscures the code that does real work.

## Additional Constraints

- **Language and runtime**: Python 3. The minimum supported version MUST be stated once in project
  metadata, and code MUST NOT use syntax or stdlib APIs newer than that floor.
- **Dependency manifest**: runtime requirements MUST remain empty. Test and development tooling
  MUST be listed in a clearly separate group.
- **Test framework**: `pytest` is the single sanctioned test runner, per Principle III.
- **Interfaces**: command-line surfaces follow the text protocol — input via arguments or stdin,
  results to stdout, diagnostics to stderr, status code conveying success or failure.
- **No hidden state**: behaviour MUST NOT depend on undeclared environment variables, network
  access, or files outside paths the caller supplied.

## Development Workflow and Quality Gates

1. **Specify**: functional requirements are written in testable form, each individually
   identifiable, before implementation begins.
2. **Plan**: the design is checked against all four principles. Any added dependency, any silent
   error path, any untestable requirement, or any unjustified abstraction is resolved at this
   stage, not later.
3. **Implement**: code and its covering tests land together. A requirement is not complete until
   its test exists and passes.
4. **Gate**: the full `pytest` suite MUST pass before any change is considered done. A change that
   leaves a specified requirement without a covering test, or that introduces a runtime import
   outside the standard library, MUST NOT be merged.
5. **Review**: reviewers verify principle compliance explicitly — stdlib-only imports, loud and
   tested failure paths, requirement-to-test traceability, and absence of speculative structure.

## Governance

This constitution supersedes all other development practices, conventions, and preferences in this
project. Where guidance conflicts, this document wins.

**Amendment procedure**: amendments MUST be proposed as an edit to this file, MUST state the
rationale and the version bump with its justification, and MUST describe any migration required
for code that the change would render non-compliant. An amendment takes effect only once it is
recorded here with an updated version line and amendment date.

**Versioning policy**: this document is versioned as MAJOR.MINOR.PATCH.
- MAJOR: a principle is removed or redefined in a way that invalidates previously compliant work.
- MINOR: a principle or governed section is added, or existing guidance is materially expanded.
- PATCH: clarifications, wording, and typo fixes that do not change what is required.

**Compliance review**: every change under review is checked against the Core Principles, and the
quality gate above is a hard precondition for merge. Complexity MUST be justified against a stated
requirement or removed. Violations are fixed or explicitly amended into this document — they are
never left as undocumented exceptions.

**Version**: 1.0.0 | **Ratified**: 2026-11-19 | **Last Amended**: 2026-11-19
