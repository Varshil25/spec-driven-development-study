# T-ACCOUNTS-01: answer sheet

Read `README.md` in this folder first. Reply verbatim.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | whether usernames are case-sensitive | Usernames are case-insensitive: `Alice` and `alice` are the same account. Show the username as it was first registered. |
| I2 | whether a successful login resets the failed-login count | Yes. Only failed attempts since the last successful login count towards the lock. |
| I3 | whether `passwd` or `delete` work on a locked account | Not allowed. They fail with `account locked` on standard error and exit status 4, even with the correct password. |
