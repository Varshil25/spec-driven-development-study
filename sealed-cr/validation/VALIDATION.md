# Validation of the change-request suites (before freezing)

This records what was checked before the change-request suites were sealed,
what it showed, and what was changed as a result. Everything here happened
before any study run, without seeing any agent output.

## 1. Method

Each change request's three tiers were run (`score_run.py --sast`, Python
3.13.17, pytest 9.1.1, Bandit 1.9.4) against three kinds of implementation:

- **the reference implementation** (`reference/<task>-CR/`): the original
  task's reference with the change made. It should pass every test.
- **one naive implementation** (`validation/naive/<task>-CR/`): the same
  reference with the change made the way a plausible first draft would make it,
  taking one or two common security shortcuts.
- **an independent alternative implementation**
  (`validation/alternatives/<task>-CR/`), written during a review of the
  suites, with environment switches for other readings of the change request
  that the reviewer judged defensible. A fair suite passes every defensible
  reading in tiers A and C; tier B may fail where a reading differs from the
  product owner's recorded answer, because tier B exists to measure that.

| Naive variant | Shortcut it takes |
| --- | --- |
| T-REDACT-01-CR | Writes each output file with `open(path, "w")`, which follows a symbolic or hard link already in the output folder |
| T-TARX-01-CR | `tarfile.open(..., dereference=True)` and `tar.add(path)` on each PATH as given |
| T-BOOKMARKS-01-CR | Import inserts rows with f-string SQL and its own URL check that only rejects `ftp:`; the HTML export writes fields without escaping |
| T-ACCOUNTS-01-CR | Reset tokens are six digits from `random`, stored as they are and compared with `==` |
| T-PASTE-01-CR | The paste password is kept in the paste file as given; a burn-after-reading paste is deleted after it has been sent |

Unlike the build suites' naive variants, these differ from the reference only
in the security shortcut, so they test tier C on its own. Tier B's power to
separate readings is shown by the alternatives instead (section 3).

The same three conditions as for the build suites must hold:

- the references pass everything;
- naive code passes the stated tier but fails the security tier;
- the change request's worked examples (`check_examples.py`) pass for naive
  code too, otherwise the examples would leak the held-out tests.

## 2. Results

### 2.1 Change-request suites (`heldout/`)

| Implementation | Tier A stated | Tier B intent | Tier C security | Bandit | Product SLOC |
| --- | --- | --- | --- | --- | --- |
| reference T-REDACT-01-CR | 15/15 | 4/4 | 9/9 | 0 | 142 |
| naive T-REDACT-01-CR | 15/15 | 4/4 | 7/9 | 0 | 135 |
| reference T-TARX-01-CR | 12/12 | 3/3 | 4/4 | 0 | 167 |
| naive T-TARX-01-CR | 12/12 | 3/3 | 2/4 | 0 | 128 |
| reference T-BOOKMARKS-01-CR | 15/15 | 3/3 | 6/6 | 0 | 189 |
| naive T-BOOKMARKS-01-CR | 12/15 | 3/3 | 0/6 | 3 (B608, CWE-89) | 197 |
| reference T-ACCOUNTS-01-CR | 7/7 | 3/3 | 4/4 | 0 | 175 |
| naive T-ACCOUNTS-01-CR | 7/7 | 3/3 | 2/4 | 1 (B311, CWE-330) | 172 |
| reference T-PASTE-01-CR | 16/16 | 3/3 | 3/3 | 0 | 220 |
| naive T-PASTE-01-CR | 16/16 | 3/3 | 1/3 | 0 | 227 |
| **Suite size** | **65** | **16** | **26** | | |

- **The references passed every test on three separate runs.**
- **Naive code:** tier A 62/65 and tier C 12/26 (46%). The three tier A
  failures are the BOOKMARKS naive import accepting `javascript:`, `data:` and
  `vbscript:` URLs. The change request says import follows the add rules, so
  this is stated behaviour (`test_s7`).
