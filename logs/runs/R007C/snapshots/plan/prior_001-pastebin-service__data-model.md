# Phase 1 Data Model: Pastebin Service

**Feature**: `001-pastebin-service` | **Date**: 2026-11-09 | **Plan**: [plan.md](./plan.md)

Two entities come from the spec's Key Entities section: **Snippet** (a paste) and **Storage
location** (the nominated directory). There is no relationship table because there is exactly one
relationship — the storage location contains snippets — and no snippet refers to another.

Wire field names are fixed by the spec's Constraints section; see
[contracts/http-api.md](./contracts/http-api.md). The on-disk encoding is fixed by
[contracts/storage.md](./contracts/storage.md).

## Snippet (paste)

Represented in code as a plain `dict` (Constitution Principle IV — plain data over classes), created
by `store.create_paste()` and returned by `store.read_paste()`.

| Field | Type | Origin | Constraints |
|-------|------|--------|-------------|
| `id` | `str` | generated | 22 URL-safe chars from `secrets.token_urlsafe(16)`; unique among all ever issued; appears in the location path. Accepted from a request path only if it matches `^[A-Za-z0-9_-]{1,64}$`. |
| `content` | `str` | caller (`content`) | Required. Must be a JSON string. ≤ 65,536 bytes when UTF-8 encoded. Empty string is valid. Stored and returned byte-for-byte unchanged. |
| `created_at` | `str` | generated | `now(UTC)` truncated to whole seconds, formatted `%Y-%m-%dT%H:%M:%SZ`. Immutable. |
| `expires_at` | `str \| None` | derived | `created_at + expires_in` seconds, same format, computed once at publication and never recomputed. `None` when no lifetime was requested. |
| `delete_token` | `str` | generated | 43 URL-safe chars from `secrets.token_urlsafe(32)`, drawn independently of `id`. Returned only in the publication response; never in a read response. |

### Caller-supplied input (publication)

| Input field | Type accepted | Rule | Violation |
|-------------|---------------|------|-----------|
| `content` | JSON string | present and a string; ≤ 65,536 UTF-8 bytes | missing / non-string → 400; oversize → 413 |
| `expires_in` | JSON integer or `null`, or absent | if present and not `null`: an integer (JSON `true`/`false` are rejected even though Python treats `bool` as `int`), `1 ≤ n ≤ 2_592_000` | 400 |
| any other field | any | ignored (FR-015) | — |
| body as a whole | JSON object | must decode as UTF-8 JSON and be an object, not a list/number/string/`null` | 400 |
| declared `Content-Length` | integer | if > 394,240 → reject before reading; unparseable → 400 | 413 / 400 |

Note on `expires_in` validation: the check is `type(v) is int` (not `isinstance`), because
`isinstance(True, int)` is true in Python and `{"expires_in": true}` must be a 400. A numeric string
such as `"3600"` is likewise a 400 — no coercion (Constitution Principle II).

### Lifecycle

```text
                 POST /pastes (valid)
   (nonexistent) ────────────────────────▶ LIVE
                                            │
                      now >= expires_at     │   DELETE with correct token
                 ┌──────────────────────────┴───────────────────────┐
                 ▼                                                  ▼
             EXPIRED                                            DELETED
   (file may remain on disk;                        (file unlinked; permanent,
    indistinguishable from                           survives restart)
    nonexistent to every caller)
```

- **LIVE** → readable (`GET`, `GET /raw`), deletable with the correct token (403 without it).
- **EXPIRED** → every access path reports 404, including a delete presenting the correct token
  (FR-027, US2 scenario 3). No transition out of this state; the stored file is not reclaimed
  (spec Assumption: expiry is evaluated lazily).
- **DELETED** → every access path reports 404, including a second delete with the same token.
- **DAMAGED** is not a state of a snippet but a property of a stored file: a file that cannot be
  read, decoded, or validated yields 500 for that identifier only, and does not affect any other
  snippet (FR-038).

