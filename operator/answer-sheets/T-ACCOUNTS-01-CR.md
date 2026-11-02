# T-ACCOUNTS-01-CR: answer sheet (change request)

Read `README.md` in this folder first. Reply verbatim. The entries of
`T-ACCOUNTS-01.md` still apply to the existing commands.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | whether `reset-token` or `reset` work on a locked account | Yes, both work on a locked account. A successful reset also unlocks the account and clears its count of failed logins. |
| I2 | what happens to an earlier token when a new one is created | Only the newest token for an account works. Creating a new token cancels any earlier one. |
| I3 | whether changing the password with `passwd` affects an outstanding reset token | Yes. After a successful `passwd`, any reset token created before it no longer works. |