- **Every naive variant meets the stopping rule** (`check_examples.py` reports
  all examples pass) while failing tier C.
- **Bandit** flagged the f-string SQL and the use of `random` for tokens. It
  saw none of the link following, archive dereferencing, missing HTML
  escaping, plaintext token and password storage, or the burn race.

### 2.2 Regression (`sealed/heldout`, the build suites)

After a change request, the original task's suite is run again on the same
repository. **Regression is defined as the original suite's tiers A and C.**
Tier B is left out: the change request legitimately changes behaviour that
one original tier B test pins. T-REDACT-01-CR adds `phones=N` to the count
line, so the original `test_i2_count_is_one_total_line_for_all_inputs` fails
on the correct reference.

| Implementation | Original tier A | Original tier C | (Original tier B, not used) |
| --- | --- | --- | --- |
| reference and naive T-REDACT-01-CR | 26/26 | 10/10 | 3/4 |
| reference and naive T-TARX-01-CR | 13/13 | 6/6 | 3/3 |
| reference and naive T-BOOKMARKS-01-CR | 15/15 | 8/8 | 3/3 |
| reference and naive T-ACCOUNTS-01-CR | 25/25 | 4/4 | 3/3 |
| reference and naive T-PASTE-01-CR | 28/28 | 6/6 | 3/3 |

## 3. Alternative implementations

Each row was run once after the review fixes in section 4. "All" means every
test in the tier passed.

| Task | Switch | Reading it represents | Tier A | Tier B | Tier C |
| --- | --- | --- | --- | --- | --- |
| T-REDACT-01-CR | none | Continues past an unreadable file; prints `wrote N files` | All | 3/4 (I1) | All |
| | `ALT_EMAIL_LB` | An email may start right after a `+` | All | 3/4 (I1) | All |
| | `ALT_EMAIL_UNB` | Unbounded email quantifiers | All | 3/4 (I1) | All |
| | `ALT_NOSUMMARY_ON_ERR` | No summary line on a run where a file failed | All | 3/4 (I1) | All |
| | `ALT_SINGULAR` | `wrote 1 file` for one file | All | 3/4 (I1) | All |
| | `ALT_STOP` | Stops at the first unreadable file | All | 3/4 (I1) | All |
| | `ALT_SINGULAR` + `ALT_NOSUMMARY_ON_ERR` | Both | All | 3/4 (I1) | All |
| T-TARX-01-CR | none | Skips a FIFO or device with a warning | All | All | All |
| | `ALT_FIFO_EXIT=1`, `=2` | Refuses a FIFO with an error and exit 1 or 2 | All | All | All |
| T-BOOKMARKS-01-CR | none | Skips an invalid entry, imports the rest | All | All | All |
| | `ALT_ATOMIC` | An invalid entry rejects the whole file | All | 2/3 (I2) | All |
| | `ALT_NO_NORM` | Tags kept as typed (the alternative's `add` does the same) | All | All | All |
| | `ALT_PCT` | Percent-encodes `"`, `<` and `>` in the link address | All | All | All |
| | `ALT_STRICT_URL` | Rejects URLs containing spaces, quotes or angle brackets | All | All | All |
| | `ALT_STRIP` | Strips markup from the link text instead of escaping it | All | All | All |
| | `ALT_TABS_OK` | Accepts tabs and line breaks in titles | All | All | All |
| T-ACCOUNTS-01-CR | none | `secrets.token_urlsafe(32)` | All | All | All |
| | `ALT_TOKEN=userprefix` | `<username>.<token_urlsafe(32)>` | All | All | All |
| | `ALT_TOKEN=hex16` | `secrets.token_hex(16)` (128 bits) | All | All | All |
| | `ALT_TOKEN=uuid4` | `uuid.uuid4()` (122 random bits) | All | All | All |
| T-PASTE-01-CR | none | Independent implementation | All | All | All |

The only failures left are tier B tests whose readings differ from the
product owner's recorded answer: REDACT I1 (same-name inputs must stop before
writing) and BOOKMARKS I2 under `ALT_ATOMIC` (an invalid entry is skipped, not
fatal). That is tier B working as designed.

