<!--
SYNC IMPACT REPORT (temporary scratch for amendment review — remove before commit)

Version change: [CONSTITUTION_VERSION] (unfilled scaffold) → 1.0.0
Bump rationale: Initial ratification. The previous file was the unpopulated
template with no project-specific values, so there is no prior governance to
supersede; first concrete adoption is 1.0.0 (MINOR/PATCH do not apply).

Modified principles (placeholder → concrete):
  - [PRINCIPLE_1_NAME] → I. Standard Library Only
  - [PRINCIPLE_2_NAME] → II. Fail Loudly
  - [PRINCIPLE_3_NAME] → III. Every Requirement Is Testable
  - [PRINCIPLE_4_NAME] → IV. Simplicity
  - [PRINCIPLE_5_NAME] → V. Secure by Default (NON-NEGOTIABLE)

Added sections (filled from placeholders, heading hierarchy unchanged):
  - [SECTION_2_NAME] → Security Baseline (minimum controls for Principle V)
  - [SECTION_3_NAME] → Development Workflow & Quality Gates
  - Governance → amendment procedure, versioning policy, compliance review

Removed sections: none.

Follow-up TODOs:
  - TODO(PROJECT_NAME): The project has no name yet; the title uses the generic
    "Python Project". Rename the H1 when a name is chosen (PATCH bump).
  - Downstream templates (spec/plan/tasks) are read at runtime and were
    deliberately not modified by this command; confirm the plan template's
    Constitution Check surfaces Principle V's per-feature security
    requirements, and amend those templates separately if it does not.
-->

# Python Project Constitution

## Core Principles

### I. Standard Library Only

The runtime MUST depend only on the Python standard library. No third-party package
may be imported by shipped code, and the project MUST run on a bare `python3`
interpreter with no install step. Development-only tooling (notably `pytest`) is
permitted, but MUST NOT be imported by runtime code paths; if a runtime module
cannot be exercised without a dev-only import, that is a design defect in the
module. Any proposal that requires a runtime dependency MUST instead be solved
with the standard library or dropped from scope.

Rationale: zero-dependency code installs anywhere, cannot break from upstream
releases or yanked versions, and carries no third-party supply-chain risk.

### II. Fail Loudly

Invalid input MUST produce a clear, actionable message naming what was rejected
and why. A command-line entry point MUST exit with a non-zero status; a library
function MUST raise; a service MUST return an error response. Silently returning a
wrong, empty, or partial answer is forbidden. Errors MUST go to stderr (or the
error channel), never be swallowed by a bare `except`, and never be degraded into
a default value that the caller cannot distinguish from a real result. Messages
MUST obey the output restriction in Principle V — clear to the operator, free of
secrets and personal data.

Rationale: a loud failure costs one fix; a silent wrong answer propagates into
downstream data and is found far later, if ever.

### III. Every Requirement Is Testable

Every functional requirement in a specification MUST be written so that it can be
checked mechanically, and MUST map to at least one automated `pytest` test. The
mapping MUST be explicit: requirement identifiers appear in test names or
docstrings so coverage of the specification is auditable, not assumed. A
requirement with no test is unimplemented, regardless of the state of the code. A
requirement that cannot be expressed as a test MUST be rewritten until it can be.
This applies in full to security requirements (Principle V), which are tested like
any other requirement.

Rationale: the test suite, not prose, is the enforceable record of what the
software promises.

### IV. Simplicity

Implementations MUST be the smallest design that satisfies the specification.
Abstraction layers, configuration options, plugin seams, caches, and concurrency
MUST NOT be added until a current requirement demands them. Speculative
generality for anticipated future needs is rejected by default. Where two designs
both meet the specification, the one with fewer moving parts wins; added
complexity MUST be justified in the plan against a specific requirement.
Simplicity MUST NOT be claimed as grounds for omitting a security control from the
Security Baseline — correctness and safety are part of the specification, not
optional extras.

Rationale: the smallest correct design is the cheapest to read, test, and audit,
and it is where defects have the fewest places to hide.

### V. Secure by Default (NON-NEGOTIABLE)

Every specification MUST state the security requirements of each feature, and every
plan MUST state how they are met, using the OWASP Top 10 and the OWASP Application
Security Verification Standard (ASVS) as the reference for what to consider. Each
stated security requirement MUST be testable and MUST have at least one automated
`pytest` test, exactly as Principle III requires of functional requirements. A
feature whose specification is silent on security is incomplete and MUST NOT
proceed to planning. The minimum controls in the Security Baseline below apply to
every feature whether or not the specification repeats them; a feature MUST NOT
weaken them, and a deliberate exception MUST be recorded in the plan with its
rationale and compensating control.

