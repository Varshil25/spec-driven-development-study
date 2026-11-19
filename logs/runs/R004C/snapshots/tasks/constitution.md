<!--
SYNC IMPACT REPORT (temporary scratch material for amendment review; remove before commit)

Version change: [CONSTITUTION_VERSION] (unfilled template) → 1.0.0

Rationale: First concrete ratification. The previous file was the untouched
constitution scaffold with every placeholder unresolved, so there is no prior
governance to break. Initial adoption is published as 1.0.0.

Principles defined (template slot → ratified title):
  - [PRINCIPLE_1_NAME] → I. Standard Library Only
  - [PRINCIPLE_2_NAME] → II. Fail Loudly
  - [PRINCIPLE_3_NAME] → III. Every Requirement Is Testable
  - [PRINCIPLE_4_NAME] → IV. Simplicity
  - [PRINCIPLE_5_NAME] → V. Secure by Default (NON-NEGOTIABLE)

Sections added (template slot → ratified title):
  - [SECTION_2_NAME] → Security Requirements
  - [SECTION_3_NAME] → Development Workflow & Quality Gates
  - Governance → filled with amendment, versioning, and compliance rules

Sections removed: none.

Templates/commands requiring no change: plan-template.md, spec-template.md,
tasks-template.md, and checklist-template.md read this constitution at runtime
via the Constitution Check gate; they were deliberately not modified here.

Deferred items:
  - TODO(PROJECT_NAME): The repository contains only study tooling
    (tools/sddlog) and no named application project yet. The title below uses
    the placeholder name "Python Project". Rename it in a PATCH amendment once
    the project has a real name.
-->

# Python Project Constitution

## Core Principles

### I. Standard Library Only

The runtime MUST depend on the Python standard library alone. No third-party
package may be imported by shipped code, and the project MUST run on a bare
`python3` interpreter with no install step.

Test and development tooling is the single exception: `pytest` and other
developer-only tools MAY be used, provided they are never imported by runtime
code and their absence never breaks the product. Every such tool MUST be
declared as a development dependency, separately from runtime requirements.

Adding a third-party runtime dependency requires an amendment to this
constitution, not merely a plan approval.

*Rationale: zero runtime dependencies means no install step, no supply-chain
surface, and no version drift — the program either runs or it does not.*

### II. Fail Loudly

Invalid input MUST produce a clear, actionable message and a failure signal.
A silent wrong answer is the most severe defect class this project recognises.

- A command-line entry point MUST write the diagnostic to stderr and exit with
  a non-zero status.
- A library or service entry point MUST raise an exception or return an
  explicit error response; it MUST NOT return a plausible-looking default.
- Errors MUST state what was expected, what was received, and where (argument
  name, file path, record offset) — subject to the disclosure limits in
  Principle V.
- Broad exception suppression (`except Exception: pass`, bare `except:`,
  swallowed errors in cleanup paths) is prohibited unless the plan records why
  continuing is correct and a test asserts the surviving behaviour.
- Fallback values, silent truncation, and silent coercion of malformed input
  are prohibited.

*Rationale: a loud failure costs one debugging session; a silent wrong answer
propagates into decisions nobody re-checks.*

### III. Every Requirement Is Testable

Every functional requirement in a specification MUST map to at least one
automated `pytest` test, and that mapping MUST be explicit.

- Each functional requirement carries a stable identifier; each test names the
  requirement it covers.
- A requirement that cannot be stated as an observable, automatable check MUST
  be rewritten until it can be, or struck from the specification.
- Security requirements (Principle V) are functional requirements for this
  purpose and carry the same obligation.
- Error paths required by Principle II MUST have tests asserting the message
  and the exit status or raised error — not only the happy path.
- The test suite MUST pass before a feature is considered complete. An
  unmapped requirement or a skipped test blocks completion.

*Rationale: an untested requirement is an intention, not a behaviour; the
requirement-to-test mapping is what makes the specification enforceable.*