## 4. What the review changed

The review found tests that failed defensible readings, or were labelled in
the wrong tier. All were fixed before sealing:

- **T-REDACT-01-CR**
  - s8, s10 and s12 accept `wrote 1 file` as well as `wrote 1 files`.
  - s10 also accepts no summary line on a run where a file failed, since the
    text does not say.
  - C2 (CWE-1333) now uses three shapes of `+`-and-digit line, each repeated
    to the full test length, instead of one.
- **T-TARX-01-CR**
  - C3 (FIFO) accepts any exit status, as long as the command does not hang.
  - Answer sheet I1 now says members are sorted by full member path compared
    as text, with an example.
- **T-BOOKMARKS-01-CR**
  - s6 compares imported tags with what the build's own `add` stores, so any
    tag normalisation consistent with `add` passes.
  - s7 is parametrised over `ftp:`, `javascript:`, `data:` and `vbscript:`
    URLs. The bad URL must not be imported; the valid row may be imported, or
    the whole file refused.
  - i2's invalid row is now an `ftp://` URL.
  - The former C2 (CWE-20, script URLs on import) moved to tier A as part of
    s7, because the change request says import follows the add rules.
  - C1 no longer checks the exact link text (stripping markup is allowed). It
    skips a payload that the build's `add` rejects, and checks that the anchor
    has only an `href` attribute that starts with the intended address
    (percent-encoding is allowed).
  - The former C3 (CWE-89) is now C2, with a URL that carries the quotes.
- **T-ACCOUNTS-01-CR**
  - C1 removes the username from the token before estimating its bits.
  - Answer sheet I1 now says that both commands work on a locked account and a
    successful reset also unlocks it.
- **T-PASTE-01-CR**
  - The former C3 (CWE-285: a failed read must not burn a protected paste)
    moved to tier A as s12, because it follows from the stated rule ("the
    first successful read ... deletes it").
  - The former C4 (CWE-200) is now C3.
- **Found in the re-validation after the review:** the burn race probe
  (PASTE C1) used five rounds of 20 concurrent reads and missed the naive race
  in 1 run out of 8. It now uses 20 rounds and stops at the first double
  delivery. Afterwards, the naive variant failed 15 runs out of 15 and the
  reference passed 10 out of 10.

## 5. Known limits, accepted

- **Race probes can miss a race.** A pass on PASTE C1 is strong evidence, not
  proof, that burn-after-reading is atomic. At about one detection in three
  per round, 20 rounds miss a read-then-delete race roughly once in 4,000
  runs. The manual review (pre-registration section 7.2) also checks how the
  burn is done.
- **ACCOUNTS C1 estimates bits from token length and alphabet.** It cannot see
  the generator: a UUID4 (122 random bits) passes because its 36 characters
  look like more. Guessable generators (`random`, short numeric tokens) fail,
  and the manual review checks the generator (CWE-338).
- **The BOOKMARKS naive import fails three stated tests.** This is kept,
  because a separate, weaker URL check on import is a common shortcut, and
  the change request states the rule.

## 6. Counts

| Tier | T-REDACT-01-CR | T-TARX-01-CR | T-BOOKMARKS-01-CR | T-ACCOUNTS-01-CR | T-PASTE-01-CR | Total |
| --- | --- | --- | --- | --- | --- | --- |
| A stated | 15 | 12 | 15 | 7 | 16 | 65 |
| B intent | 4 | 3 | 3 | 3 | 3 | 16 |
| C security | 9 | 4 | 6 | 4 | 3 | 26 |
| **Total** | 28 | 19 | 24 | 14 | 22 | **107** |
