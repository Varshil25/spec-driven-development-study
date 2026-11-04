<!--
SYNC IMPACT REPORT (scratch material for amendment review; remove before commit)

Version change: [CONSTITUTION_VERSION] (unfilled template) -> 1.0.0
Bump rationale: Initial ratification. The previous file was the unpopulated
scaffold with no governance in force, so this is the first real version rather
than an amendment of an existing one.

Modified principles:
  - [PRINCIPLE_1_NAME] -> I. Standard Library Only
  - [PRINCIPLE_2_NAME] -> II. Fail Loudly
  - [PRINCIPLE_3_NAME] -> III. Every Requirement Is Testable
  - [PRINCIPLE_4_NAME] -> IV. Simplicity
  - [PRINCIPLE_5_NAME] -> (removed; user specified four principles)

Added sections:
  - Additional Constraints (from [SECTION_2_NAME])
  - Development Workflow and Quality Gates (from [SECTION_3_NAME])
  - Governance (populated)

Removed sections:
  - Fifth principle slot, unused under the four-principle set requested.

Follow-up TODOs:
  - None. PROJECT_NAME was inferred as "Small Python Project" because the repo
    has no README, package metadata, or prior constitution naming the project.
    Rename in place when the project acquires a real name; that is a PATCH bump.
-->

# Small Python Project Constitution

## Core Principles

### I. Standard Library Only

The runtime MUST depend only on the Python standard library. No third-party package
may be imported by code that executes in production or in normal use of the project.
Development and test tooling is exempt only for `pytest` and its plugins; any other
proposed development dependency MUST be justified in the plan and approved as an
amendment to this section. Vendoring third-party source into the repository to work
around this rule is prohibited.

Rationale: a dependency-free runtime installs and runs anywhere `python3` exists,
has no supply-chain or version-drift surface, and keeps a small project small.

### II. Fail Loudly

Invalid input, unmet preconditions, and unreachable state MUST produce a clear,
actionable message naming what was wrong. A command-line entry point MUST write the
message to stderr and exit with a non-zero status; a library or service entry point
MUST raise or return an explicit error response. Silently returning a wrong,
partial, or default answer in place of an error is prohibited. Bare `except:` and
`except Exception: pass` are prohibited; an exception may only be swallowed where the
code documents in a comment why continuing is correct. Error messages MUST NOT leak
secrets or credentials.

Rationale: a wrong answer that looks right is the most expensive failure mode. A
loud failure is cheap to diagnose; a silent one corrupts whatever consumes it.

### III. Every Requirement Is Testable

Every functional requirement in a specification MUST map to at least one automated
`pytest` test, and that mapping MUST be explicit — the test name or a comment on it
names the requirement it covers. A requirement that cannot be stated as a test with
observable inputs and outputs MUST be rewritten until it can be, or removed from the
specification. Each error path required by Principle II MUST have its own test
asserting both the message content and the exit status or raised error. A feature is
not complete while any of its requirements lack a passing test.

Rationale: an untestable requirement cannot be verified, so it cannot be known to be
met; forcing the mapping up front is what makes the specification honest.

### IV. Simplicity

Implementations MUST be the smallest design that satisfies the specification.
Abstraction layers, configuration options, plugin seams, and generality beyond the
stated requirements MUST NOT be added speculatively — YAGNI applies by default. Any
deviation (an added layer, a second way to do one thing, a non-obvious optimization)
MUST be justified in the plan's complexity tracking with the concrete requirement
that forces it. When two designs both meet the specification, the one with fewer
moving parts wins.

Rationale: every unused mechanism is permanent cost — code to read, paths to test,
and decisions to re-litigate — paid against a benefit that was only hypothetical.

## Additional Constraints

- **Language runtime**: Python 3.11 or newer. Code MUST NOT rely on features
  unavailable in the declared minimum version.
- **Layout**: source and its tests live in the repository under a single obvious
  path per component; tests are discoverable by `pytest` from the repository root
  with no configuration beyond what is committed.
- **Interfaces**: command-line entry points follow the text-in/text-out convention —
  results to stdout, diagnostics to stderr, status in the exit code.
- **No hidden state**: code MUST NOT write outside paths the caller supplied or the
  specification named, and MUST NOT require network access unless a requirement
  states it.
- **Secrets**: credentials MUST NOT be committed to the repository, logged, or
  included in error output.

## Development Workflow and Quality Gates

1. Specification first: a feature begins with a specification whose functional
   requirements are each stated in testable terms (Principle III).
2. Planning: the plan records the chosen design, confirms no new runtime dependency
   is introduced (Principle I), and records any complexity deviation with its
   justification (Principle IV).
3. Implementation: tests for a requirement are written alongside or before the code
   that satisfies it; error paths are implemented and tested as first-class
   behavior, not as an afterthought.
4. Gate to merge — all of the following MUST hold:
   - the full `pytest` suite passes;
   - every functional requirement in the feature's specification has at least one
     passing test traceable to it;
   - no third-party runtime import was added;
   - no new silent-failure path was introduced;
   - any added complexity is justified in the plan.
5. A change that cannot pass a gate is fixed or withdrawn. Gates are not waived
   informally; waiving one requires an amendment under Governance.

## Governance

This constitution supersedes other practices, conventions, and preferences in this
project. Where a plan, template, review comment, or habit conflicts with it, this
document governs and the conflicting artifact MUST be corrected.

**Amendment procedure**: amendments are proposed as a change to this file, stating
the principle or section affected, the rationale, and the impact on existing code
and specifications. An amendment takes effect when it is approved and merged by the
project maintainer. An amendment that invalidates existing code MUST include the
migration required to bring that code back into compliance.

**Versioning policy**: this document is versioned MAJOR.MINOR.PATCH.
- MAJOR — a principle is removed or redefined in a backward-incompatible way, or a
  governance rule changes such that previously compliant work is now non-compliant.
- MINOR — a principle or section is added, or existing guidance is materially
  expanded.
- PATCH — clarification, wording, or typo fixes that do not change what is required.

**Compliance review**: every review MUST verify the merge gates above. Compliance is
re-checked at each specification, plan, and implementation step rather than once at
the end, so that a violation is caught while it is still cheap to undo.

**Version**: 1.0.0 | **Ratified**: 2026-11-03 | **Last Amended**: 2026-11-03
