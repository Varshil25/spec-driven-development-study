<!--
SYNC IMPACT REPORT (scratch material for amendment review — remove before committing)

Version change: none (unfilled template) → 1.0.0
Bump rationale: Initial ratification. The previous file was the unmodified scaffold with all
placeholder tokens intact, so no prior governance existed to supersede. First concrete constitution
is published as 1.0.0 rather than a MINOR/PATCH bump on a placeholder document.

Modified principles (placeholder → concrete):
- [PRINCIPLE_1_NAME] → I. Standard Library Only
- [PRINCIPLE_2_NAME] → II. Fail Loudly
- [PRINCIPLE_3_NAME] → III. Every Requirement Is Testable
- [PRINCIPLE_4_NAME] → IV. Simplicity
- [PRINCIPLE_5_NAME] → V. Secure by Default (NON-NEGOTIABLE)

Added sections (template slots filled, hierarchy unchanged):
- [SECTION_2_NAME] → Security Baseline (minimum controls required by Principle V)
- [SECTION_3_NAME] → Development Workflow & Quality Gates
- Governance → amendment procedure, versioning policy, compliance review

Removed sections: none (no headings demoted, promoted, added, or dropped relative to the template)

Deferred items / follow-up TODOs:
- TODO(PROJECT_NAME): The repository has no README, package metadata, or other declared project
  name. "R039" is the repository root directory name, used as a provisional title. Replace it with
  the real project name on the next amendment (PATCH bump).
-->

# R039 Constitution

## Core Principles

### I. Standard Library Only

The project MUST run on the Python standard library alone. No third-party package may be imported
by code that executes at runtime. Any specification or plan that assumes a third-party runtime
dependency is non-compliant and MUST be reworked or justified through the amendment process in
**Governance**.

The single exception is the test and developer tooling chain: `pytest` is the mandated test runner
(Principle III), and linters, formatters, and type checkers MAY be third-party. These MUST NOT be
imported by shipped code, and the project MUST remain fully usable by someone who has installed
nothing but CPython.

*Rationale:* A dependency-free runtime removes supply-chain exposure, version drift, and install
friction from a small project, and keeps the deployable surface auditable in full.

### II. Fail Loudly

Invalid input MUST produce a clear, actionable message and an explicit failure signal. A silent
wrong answer is the most severe defect class in this project and MUST never ship.

- Command-line entry points MUST write the diagnostic to stderr and exit with a non-zero status.
- Library and service entry points MUST raise an exception or return an explicit error response;
  they MUST NOT return a sentinel that a caller can mistake for a successful result.
- Code MUST NOT swallow exceptions. A bare `except:` or an `except Exception:` that discards the
  error is prohibited. Catching is permitted only to add context, translate to a documented error
  type, or release a resource — and the failure MUST still propagate or be reported.
- A diagnostic MUST say what was rejected and why, in terms the caller can act on, and MUST
  respect the output-redaction rule in **Security Baseline**.
- Defaults MUST NOT paper over bad input. No silent coercion, truncation, or substitution of a
  "reasonable" value for an invalid one.

*Rationale:* An error that is visible costs minutes; a wrong answer that looks right costs
whatever was decided on top of it.

### III. Every Requirement Is Testable

Every functional requirement MUST map to at least one automated `pytest` test, and every
requirement in **Security Baseline** MUST be tested on the same terms as any other requirement —
security assertions are not a separate, softer category.

- A requirement that cannot be stated as an observable, automatable assertion is not yet specified.
  It MUST be rewritten until it can be, before implementation begins.
- Specifications MUST state each requirement so that its pass/fail condition is unambiguous.
  Plans MUST record the requirement-to-test mapping.
- Failure paths are requirements. Each Principle II behaviour in scope MUST have a test asserting
  the exit status or error type *and* the message content.
- The suite MUST pass before any change is considered complete. A known-failing test MUST NOT be
  skipped, marked expected-failure, or deleted to make the suite green; either fix the code or
  amend the requirement.