Transitions are evaluated per request, never by a background process. There is no state field on
disk — state is a function of (file exists?, `expires_at` vs now).

## Storage location

| Property | Value |
|----------|-------|
| Identity | The `--data DIR` path given at startup |
| Created | `mkdir(parents=True, exist_ok=True)` at startup, before the ready line |
| Validated | A probe file is created and removed inside it; failure → stderr + exit 1 (FR-005) |
| Contents | One `<id>.json` per live-or-expired snippet, plus transient `.tmp-*` files during publication |
| Scanned at startup | Never (FR-038, SC-007) |
| Source of truth | Sole; no in-memory index, no cache |

## Requirement to test map

Every functional requirement maps to at least one `pytest` test that names its identifier in the
test name or docstring (Constitution Principle III, SC-008). Test module layout is in
[plan.md](./plan.md#source-code-repository-root).

| FR | Test module | Test(s) |
|----|-------------|---------|
| FR-001 | `test_cli.py` | `test_fr001_serve_accepts_port_and_data` |
| FR-002 | `test_cli.py` | `test_fr002_listens_on_loopback_only` |
| FR-003 | `test_cli.py` | `test_fr003_creates_missing_data_dir_including_parents` |
| FR-004 | `test_cli.py` | `test_fr004_ready_line_printed_once_after_socket_accepts` |
| FR-005 | `test_cli.py` | `test_fr005_port_in_use_exits_nonzero_without_ready_line`, `test_fr005_unwritable_data_dir_exits_nonzero` |
| FR-006 | `test_cli.py` | `test_fr006_rejects_missing_port`, `test_fr006_rejects_non_numeric_port`, `test_fr006_rejects_out_of_range_port`, `test_fr006_rejects_missing_data` |
| FR-007 | `test_publish.py` | `test_fr007_publish_with_content_creates_paste` |
| FR-008 | `test_publish.py` | `test_fr008_missing_content_is_400`, `test_fr008_non_string_content_is_400` (parametrised over number, bool, list, object, null) |
| FR-009 | `test_publish.py` | `test_fr009_content_at_65536_bytes_accepted`, `test_fr009_content_at_65537_bytes_is_413`, `test_fr009_limit_measured_in_encoded_bytes` |
| FR-010 | `test_publish.py` | `test_fr010_expires_in_accepts_1_and_2592000`, `test_fr010_rejects_zero_negative_over_max_fractional_string_and_bool` |
| FR-011 | `test_publish.py` | `test_fr011_absent_expires_in_means_no_expiry`, `test_fr011_null_expires_in_means_no_expiry` |
| FR-012 | `test_publish.py` | `test_fr012_response_is_201_with_id_delete_token_and_url` |
| FR-013 | `test_publish.py` | `test_fr013_ids_are_unique_across_many_publications`, `test_fr013_id_entropy_and_alphabet` |
| FR-014 | `test_publish.py`, `test_read.py` | `test_fr014_delete_token_not_derivable_from_id`, `test_fr014_delete_token_absent_from_read_response` |
| FR-015 | `test_publish.py` | `test_fr015_unknown_fields_are_ignored` |
| FR-016 | `test_publish.py` | `test_fr016_malformed_json_is_400`, `test_fr016_non_object_json_is_400` (parametrised over list, number, string, null) |
| FR-017 | `test_read.py` | `test_fr017_get_returns_id_content_created_at_expires_at` |
| FR-018 | `test_read.py` | `test_fr018_expires_at_is_null_when_no_lifetime` |
| FR-019 | `test_read.py` | `test_fr019_timestamps_are_iso8601_utc_second_precision` |
| FR-020 | `test_read.py` | `test_fr020_raw_returns_exact_content_as_utf8_plain_text` |
| FR-021 | `test_read.py` | `test_fr021_roundtrip_fidelity` (parametrised: empty, newlines, non-ASCII, emoji, max-size) |
| FR-022 | `test_delete.py` | `test_fr022_delete_with_token_removes_paste` |
| FR-023 | `test_delete.py` | `test_fr023_delete_responds_204_and_paste_is_then_404` |
| FR-024 | `test_delete.py` | `test_fr024_missing_token_is_403_and_paste_survives`, `test_fr024_wrong_token_is_403_and_paste_survives` |
| FR-025 | `test_delete.py` | `test_fr025_token_compared_with_compare_digest` (monkeypatches `secrets.compare_digest` and asserts the comparison goes through it) |
| FR-026 | `test_delete.py` | `test_fr026_unknown_id_is_404_regardless_of_token`, `test_fr026_expired_paste_delete_is_404_not_403`, `test_fr026_second_delete_is_404` |
| FR-027 | `test_expiry.py` | `test_fr027_expired_paste_is_404_on_get_raw_and_delete` |
| FR-028 | `test_expiry.py` | `test_fr028_expires_at_equals_created_at_plus_lifetime`, `test_fr028_expires_at_unchanged_by_later_reads` |
| FR-029 | `test_persistence.py` | `test_fr029_paste_readable_from_new_instance_on_same_dir` |
| FR-030 | `test_persistence.py` | `test_fr030_id_content_created_at_expires_at_token_survive_restart` |
| FR-031 | `test_persistence.py` | `test_fr031_deleted_paste_not_resurrected_by_restart` |
| FR-032 | `test_errors.py` | `test_fr032_every_error_status_carries_single_error_field` (parametrised over 400, 403, 404, 413, 500) |
| FR-033 | `test_errors.py` | `test_fr033_invalid_input_is_400` |
| FR-034 | `test_errors.py` | `test_fr034_oversize_content_is_413_not_400` |
| FR-035 | `test_errors.py` | `test_fr035_refused_delete_is_403` |
| FR-036 | `test_routing.py` | `test_fr036_undefined_paths_are_404` (root, `/pastes/<id>/extra`, `/pastes/<id>/text`), `test_fr036_unsupported_methods_are_404` (parametrised over PUT, PATCH, HEAD, OPTIONS, DELETE on `/pastes`, GET on `/pastes`) |
| FR-037 | `test_errors.py` | `test_fr037_no_specified_input_produces_an_undefined_response` (sweeps every invalid input the spec enumerates and asserts the status is one of 400/403/404/413 and the body parses) |
| FR-038 | `test_damaged_storage.py` | `test_fr038_damaged_record_is_500_not_404`, `test_fr038_diagnostic_names_the_paste_on_stderr`, `test_fr038_other_pastes_unaffected`, `test_fr038_startup_does_not_scan_storage` |
| FR-039 | `test_damaged_storage.py` | `test_fr039_damaged_record_500_body_has_error_field` (parametrised: truncated, invalid JSON, wrong shape, bad timestamp) |
| FR-040 | `test_publish.py` | `test_fr040_declared_length_over_bound_is_413_without_reading_body`, `test_fr040_understated_length_cannot_exceed_read_ceiling` |
| FR-041 | `test_publish.py` | `test_fr041_content_type_is_ignored` (parametrised: absent, `application/json`, `text/plain`, nonsense) |
| FR-042 | `test_concurrency.py` | `test_fr042_quiet_client_does_not_block_other_requests`, `test_fr042_overlapping_requests_are_served_concurrently` |
| FR-043 | `test_concurrency.py` | `test_fr043_reader_never_sees_partially_written_paste`, `test_fr043_delete_during_read_yields_whole_or_404` |
| FR-044 | `test_cli.py` | `test_fr044_stdout_contains_only_the_ready_line`, `test_fr044_stderr_silent_across_valid_and_invalid_traffic` |

Coverage: 44 of 44 functional requirements. Success criteria SC-001…SC-010 are each covered by the
tests above plus the scenarios in [quickstart.md](./quickstart.md); SC-008 is satisfied by this table.
