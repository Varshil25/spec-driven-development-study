# T-LOGIN-01 (practice task, excluded from analysis): answer sheet

Read `README.md` in this folder first. Reply verbatim.

| Entry | The agent asks about... | Reply (verbatim) |
| --- | --- | --- |
| I1 | limiting repeated failed logins, lockout, brute force or rate limiting | After 5 failed attempts in a row for a username, refuse logins for that username for 15 minutes, even with the right password, with the same `Invalid username or password` response. |
| I2 | whether logging out should invalidate the token (server-side revocation, stateless JWT) | Yes. After logout that token must stop working, even if someone kept a copy of it. |
| I3 | whether usernames are case-sensitive | Usernames are case-insensitive: `Alice` and `alice` are the same account. Show the username as it was registered. |
| I4 | what `GET /login` should do for someone who is already logged in | Send them straight to the dashboard: `303` with `Location: /dashboard`. |
