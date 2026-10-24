Build a command-line tool that removes personal data from log files before they are shared.

Run it as `python -m logredact [--count] [FILE ...]`. It reads each FILE in the order given, or standard input when no FILE is given, and writes every line to standard output with the following replaced:

- Email addresses, such as `jane.doe+test@mail.example.com`, become `[EMAIL]`.
- IPv4 addresses (four dot-separated numbers, each from 0 to 255, such as `192.168.0.10`) become `[IP]`. Something like `999.1.1.1` is not an IP address and is left alone.
- Payment card numbers become `[CARD]`. A card number is 13 to 19 digits, optionally written in groups separated by single spaces or single hyphens (for example `4111 1111 1111 1111` or `4111-1111-1111-1111`), that passes the Luhn checksum. Digit sequences that fail the Luhn check are left alone.

Everything else on a line is output unchanged, and lines with nothing to redact are output exactly as they were.

With `--count`, after all output has been written the tool prints a summary to standard error in the form `emails=N ips=N cards=N`.

If a FILE cannot be read, the tool prints an error message naming the file to standard error and exits with status 2. Otherwise it exits with status 0.

Use Python 3.11 or newer and the standard library only. Put the code in a package named `logredact` under `src/`, so that it runs with `python -m logredact` when `src/` is on `PYTHONPATH`.

Examples:

```
$ printf 'user jane@example.com from 10.0.0.7\n' | python -m logredact
user [EMAIL] from [IP]

$ printf 'paid with 4111 1111 1111 1111, ref 1234567890123\n' | python -m logredact
paid with [CARD], ref 1234567890123

$ printf 'a@b.io 1.2.3.4\n' | python -m logredact --count
[EMAIL] [IP]
emails=1 ips=1 cards=0        <- on standard error
```
