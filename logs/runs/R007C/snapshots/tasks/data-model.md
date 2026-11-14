# Phase 1 Data Model: Burn After Reading and Password Protection

**Feature**: `002-burn-after-reading-password` | **Date**: 2026-11-10 | **Plan**: [plan.md](./plan.md)

No new entity. The spec's Key Entities section extends the one entity feature 001 defined —
**Snippet** — with two properties, and names **Reading password** as a concept rather than a stored
thing: the password itself is never stored, only a derivation of it, and it lives inside the
snippet's own record. There is still exactly one relationship (the storage location contains
snippets) and nothing refers to anything else.

Wire field names and the header name are fixed by the spec's Constraints section; see
[contracts/http-api.md](./contracts/http-api.md). The on-disk encoding is fixed by
[contracts/storage.md](./contracts/storage.md). Feature 001's model, which continues to hold
unchanged, is [../001-pastebin-service/data-model.md](../001-pastebin-service/data-model.md).

## Snippet — the two added properties

Still a plain `dict` (Principle IV), created by `store.create_paste()` and returned by
`store.read_paste()`. The five fields of feature 001 are unchanged in type, origin, and constraints.

| Field | Type | Origin | Constraints |
|-------|------|--------|-------------|
| `burn_after_reading` | `bool` | caller (`burn_after_reading`) | Fixed at publication; never modified afterwards. Absent from a record written by the previous version, which means `False` (FR-067). |
| `password` | `dict \| None` | derived from caller (`password`) | `None` when unprotected. Otherwise `{"iterations": int, "salt": str, "hash": str}` — see below. The password itself is never a field of the record and is never retained after the publication request is answered (FR-056). |

### The `password` sub-record

| Key | Type | Value |
|-----|------|-------|
| `iterations` | `int` | PBKDF2 iteration count used for *this* snippet, as calibrated when the serving process started ([research.md](./research.md) R-02). Positive. Verification uses this value, not the current calibration, so a snippet still verifies after a restart on a differently-calibrated host (FR-056). |
| `salt` | `str` | 16 bytes from `secrets.token_bytes(16)`, hex-encoded (32 characters). Drawn per snippet, so two snippets with identical passwords have different salts and different hashes (FR-073, SC-021). |
| `hash` | `str` | `hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)`, hex-encoded (64 characters). One-way: the password cannot be recovered from it (FR-056). |

Either all three keys are present or the whole `password` value is `None`; nesting them makes that
structural rather than a checked invariant, and makes "is this snippet protected?" the single test
`record["password"] is not None` at every site that asks.

### Derived report fields

Neither is stored; both are computed from the record when `GET /pastes/<id>` answers (FR-064):

| Response field | Computed as | Never |
|----------------|-------------|-------|
| `burn_after_reading` | `record.get("burn_after_reading", False)` | absent, `null`, or anything but a JSON boolean |
| `protected` | `record.get("password") is not None` | absent, `null`, or anything but a JSON boolean |

The `password` sub-record is never serialised into any response, in whole or in part (FR-057,
FR-066, SC-015).

## Caller-supplied input (publication)

Added to feature 001's table. The decisive difference from `expires_in` is that **absence, not
`null`, is how a caller declines either option** — `null` is an invalid value for both (spec
Assumptions, FR-046, FR-055). The check is therefore `"field" in payload`, not
`payload.get("field") is not None`.

| Input field | Type accepted | Rule | Violation |
|-------------|---------------|------|-----------|
| `burn_after_reading` | JSON `true`/`false`, or absent | if present: `type(v) is bool`. `"true"`, `"false"`, `1`, `0`, `null`, `[]`, `{}` are all rejected — no coercion | 400 |
| `password` | JSON string, or absent | if present: `type(v) is str` and `1 <= len(v) <= 128`, **counted in characters**. `""`, a 129-character string, a number, a boolean, `null`, a list, an object are all rejected | 400 |
| any other field | any | still ignored (FR-015, FR-068) | — |
| declared `Content-Length` | integer | if > 395,776 → reject before reading the body ([research.md](./research.md) R-09) | 413 |

`len(v)` on a Python `str` counts characters, which is what FR-054 and the spec's edge case ("the
1-to-128 bound is on characters, not encoded bytes") require: a 128-character password of multi-byte
characters is valid. No trimming, case folding, or Unicode normalisation is applied at publication or
at verification — the password is stored and compared exactly as given (FR-058).

A submission invalid in several ways is rejected once, naming one problem; which one follows from the
order the checks are written in and is not specified (spec Assumptions).

## Caller-supplied input (reading)

