# Specification Quality Checklist: Secure Login Web Application

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-23
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`

### Validation iteration 1 (2026-10-23)

- Failing items:
  - **No [NEEDS CLARIFICATION] markers remain**: two markers remained, on sign-out revocation and on limiting failed sign-ins.
  - **Requirements are testable and unambiguous**: failed because those two requirements were incomplete.
- Fixed in this iteration:
  - The order of `adduser` checks when several fail.
  - The order of `serve` startup checks.
  - The handling of password input that is not valid UTF-8.
  - A measurable timing bound for failed sign-ins (factor of 2).
  - The `Allow` header values for 405 responses.
  - The exact token format.
  - OWASP minimum cost settings for password hashing.
  - The accepted content type for sign-in.

### Validation iteration 2 (2026-10-23): all items pass

- **Clarifications resolved**: both product-owner answers are recorded under `## Clarifications` / `### Session 2026-10-23`.
  - **Q1, sign-out revocation**: a signed-out token must stop working, even as a copy.
    - FR-020: the server refuses a signed-out token until it expires, including re-encoded copies, and still refuses it after a restart.
    - FR-027: tokens from an earlier server run are refused.
    - FR-018, FR-023, User Story 5, SC-005 and SC-010 were updated to match.
  - **Q2, failed sign-ins**: 5 failures in a row lock the username for 15 minutes, even with the right password, with the same response.
    - FR-030: defines what counts as a failure, what resets the count, the exact 900-second boundary, that attempts while locked neither count nor extend the lock, correct counting under simultaneous attempts, and that locks are kept in memory only.
    - FR-014, FR-015, FR-016 (timing indistinguishable), User Story 4, the edge cases, SC-003 and SC-011 were updated to match.
- **Interpretation made (documented in Assumptions, "Sign-out across restarts")**: the answer to Q1 is read as covering the token's whole remaining lifetime, including after a restart. Two options met that reading:
  - Saving signed-out tokens in a file. This needs a storage location, and the command-line contract defines none.
  - Refusing every token from an earlier server run (FR-027). This needs no new file or option, so it was chosen. A restart therefore signs everyone out.

  `/speckit-clarify` can revisit this if the product owner prefers sessions to survive restarts.
- **Renumbering**: the FR IDs were renumbered once so they run in order (FR-001 to FR-032). Every cross-reference was checked, and each FR ID cited in the spec is defined.
- **Requirements are testable and unambiguous**: PASS. Each of FR-001 to FR-032 states an exact pass condition: status codes, headers, exit statuses, message texts, limits, the 900/1800-second boundaries, the factor-of-2 timing bound and the 10-simultaneous-attempts check.
- **No implementation details**: PASS, with a note. The HTTP status codes, header names, cookie attributes, the JWT/HS256 token format, CLI syntax, exit statuses, the `src/loginapp` layout and "Python 3.11+, standard library only" all come from the product owner's description. They are the fixed external contract and constraints, recorded as such under "Constraints". The spec chooses no internal design: no hashing function, no file format, no way of storing signed-out tokens, no way of telling server runs apart and no server structure. Those are left to planning.
- **Written for non-technical stakeholders**: PASS, with a note. The user stories and success criteria use plain language. The functional requirements have to be precise about the protocol contract that the product owner specified.
- **Constitution alignment** (`.specify/memory/constitution.md` v1.0.0):
  - Principle I (stdlib only): FR-032 and the Constraints.
  - Principle II (fail loudly): every invalid input has a stated message, exit status or error response (FR-002, FR-003, FR-004, FR-007, FR-009, FR-010, FR-011, FR-015, FR-031).
  - Principle III (testable): every FR has an ID and an automatable pass condition, and SC-009 requires tests that cite FR IDs.
  - The specification gate is met.
