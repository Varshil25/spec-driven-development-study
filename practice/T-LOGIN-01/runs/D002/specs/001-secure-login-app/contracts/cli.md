# Contract: Command-Line Interface

**Feature**: `001-secure-login-app` | **Plan**: [../plan.md](../plan.md)

Run as `python -m loginapp …`, with `src/` on `PYTHONPATH` (FR-032).

- The command names, arguments, exit statuses and the two stdout lines (`added USERNAME`, `listening on 127.0.0.1:PORT`) come from the product owner and are fixed.
- The wording of the stderr messages is set by this plan. Tests check the parts each FR requires: the bad value, the rule or the variable named, and that no secret appears.

## Exit statuses

| Status | Meaning |
|--------|---------|
| 0 | Success (`adduser`) |
| 1 | Problem with the environment or a file: secret unset or empty, accounts file unreadable, invalid or not writable, port in use, or the server could not start. |
| 2 | Invalid usage or input: unknown or missing command or argument, invalid username, invalid password, port out of range. |
| 3 | `adduser`: the username already exists. |
| 130 | `serve` was stopped with Ctrl+C. The spec does not require a status for this. |

- Every error is written to **stderr**, as `loginapp: error: <message>`, or as argparse's usage block for usage errors.
- Nothing is written to **stdout** unless the command succeeds.
- A value the user supplied appears in a message `repr()`-quoted, for example `'al-ice'`.
- No message ever contains a password, a hash, a token or the secret (FR-029).
- An expected error never produces a traceback (SC-007).

## Global usage (FR-007)

```text
python -m loginapp COMMAND ...
COMMAND is one of: adduser, serve
```

- `argparse` with `allow_abbrev=False` and `add_help=False` on the main parser and both subcommands.
  - So a shortened name like `addu` or `--use` is refused, and `-h` / `--help` are unrecognised arguments.
  - The spec defines no help option, and Principle IV says not to add one.
- These cases write a usage message to stderr and exit **2**:
  - no command;
  - an unknown command;
  - a missing required argument;
  - an unrecognised argument;
  - an option given twice, such as `--users a --users b`. A custom action refuses this; argparse would otherwise keep the last value silently.
- These forms are accepted: `--users=FILE`, `--port=PORT`, and options before or after the `USERNAME` positional.

## `adduser`

```text
python -m loginapp adduser USERNAME --users FILE
stdin: one line, the password
```

### Order of checks (FR-004)

The first failure decides the exit status:

| # | Check | On failure: stderr | Exit |
|---|-------|--------------------|------|
| 1 | Arguments (FR-007) | argparse usage + `error: …` | 2 |
| 2 | Username matches `^[A-Za-z0-9_]{3,32}$` (FR-002) | `loginapp: error: invalid username 'al-ice': must be 3 to 32 characters, each an ASCII letter, digit or underscore` | 2 |
| 3 | Password: read first stdin line as bytes, strip one `\n` or `\r\n`, decode UTF-8 strictly, require ≥ 12 characters (FR-003) | `loginapp: error: invalid password: must be at least 12 characters of UTF-8 text` | 2 |
| 4 | Read FILE. A missing file counts as no accounts (FR-007). | `loginapp: error: cannot read accounts file 'users.json': <reason>` or `loginapp: error: invalid accounts file 'users.json': <rule broken>` | 1 |
| 5 | USERNAME not already in FILE, case-sensitive (FR-004) | `loginapp: error: username 'alice' already exists` | 3 |
| 6 | Write FILE through a temporary file and `os.replace` (FR-006, FR-007) | `loginapp: error: cannot write accounts file 'users.json': <reason>` | 1 |

### Notes

- Standard input is read only if check 2 passes. It is never echoed.
- An empty stdin (EOF at once) gives an empty password, so check 3 fails with status 2.
- Input with no final line ending is accepted as it is.
- The password message is the same whether the password is too short or not UTF-8. It states the 12-character minimum and never includes the input (FR-003).
- `<reason>` is the `strerror` of the `OSError`, for example `No such file or directory` or `Is a directory`. It never comes from the file's contents.
- `<rule broken>` names the rule that failed, never a field value (see [data-model.md](../data-model.md#validity-rules)).
- **On success**:
  - stdout gets exactly `added USERNAME\n`, and the exit status is 0;
  - FILE has mode `0600`;
  - every account that was in FILE before is still there, byte-for-byte;
  - nothing is written to stderr.

### Examples

```text
$ printf 'correct-horse-battery\n' | python -m loginapp adduser alice --users users.json
added alice                                                                # exit 0
$ printf 'correct-horse-battery\n' | python -m loginapp adduser alice --users users.json
loginapp: error: username 'alice' already exists                          # stderr, exit 3
$ printf 'short-pass1\n' | python -m loginapp adduser alice --users users.json
loginapp: error: invalid password: must be at least 12 characters of UTF-8 text   # exit 2 (FR-004 order)
```

## `serve`

```text
python -m loginapp serve --port PORT --users FILE
env: LOGINAPP_SECRET (required, non-empty)
```

### Order of startup checks (FR-010)

The first failure decides the exit status. None of these failures prints the `listening on` line.

| # | Check | On failure: stderr | Exit |
|---|-------|--------------------|------|
| 1 | Arguments, including PORT: 1–5 ASCII digits with a value of 1–65535 (FR-007, FR-010) | argparse usage + `error: argument --port: invalid port '0': must be a whole number from 1 to 65535` | 2 |
| 2 | `LOGINAPP_SECRET` set, non-empty, encodable as UTF-8 (FR-009) | `loginapp: error: LOGINAPP_SECRET is not set or is empty` (or `… is not valid UTF-8 text`) | 1 |
| 3 | FILE exists, is readable and valid (FR-010) | `loginapp: error: cannot read accounts file 'users.json': <reason>` or `loginapp: error: invalid accounts file 'users.json': <rule broken>` | 1 |
| 4 | Bind and listen on `127.0.0.1:PORT` (FR-008, FR-010) | `loginapp: error: cannot listen on 127.0.0.1:8000: <reason>` (for example `Address already in use`) | 1 |

- A PORT like `+8000`, ` 8000`, `8_000`, `08000x` or one using non-ASCII digits is refused at check 1.
- A PORT with leading zeros, such as `08000`, is 5 ASCII digits with a value of 8000, so it is accepted. The line then says `listening on 127.0.0.1:8000`, because PORT is printed as an integer.

### Ready line (FR-008)

When checks 1–4 pass, the socket is already listening. The program then writes `listening on 127.0.0.1:PORT\n` to stdout and flushes it at once (`print(..., flush=True)`), then starts serving.

### While running

- Requests are not logged.
- These events write one `loginapp: error: …` line (or block) to stderr:
  - an accounts file that cannot be read or is invalid during a sign-in (FR-011);
  - an unexpected exception (FR-031): exception type and traceback frames, without the exception message.
- Neither kind of message contains passwords, hashes, tokens or the secret (FR-029).

### Stopping

- Ctrl+C (SIGINT) closes the listening socket, writes `loginapp: stopped` to stderr and exits with status 130.
- Any other signal uses Python's default behaviour.
