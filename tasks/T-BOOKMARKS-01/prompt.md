Build a command-line bookmark manager that stores bookmarks in an SQLite database.

Run it as `python -m bookmarks [--db PATH] COMMAND ...`. The database is the file PATH, or `bookmarks.db` in the current directory when `--db` is not given. It is created if it does not exist, and bookmarks persist between runs.

Commands:

- `add URL [--title TITLE] [--tags TAGS]` adds a bookmark and prints its numeric id. Ids start at 1 and increase. The URL must start with `http://` or `https://`; anything else is rejected with an error message on standard error and exit status 2. TITLE defaults to an empty string. TAGS is a comma-separated list such as `python,cli`.
- `list [--tag TAG]` prints all bookmarks, or only those that have the tag TAG, ordered by id.
- `search TEXT` prints the bookmarks whose title or URL contains TEXT, ignoring case, ordered by id.
- `delete ID` deletes the bookmark with that id. If there is no such bookmark it prints an error message on standard error and exits with status 3.
- `export --format csv` prints all bookmarks as CSV with the header row `id,url,title,tags`. `export --format json` prints them as a JSON array of objects with the keys `id` (a number), `url`, `title` and `tags` (a list of strings).

`list` and `search` print one bookmark per line as four tab-separated fields: the id, the URL, the title, and the bookmark's tags joined with commas in alphabetical order. In CSV output, the tags field also holds the tags joined with commas in alphabetical order.

Successful commands exit with status 0.

Use Python 3.11 or newer and the standard library only (`sqlite3` is part of it). Put the code in a package named `bookmarks` under `src/`, so that it runs with `python -m bookmarks` when `src/` is on `PYTHONPATH`.

Examples (`<TAB>` stands for a tab character):

```
$ python -m bookmarks --db b.db add https://docs.python.org --title "Python docs" --tags python,docs
1
$ python -m bookmarks --db b.db add https://example.com
2
$ python -m bookmarks --db b.db list
1<TAB>https://docs.python.org<TAB>Python docs<TAB>docs,python
2<TAB>https://example.com<TAB><TAB>
$ python -m bookmarks --db b.db search PYTHON
1<TAB>https://docs.python.org<TAB>Python docs<TAB>docs,python
$ python -m bookmarks --db b.db add ftp://example.com
(an error message on standard error; exit status 2)
```