- Tests MUST be deterministic and MUST NOT require network access.

*Rationale:* An untestable requirement cannot be verified, regression-protected, or honestly
reported as done.

### IV. Simplicity

Every feature MUST be the smallest design that satisfies its specification. Scope is set by the
spec, not by anticipated futures.

- Build what the specification requires and nothing beyond it. Speculative generality,
  configuration knobs with one caller, and abstractions with one implementation MUST be omitted.
- Prefer a function to a class, a module to a package, and a flat data structure to a custom type,
  unless the specification demands otherwise.
- Any structure added for reasons other than a stated requirement MUST be justified in the plan's
  complexity section or removed.
- Simplicity MUST NOT be invoked to skip a requirement. Omitting validation, error handling, or a
  security control is not simplicity — it is an incomplete implementation. Where this principle
  appears to conflict with Principle II, III, or V, those principles win.

*Rationale:* In a small project, every line is a line someone must read, test, and secure.

### V. Secure by Default (NON-NEGOTIABLE)

Every specification and every plan MUST state the security requirements of the feature it
describes. A spec or plan with no security section is incomplete and MUST NOT proceed to
implementation.

- Security requirements MUST be derived against the **OWASP Top 10** and the **OWASP Application
  Security Verification Standard (ASVS)**. The spec MUST name the categories or ASVS requirements
  considered, and MUST record categories judged not applicable together with the reason.
- Each security requirement MUST be written as a testable assertion and covered by automated tests
  under Principle III, including negative tests that prove the control rejects malicious input.
- The controls in **Security Baseline** are the floor for every feature, not a menu. A feature
  MUST satisfy all applicable baseline controls plus any additional requirements its own threat
  surface implies.
- Secure defaults are mandatory: the safe behaviour MUST be the one that requires no
  configuration, and any opt-out MUST be explicit, documented, and tested.

*Rationale:* Security stated per feature and tested per requirement is enforced; security left as
a general intention is not.

## Security Baseline

These controls are the minimum required by Principle V. They apply to every feature, MUST be
reflected in each spec and plan, and MUST each be covered by automated tests. All are achievable
with the standard library, satisfying Principle I.

**Untrusted input.** Every input is untrusted: command-line arguments, environment variables,
files, archive contents, network requests and responses, and previously stored data. Each MUST be
validated against an explicit allowlist of expected type, range, length, and format before use.
Validation MUST happen at the boundary, before the value reaches any logic. Data read back from
storage MUST be re-validated — persistence is not trust.

**No injection by concatenation.** SQL, shell commands, file paths, and markup MUST NOT be
assembled from untrusted input by string concatenation, interpolation, or formatting.

- SQL MUST use parameterised queries (`sqlite3` placeholders). Identifiers that cannot be
  parameterised MUST come from a fixed allowlist.
- Subprocesses MUST be invoked with an argument list and `shell=False`. `shell=True` is prohibited.
- Output MUST be encoded for the context it is written into (`html.escape` for HTML,
  `json.dumps` for JSON, `urllib.parse.quote` for URLs, `csv` for CSV). Encoding MUST happen at
  the point of output, chosen by destination context.

**Path containment.** File paths derived from untrusted input MUST be resolved
(`pathlib.Path.resolve()` or `os.path.realpath`) and then verified to lie inside an allowed base
directory before any open, read, write, or delete. Symbolic links MUST NOT be followed out of that
directory. Archive extraction MUST validate every member path and size before writing
(`tarfile` extraction MUST use `filter="data"`), rejecting absolute paths, `..` traversal, links,
and device entries.

**Password and secret storage.** Passwords MUST be stored only as salted, deliberately slow
hashes (`hashlib.scrypt`, or `hashlib.pbkdf2_hmac` with a documented high iteration count), with a
unique per-password salt from `secrets`. Fast hashes (MD5, SHA-1, bare SHA-256) MUST NOT be used
for passwords. Passwords, tokens, keys, and other secrets MUST NOT be written to disk, source
code, or configuration in plaintext.