### IV. Simplicity

A design MUST be the smallest one that satisfies the specification. Nothing is
built for anticipated future needs.

- No abstraction (class hierarchy, plugin layer, configuration system,
  indirection) may be introduced without a current requirement that fails
  without it.
- Prefer functions over classes, a module over a package, a flat data
  structure over a nested one, and the standard library's existing solution
  over a hand-rolled one.
- Every deviation toward added structure MUST be recorded in the plan's
  complexity-tracking section with the requirement that forces it, and MUST be
  removed when that requirement goes away.
- Duplication is tolerated over premature generalisation; the third occurrence
  is the trigger to factor out, not the first.
- Security controls required by Principle V are never simplified away; they are
  part of the specification, not optional structure.

*Rationale: the smallest design is the one that can be read in full, and code
that is read in full is code whose bugs are found.*

### V. Secure by Default (NON-NEGOTIABLE)

Every specification and every plan MUST state the security requirements of
each feature, derived from the OWASP Top 10 and the OWASP Application Security
Verification Standard (ASVS), and each one MUST be tested like any other
requirement under Principle III.

The baseline below applies to every feature. A feature to which a given rule
does not apply MUST say so explicitly in its specification, with the reason;
silence is not an exemption.

1. **All input is untrusted.** Command-line arguments, environment variables,
   files, archive members, network requests and responses, and previously
   stored data MUST be validated against an allow-list of expected type,
   range, length, format, and encoding before use. Validate on the way in, not
   at the point of consumption.
2. **No injection by concatenation.** SQL, shell commands, file paths, and
   markup MUST NOT be assembled from untrusted input by string concatenation,
   formatting, or interpolation. Use parameterised queries; pass argument
   vectors without a shell; encode or escape output for the exact context it is
   written into (HTML, attribute, URL, JSON, CSV, log, terminal).
3. **Path containment.** File paths derived from input MUST be resolved and
   confirmed to land inside an explicitly allowed base directory, and MUST NOT
   follow symbolic links out of it. Archive extraction MUST reject absolute
   paths, parent-directory traversal, links, and declared sizes over the limit.
4. **Credential storage.** Passwords MUST be stored only as salted hashes from
   a deliberately slow, memory-hard or iterated algorithm with current
   parameters. Passwords, tokens, keys, and other secrets MUST NOT be written
   anywhere in plaintext — not in source, config, logs, fixtures, or test data.
5. **Cryptographic randomness and comparison.** Identifiers, tokens, salts,
   and nonces MUST come from a cryptographically secure generator
   (`secrets`, `os.urandom`), never from `random`. Secrets, tokens, MACs, and
   hashes MUST be compared in constant time (`hmac.compare_digest`).
6. **Resource limits.** Every input MUST have an enforced maximum size, and
   every operation an enforced bound on time and memory. Recursion depth,
   decompression ratios, nesting depth, collection sizes, and regular
   expression backtracking MUST be bounded so no input can exhaust the host.
7. **Authorisation on every operation.** Access MUST be checked at the point of
   each operation against the acting identity, not inferred from an earlier
   check, a client-supplied field, or reachability of an endpoint. Checks MUST
   hold under concurrent requests: shared state MUST be guarded so no
   interleaving permits an action a serial execution would deny.
8. **Least-privilege files.** Files and directories MUST be created with the
   narrowest permissions that work, set at creation. Anything holding secrets
   or personal data MUST be owner-only. Temporary files MUST be created
   atomically in a private location, never at a predictable path.
9. **No sensitive data in output.** Personal data, credentials, tokens, session
   identifiers, and full internal paths or stack traces MUST NOT appear in
   program output, logs, telemetry, or error messages. User-facing errors say
   what is wrong and how to fix it; detail that would aid an attacker stays
   internal. Redaction MUST happen before anything is written, not after.

*Rationale: security requirements that live outside the specification are never
scheduled and never tested; naming them per feature and testing them like any
other requirement is what makes them real.*