Rationale: security requirements that are not written down are not reviewed, and
requirements that are not tested regress; naming an external standard keeps the
analysis from being limited to whatever the author happened to remember.

## Security Baseline

These are the minimum controls required by Principle V. They are requirements, so
Principle III applies: each one that a feature touches MUST have an automated test.

- **Untrusted input.** Treat every input as untrusted and validate it before use:
  command-line arguments, environment variables, files, archive members, network
  requests and responses, and previously stored data. Validate against an allowed
  shape — type, range, length, and permitted values — and reject what does not
  match rather than attempting to repair it.
- **No string-built interfaces.** Never construct SQL, shell commands, file paths,
  or markup from untrusted input by concatenation or interpolation. Use
  parameterised queries for SQL; pass argument lists without a shell for
  subprocesses; encode output for the exact context it is written into (HTML, URL,
  shell, SQL, log); and resolve file paths against an allowed base directory,
  confirming the fully resolved path stays inside it and refusing to follow
  symbolic links out of it.
- **Credentials and secrets.** Store passwords only as salted, deliberately slow
  hashes. Never keep passwords, tokens, keys, or other secrets in plaintext — not
  in source, configuration committed to the repository, logs, or persisted state.
- **Randomness and comparison.** Generate identifiers, tokens, salts, and nonces
  with a cryptographically secure random generator. Compare secrets, tokens, and
  authentication tags in constant time.
- **Resource limits.** Bound the size of every input and the time and memory any
  single input can consume, including decompressed and recursively nested data.
  Exceeding a limit is an error under Principle II, not a best-effort truncation.
- **Access control.** Check authorisation on every operation, at the point the
  operation is performed rather than only where it is requested, and ensure the
  check still holds under concurrent requests.
- **File permissions.** Create files and directories with the narrowest
  permissions that still work, and set them at creation rather than afterwards.
- **Output hygiene.** Never expose secrets or personal data in program output,
  logs, diagnostics, stack traces, or error messages.

## Development Workflow & Quality Gates

- **Specification first.** Work begins from a specification whose functional and
  security requirements are individually identified and testable (Principles III
  and V). A specification missing security requirements is rejected at review.
- **Plan review.** Every plan MUST include a Constitution Check that states, per
  principle, how the plan complies — in particular which standard-library
  facilities replace any dependency that was considered (I), how invalid input
  fails (II), which tests cover which requirement identifiers (III), what
  complexity was declined and why (IV), and how each Security Baseline control is
  satisfied or deliberately excepted (V).
- **Tests gate merges.** The full `pytest` suite MUST pass before any change
  merges. Tests covering a requirement MUST be present in the same change as the
  code implementing it. A change that adds or alters behaviour without a
  corresponding test does not merge.
- **Runtime dependency gate.** No change may introduce a runtime import outside
  the standard library. Development dependencies are limited to the test runner
  and MUST be declared in test configuration, not in runtime code.
- **Review obligation.** Reviewers MUST verify compliance with all five
  principles, and MUST block on an unjustified complexity increase, a missing
  security requirement, or an untested requirement.

## Governance

This constitution supersedes all other development practices for this project.
Where any other document, convention, habit, or tool default conflicts with it,
this constitution governs, and the conflicting practice MUST be corrected.

**Amendment procedure.** Amendments MUST be proposed as a change to this file that
states the motivation, the exact principle or section text added, removed, or
redefined, and the impact on existing specifications, plans, and tests. An
amendment that invalidates existing artifacts MUST include a migration plan naming
which artifacts need revision. Amendments take effect only once merged; the
amending change MUST update the version and the Last Amended date below.

**Versioning policy.** This constitution is versioned as MAJOR.MINOR.PATCH:

- MAJOR — a principle or governance rule is removed or redefined in a way that
  existing compliant work would now violate.
- MINOR — a principle or section is added, or existing guidance is materially
  expanded with new obligations.
- PATCH — clarifications, wording, and typo fixes that change no obligation.

**Compliance review.** Every pull request and review MUST verify compliance with
these principles, and reviewers MUST state the Constitution Check outcome.
Complexity MUST be justified against a specific requirement (Principle IV). Any
exception to the Security Baseline MUST be recorded in the relevant plan with its
rationale and compensating control, and MUST be revisited at the next amendment
review; an undocumented exception is a defect to be fixed, not a precedent.
Agent-facing guidance files MUST be kept consistent with this constitution and
MUST NOT relax it.

**Version**: 1.0.0 | **Ratified**: 2026-11-12 | **Last Amended**: 2026-11-12