**Randomness and comparison.** Identifiers, tokens, salts, and nonces that carry any security
weight MUST be generated with `secrets`. `random` MUST NOT be used for these. Comparison of
secrets, tokens, and hashes MUST use `hmac.compare_digest` for constant-time behaviour.

**Resource limits.** Every input MUST have a documented, enforced maximum size, and every
operation on untrusted input MUST have a bound on the time and memory it can consume. Reads MUST
be bounded rather than unbounded (`read(n)`, streaming, declared maximum lengths). Decompression
MUST enforce an uncompressed-size ceiling. Recursive and backtracking processing of untrusted
input MUST have an explicit depth or complexity limit. Exceeding a limit MUST fail per Principle
II, never degrade silently.

**Access control on every operation.** Authorization MUST be checked at the point of each
operation against the acting identity, not once per session and not in the caller. Checks MUST be
deny-by-default. Where concurrent requests can interleave, the check and the operation it guards
MUST be atomic with respect to each other — a time-of-check-to-time-of-use gap is a defect, and
concurrent access MUST be covered by tests.

**File permissions.** Files and directories MUST be created with the narrowest permissions that
work — secrets and private data at `0o600` (directories `0o700`), set at creation via `os.open`
with `mode` or an explicit `os.chmod` before any content is written, never widened afterwards.
Temporary files MUST be created with `tempfile`, never at a predictable path.

**Output, log, and error hygiene.** Personal data, credentials, tokens, keys, and session
identifiers MUST NOT appear in stdout, stderr, logs, or error messages. Error text returned to a
caller MUST describe the problem without disclosing secrets, internal paths, or raw input
containing sensitive values. Stack traces MUST NOT be exposed to untrusted callers. Where a
sensitive value must be referenced, it MUST be redacted or replaced by a non-reversible
identifier. Redaction MUST be tested.

## Development Workflow & Quality Gates

**Specification gate.** A specification MUST state functional requirements as testable assertions
and MUST include the security requirements and OWASP/ASVS consideration required by Principle V.
Specs failing either condition MUST NOT advance to planning.

**Planning gate.** A plan MUST record the requirement-to-test mapping for every functional and
security requirement, MUST confirm no third-party runtime dependency is introduced, and MUST
justify any structure not demanded by the specification.

**Implementation gate.** A change is complete only when: the full `pytest` suite passes; every new
or changed requirement has at least one test; failure paths assert both failure signal and message;
applicable **Security Baseline** controls are implemented and covered by negative tests; and no
runtime import outside the standard library was added.

**Review.** Review MUST verify these gates explicitly rather than assume them. A reviewer who
cannot locate the test for a requirement MUST treat the requirement as unimplemented. Unjustified
complexity MUST be sent back under Principle IV.

## Governance

This constitution supersedes all other development practices, conventions, and preferences in this
project. Where any other document, template, or habit conflicts with it, this constitution governs.

**Amendment procedure.** Amendments MUST be proposed as an explicit change to this file, stating
the principle or section affected, the rationale, and the migration consequences for existing
specs, plans, and code. An amendment takes effect only once written here with the version and
**Last Amended** date updated. Principles MUST NOT be waived case by case: a rule that no longer
holds MUST be amended in the open or complied with.

**Versioning policy.** This document is versioned as MAJOR.MINOR.PATCH:

- **MAJOR** — a principle or governance rule is removed, or redefined in a way that makes
  previously compliant work non-compliant.
- **MINOR** — a principle or section is added, or existing guidance is materially expanded.
- **PATCH** — clarification, wording, or typo fixes that do not change what is required.

**Compliance review.** Every specification, plan, and code review MUST verify compliance with
these principles. Non-compliance MUST block the change until either the change or this
constitution is amended. Complexity, and any deviation permitted by an explicit exception above,
MUST be justified in writing in the plan.

**Version**: 1.0.0 | **Ratified**: 2026-11-21 | **Last Amended**: 2026-11-21
