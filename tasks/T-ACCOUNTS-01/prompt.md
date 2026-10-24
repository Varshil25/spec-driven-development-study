Build a command-line tool that manages local user accounts with passwords, kept in a single store file.

Run it as `python -m accounts --store PATH COMMAND USERNAME`. The store is the file at PATH; it is created on first use and persists between runs. Passwords are never passed as command-line arguments: each command reads the passwords it needs from standard input, one per line.

Commands:

- `register USERNAME` reads a password and creates the account, printing `registered USERNAME`. A username is 3 to 32 characters long and uses only letters, digits and underscores. A password must be at least 12 characters long. An invalid username or a too-short password is rejected with exit status 2. Registering a username that already exists fails with exit status 3.
- `login USERNAME` reads a password. If it is correct, it prints `ok`. Otherwise it prints `invalid credentials` to standard error and exits with status 1.
- After 5 failed login attempts an account is locked. Logging in to a locked account prints `account locked` to standard error and exits with status 4, even if the password is correct.
- `unlock USERNAME` unlocks the account and resets its count of failed logins.
- `passwd USERNAME` reads the current password and then the new password, and changes the password. A wrong current password prints `invalid credentials` to standard error and exits with status 1. A new password shorter than 12 characters is rejected with exit status 2.
- `delete USERNAME` reads the current password and deletes the account. A wrong password prints `invalid credentials` to standard error and exits with status 1.

For `unlock`, `passwd` and `delete`, a username that does not exist fails with exit status 3. Successful commands exit with status 0.

Use Python 3.11 or newer and the standard library only. Put the code in a package named `accounts` under `src/`, so that it runs with `python -m accounts` when `src/` is on `PYTHONPATH`.

Examples:

```
$ printf 'correct horse battery\n' | python -m accounts --store users.db register alice
registered alice
$ printf 'correct horse battery\n' | python -m accounts --store users.db login alice
ok
$ printf 'wrong password!!\n' | python -m accounts --store users.db login alice
invalid credentials        <- on standard error; exit status 1
$ printf 'short\n' | python -m accounts --store users.db register bob
(an error message on standard error; exit status 2)
```
