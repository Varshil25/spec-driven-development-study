This repository already contains `accounts`, a command-line tool that manages local user accounts with passwords in a single store file. Read the existing code and any documentation in the repository before changing it. Add password reset as described below; every existing command must keep working exactly as it does now.

- `python -m accounts --store PATH reset-token USERNAME [--ttl SECONDS]` creates a one-time password-reset token for the account and prints it on a line of its own to standard output; an administrator passes it on to the user. The token is valid for SECONDS seconds, 900 (15 minutes) by default.
- `python -m accounts --store PATH reset USERNAME` reads the token and then the new password from standard input, one per line. If the token is valid, it sets the new password and prints `password reset`. A token can be used only once. A wrong, already used or expired token prints `invalid token` to standard error and exits with status 1. A new password shorter than 12 characters is rejected with exit status 2, and the token can still be used afterwards.
- For both commands, a username that does not exist fails with exit status 3.

Successful commands exit with status 0.

Examples, with a store `users.db`:

```
$ printf 'correct horse battery\n' | python -m accounts --store users.db register alice
registered alice
$ python -m accounts --store users.db reset-token alice
(a token on one line, for example 3Hk2...)
$ printf 'not-the-token\nbrand new password\n' | python -m accounts --store users.db reset alice
invalid token        <- on standard error; exit status 1
$ python -m accounts --store users.db reset-token nobody
(an error message on standard error; exit status 3)
```