| Input | Shape | Rule |
|-------|-------|------|
| `X-Paste-Password` | request header, 0, 1, or more occurrences | Inspected **only** when the snippet is protected (FR-062). Exactly one occurrence, whose bytes decode as UTF-8 to the snippet's password, is the only accepted form. Absent, repeated, undecodable, or non-matching are one outcome: 403 ([research.md](./research.md) R-06, R-07). |

## Lifecycle

Feature 001's lifecycle gains one transition and one terminal state. The three ways a snippet leaves
circulation are independent and whichever happens first wins.

```text
                   POST /pastes (valid)
     (nonexistent) ──────────────────────────▶ LIVE ◀── a refused or failed read
                                                │       returns here unchanged
            ┌───────────────────────────────────┼───────────────────────────────┐
            │ now >= expires_at                 │ DELETE with correct token     │ successful read,
            │ (not a consumption)               │ (needs no password)           │ if burn_after_reading
            ▼                                   ▼                               ▼
        EXPIRED                             DELETED                         CONSUMED
  (file remains; 404 on every          (file unlinked durably;     (file unlinked durably *before*
   access, whatever password            permanent)                  the response is written;
   is presented; never consumed)                                    permanent, survives restart)
```

All three terminal states answer every later request for the identifier with **404**, and are
indistinguishable from each other and from an identifier never issued (FR-060).

### What counts as a consumption

A one-time snippet is consumed on, and only on, a read that has passed every check that could refuse
it and has the text in hand (FR-049). Concretely, in the order the handler performs them
([research.md](./research.md) R-05):

| Outcome of a read | Status | Consumed? |
|-------------------|--------|-----------|
| Identifier unknown, deleted, or already consumed | 404 | — |
| Expiry moment reached or passed | 404 | no (FR-053) |
| Stored record damaged | 500 | no (FR-049) |
| Protected, and the password is absent, repeated, undecodable, or wrong | 403 | no (FR-049, SC-013) |
| Every check passed, text obtained, claim lost to a concurrent reader | 404 | no — the other reader consumed it (FR-050) |
| Every check passed, text obtained, claim won | 200 | **yes** |
| Claim won, then the caller abandoned the connection or the service stopped mid-body | — | **yes**, deliberately (FR-049, FR-051) |

The claim is an atomic `unlink` plus a directory `fsync`, so exactly one of any number of overlapping
readers wins it and the removal is durable before the first byte of the response is written
(FR-048, FR-050, [research.md](./research.md) R-04).

## Server state

One value is added to the server object, alongside `data_dir`:

| Attribute | Type | Set | Meaning |
|-----------|------|-----|---------|
| `password_iterations` | `int` | once, in `make_server()` | PBKDF2 iteration count stamped into records this process creates, measured so that one verification costs ~50 ms on this host (FR-073, [research.md](./research.md) R-02). Read by the publish handler; verification ignores it and uses each record's own value. |

It is not a configuration option: no command-line flag sets it and no caller can influence it.

## Requirement to test map

