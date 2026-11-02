This repository already contains `tarx`, a command-line tool for listing and extracting tar archives. Read the existing code and any documentation in the repository before changing it. Add a third command as described below; `list` and `extract` must keep working exactly as they do now.

- `python -m tarx create ARCHIVE PATH... [--overwrite]` creates a tar archive at ARCHIVE containing each PATH. A PATH is a file or a directory given relative to the current directory, such as `notes.txt` or `photos`; a directory is added together with everything inside it. Members are named by their relative path, so `python -m tarx create photos.tar.gz photos` produces members such as `photos/a.jpg`. If ARCHIVE ends in `.tar.gz` or `.tgz` the archive is gzip-compressed; otherwise it is a plain tar archive. When it finishes it prints `created ARCHIVE with N files` to standard output, where N is the number of regular files added.

If ARCHIVE already exists, `create` fails with exit status 3 and an error message on standard error, unless `--overwrite` is given, in which case the archive is replaced. If a PATH does not exist, it prints an error message naming that PATH to standard error, exits with status 2, and creates no archive. Archives made by `create` must be readable by the existing `list` and `extract` commands. Successful commands exit with status 0.

Examples, in a directory that contains a folder `photos` with the files `a.jpg` and `b.jpg`:

```
$ python -m tarx create photos.tar.gz photos
created photos.tar.gz with 2 files

$ python -m tarx create photos.tar.gz photos
(an error message on standard error; exit status 3)

$ python -m tarx create other.tar missing-folder
(an error message on standard error; exit status 2)
```