## Security Requirements

How Principle V is carried through the workflow:

- **Specification stage.** Each feature specification MUST contain a security
  requirements subsection that walks the nine baseline rules, states which
  apply, names the concrete requirement for each applicable rule as a testable
  statement with an identifier, and justifies every rule marked not
  applicable. Untrusted inputs MUST be enumerated by name, with their
  validation rules and size limits.
- **Planning stage.** Each plan MUST map every security requirement to the
  module, function, or boundary that enforces it, name the standard-library
  mechanism used (`secrets`, `hmac.compare_digest`, `sqlite3` parameter
  binding, `subprocess` argument lists, `os.open` with an explicit mode,
  `html.escape`, `resource` limits), and record the identifiers of the tests
  that will prove it.
- **Test stage.** Security requirements are tested as negatives as well as
  positives: the malicious or malformed input MUST be shown to be rejected,
  not merely the valid input accepted. Traversal, injection, oversized input,
  unauthorised access, and secret leakage into logs each need an explicit
  failing-input test.
- **Review stage.** A change that touches input handling, path resolution,
  query or command construction, authentication, authorisation, cryptography,
  file creation, or logging MUST be reviewed against this section before merge.
- **Reporting.** A discovered vulnerability MUST be recorded, fixed, and
  covered by a regression test that fails against the unfixed code.

## Development Workflow & Quality Gates

- **Order of work.** Specify → plan → tasks → implement. Implementation MUST
  NOT begin before the specification states its functional and security
  requirements and the plan maps them to tests.
- **Constitution Check.** Plans MUST pass the Constitution Check gate before
  and after design. A violation either gets removed or gets an entry in
  complexity tracking naming the requirement that forces it. Unjustified
  violations block the plan.
- **Definition of done.** A feature is complete only when: every functional
  and security requirement maps to a passing `pytest` test; error paths assert
  message and exit status or raised error; the full suite passes; no
  third-party runtime import was added; and no placeholder, stub, or `TODO`
  remains in the delivered path.
- **Review obligations.** Every review MUST verify the five principles
  explicitly, not implicitly: dependency surface, failure behaviour,
  requirement-to-test mapping, design size, and the security baseline.
- **Secrets hygiene.** No credential, token, key, or real personal data may
  enter the repository, including in tests and fixtures. Tests MUST use
  synthetic values.

## Governance

This constitution supersedes all other development practices for this project.
Where a plan, task list, habit, or tool default conflicts with it, this
document wins.

**Amendment procedure.** Amendments MUST be proposed as a written change to
this file stating the principle or section affected, the motivation, the
semantic version bump with its rationale, and the migration consequences for
work already in progress. An amendment takes effect when it is merged; the
Last Amended date MUST be updated in the same change. Principle V is marked
NON-NEGOTIABLE: its baseline may be strengthened or clarified at any time, but
weakening or removing any of its nine rules requires a MAJOR bump and an
explicit written acceptance of the risk.

**Versioning policy.** This document is versioned MAJOR.MINOR.PATCH:

- MAJOR — a principle or governance rule is removed, or redefined in a way
  that permits what it previously forbade.
- MINOR — a principle or section is added, or existing guidance is materially
  expanded with new obligations.
- PATCH — clarification, wording, typo, or formatting change that adds no new
  obligation and relaxes none.

**Compliance review.** Every pull request and review MUST verify compliance
with the five principles and the Security Requirements section; a
non-compliant change does not merge. Added structure MUST be justified in the
plan's complexity tracking under Principle IV. Agent-facing guidance files
(`CLAUDE.md` and per-command Spec Kit templates) provide runtime development
guidance and MUST stay consistent with this constitution; where they diverge,
this constitution governs and the guidance file is the artifact that gets
corrected.

**Version**: 1.0.0 | **Ratified**: 2026-11-04 | **Last Amended**: 2026-11-04