Every functional requirement maps to at least one `pytest` test naming its identifier in the test
name or docstring (Constitution Principle III, SC-020). Module layout is in
[plan.md](./plan.md#source-code-repository-root). Requirements are listed in the order the spec
states them, which is not numerically contiguous.

| FR | Test module | Test(s) |
|----|-------------|---------|
| FR-045 | `test_burn.py` | `test_fr045_burn_true_publishes`, `test_fr045_absent_burn_means_not_one_time` |
| FR-046 | `test_burn.py` | `test_fr046_non_boolean_burn_is_400` (parametrised over `"true"`, `"false"`, `1`, `0`, `null`, `[]`, `{}`), `test_fr046_rejected_publication_creates_nothing` |
| FR-047 | `test_burn.py` | `test_fr047_one_time_flag_is_on_disk`, `test_fr047_one_time_survives_restart` |
| FR-048 | `test_burn.py` | `test_fr048_first_read_returns_then_404_forever`, `test_fr048_first_raw_read_returns_then_404`, `test_fr048_record_is_gone_when_the_read_returns`, `test_fr048_abandoned_response_still_consumes` |
| FR-049 | `test_burn.py` | `test_fr049_wrong_password_does_not_consume`, `test_fr049_missing_password_does_not_consume`, `test_fr049_expired_one_time_is_not_consumed`, `test_fr049_damaged_one_time_is_not_consumed` |
| FR-050 | `test_burn.py` | `test_fr050_concurrent_reads_serve_exactly_one`, `test_fr050_winner_body_is_complete` |
| FR-051 | `test_burn.py` | `test_fr051_consumed_snippet_stays_gone_across_restart` |
| FR-052 | `test_burn.py` | `test_fr052_unread_one_time_deletes_with_token`, `test_fr052_consumed_one_time_delete_is_404` |
| FR-053 | `test_burn.py` | `test_fr053_expired_one_time_is_404_on_both_endpoints` |
| FR-054 | `test_password.py` | `test_fr054_password_of_1_and_128_chars_accepted`, `test_fr054_length_is_counted_in_characters_not_bytes` |
| FR-055 | `test_password.py` | `test_fr055_invalid_password_is_400` (parametrised over `""`, 129 chars, number, bool, `null`, `[]`, `{}`), `test_fr055_rejected_publication_creates_nothing` |
| FR-056 | `test_password.py` | `test_fr056_record_holds_no_recoverable_password`, `test_fr056_same_password_required_after_restart` |
| FR-073 | `test_password.py` | `test_fr073_one_verification_costs_between_10ms_and_200ms`, `test_fr073_salt_is_unique_per_snippet`, `test_fr073_identical_passwords_have_different_stored_forms` |
| FR-074 | `test_password.py` | `test_fr074_verification_does_not_delay_other_snippets` |
| FR-057 | `test_password.py` | `test_fr057_password_absent_from_publication_response`, `test_fr057_password_absent_from_every_response_and_stream` |
| FR-058 | `test_password.py` | `test_fr058_correct_password_reads_both_endpoints`, `test_fr058_non_ascii_password_matches_utf8_header_bytes`, `test_fr058_no_trimming_case_folding_or_normalisation`, `test_fr058_invalid_utf8_header_bytes_are_403` |
| FR-059 | `test_password.py` | `test_fr059_missing_password_is_403`, `test_fr059_wrong_password_is_403`, `test_fr059_empty_password_header_is_403`, `test_fr059_refused_read_leaves_snippet_readable` |
| FR-072 | `test_password.py` | `test_fr072_repeated_password_header_is_403`, `test_fr072_repeated_header_with_one_correct_copy_is_403`, `test_fr072_snippet_still_readable_with_one_correct_header` |
| FR-060 | `test_password.py` | `test_fr060_unknown_identifier_is_404_not_403`, `test_fr060_expired_protected_snippet_is_404_whatever_password`, `test_fr060_consumed_protected_snippet_is_404` |
| FR-061 | `test_password.py` | `test_fr061_verification_uses_compare_digest_on_derived_bytes` |
| FR-062 | `test_password.py` | `test_fr062_password_header_ignored_on_unprotected_snippet` (parametrised over a value, invalid UTF-8 bytes, and a repeated header) |
| FR-063 | `test_password.py` | `test_fr063_delete_needs_only_the_token_no_password`, `test_fr063_password_does_not_substitute_for_the_token` |
| FR-064 | `test_flags.py` | `test_fr064_flags_reported_for_all_four_combinations`, `test_fr064_flags_are_booleans_never_absent_or_null` |
| FR-065 | `test_flags.py` | `test_fr065_raw_body_is_the_text_alone`, `test_fr065_raw_content_type_unchanged` |
| FR-066 | `test_flags.py` | `test_fr066_read_discloses_neither_token_nor_password` |
| FR-067 | `test_compatibility.py` | `test_fr067_five_key_legacy_record_reads_as_neither`, `test_fr067_legacy_record_is_not_reported_as_damaged` |
| FR-068 | `test_compatibility.py` | `test_fr068_feature_001_suite_passes_unchanged` (the whole of `tests/` from feature 001, run unmodified), `test_fr068_plain_snippet_response_fields_unchanged_but_for_the_two_flags` |
| FR-069 | `test_compatibility.py` | `test_fr069_every_new_error_has_a_single_error_field` (parametrised over the 400, 403, and 404 paths this feature introduces) |
| FR-070 | `test_compatibility.py` | `test_fr070_invalid_option_is_400`, `test_fr070_password_failure_is_403`, `test_fr070_no_enumerated_input_produces_a_500_or_a_traceback` |
| FR-071 | `test_compatibility.py` | `test_fr071_max_content_with_max_password_and_burn_is_created`, `test_fr071_ceiling_covers_worst_case_escaped_body`, `test_fr071_ceiling_is_independent_of_declared_length`, `test_fr071_oversize_content_is_still_413` |

Success criteria SC-011…SC-021 are covered by the same tests: SC-012 by the FR-050 and FR-051 tests,
SC-013 by the FR-049 tests, SC-014 by the FR-056 and FR-058 tests, SC-015 by the FR-057 test,
SC-016 by the FR-063 tests, SC-017 by the FR-046, FR-055, and FR-070 tests, SC-018 by the FR-067 and
FR-068 tests, SC-019 by the FR-064 tests, SC-021 by the FR-073 and FR-074 tests. SC-011 and SC-020
are properties of this map and of [quickstart.md](./quickstart.md) rather than of a single test.
