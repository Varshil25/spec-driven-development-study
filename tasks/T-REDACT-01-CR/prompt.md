This repository already contains `logredact`, a command-line tool that removes personal data from log files. Read the existing code and any documentation in the repository before changing it. Change it as follows; everything else it does now must keep working exactly as it does.

1. **Phone numbers.** Phone numbers in international format, a `+` followed by 8 to 15 digits such as `+14155552671`, become `[PHONE]`. With `--count`, the summary on standard error becomes `emails=N ips=N cards=N phones=N`.

2. **Output folder.** A new option `--out-dir DIR` writes the redacted lines of each FILE to a file with the same name in DIR (the file's name only, without its directories) instead of to standard output. DIR is created, with any missing parent directories, if it does not exist, and an existing file of that name in DIR is replaced. When every FILE has been processed, the tool prints `wrote N files` to standard output, where N is the number of output files written. A FILE that cannot be read is handled as it is now: an error message naming the file on standard error, and exit status 2.

Examples, for files `app.log` (containing `user jane@example.com`) and `web.log` (containing `GET / from 10.0.0.7`):

```
$ printf 'call +14155552671 now\n' | python -m logredact
call [PHONE] now

$ printf 'a@b.io +442071838750\n' | python -m logredact --count
[EMAIL] [PHONE]
emails=1 ips=0 cards=0 phones=1        <- on standard error

$ python -m logredact --out-dir clean app.log web.log
wrote 2 files
```
