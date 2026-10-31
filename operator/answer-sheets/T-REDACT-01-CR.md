# T-REDACT-01-CR: answer sheet (change request)

Read `README.md` in this folder first. Reply verbatim. The entries of
`T-REDACT-01.md` still apply to behaviour the change request does not touch.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | two input files with the same name (for example `a/app.log` and `b/app.log`) with `--out-dir` | Stop before writing anything: print an error naming the clashing file name and exit with status 3. |
| I2 | `--out-dir` when no FILE is given (standard input) | Reject it: print an error saying `--out-dir` needs at least one FILE, and exit with status 2. |
| I3 | a `+` number that would also pass as a card number | It is a phone number. Anything that starts with `+` and fits the phone rule is a phone number, never a card. |
| I4 | phone numbers written with spaces, hyphens or brackets, such as `+1 415 555 2671` | Only the compact form counts: `+` and the digits with nothing in between. Leave other forms unchanged. |
