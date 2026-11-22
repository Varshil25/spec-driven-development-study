"""bookmarks reference implementation.

Safety design (why the probes in test_security.py pass):
  * Every SQL statement uses ? placeholders; user text never becomes SQL
    (CWE-89).
  * Search is a plain substring test done in Python, so % and _ in the
    search text are literal characters, not LIKE wildcards (CWE-155).
  * CSV cells that a spreadsheet would treat as a formula are prefixed with a
    single quote on export (CWE-1236).
"""

import argparse
import csv
import json
import sqlite3
import sys

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookmarks (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    url   TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bookmark_tags (
    bookmark_id INTEGER NOT NULL REFERENCES bookmarks(id) ON DELETE CASCADE,
    tag         TEXT NOT NULL,
    PRIMARY KEY (bookmark_id, tag)
);
"""

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class UsageError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def connect(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def normalise_tags(raw):
    if not raw:
        return []
    return sorted({t.strip().lower() for t in raw.split(",") if t.strip()})


def fetch_all(conn):
    rows = conn.execute("SELECT id, url, title FROM bookmarks ORDER BY id").fetchall()
    tags = {}
    for bid, tag in conn.execute("SELECT bookmark_id, tag FROM bookmark_tags"):
        tags.setdefault(bid, []).append(tag)
    return [(bid, url, title, sorted(tags.get(bid, []))) for bid, url, title in rows]


def line(row):
    bid, url, title, tags = row
    return "%d\t%s\t%s\t%s" % (bid, url, title, ",".join(tags))


def cmd_add(conn, args):
    url = args.url
    if not (url.startswith("http://") or url.startswith("https://")):
        raise UsageError(2, "URL must start with http:// or https://")
    title = args.title or ""
    if any(ch in title for ch in "\t\r\n"):
        raise UsageError(2, "title may not contain tabs or line breaks")
    existing = conn.execute("SELECT id FROM bookmarks WHERE url = ?", (url,)).fetchone()
    if existing:
        print(existing[0])
        return 0
    with conn:
        cur = conn.execute("INSERT INTO bookmarks (url, title) VALUES (?, ?)", (url, title))
        bid = cur.lastrowid
        conn.executemany("INSERT INTO bookmark_tags (bookmark_id, tag) VALUES (?, ?)",
                         [(bid, t) for t in normalise_tags(args.tags)])
    print(bid)
    return 0


def cmd_list(conn, args):
    wanted = args.tag.strip().lower() if args.tag is not None else None
    for row in fetch_all(conn):
        if wanted is None or wanted in row[3]:
            print(line(row))
    return 0


def cmd_search(conn, args):
    needle = args.text.casefold()
    for row in fetch_all(conn):
        if needle in row[1].casefold() or needle in row[2].casefold():
            print(line(row))
    return 0


def cmd_delete(conn, args):
    with conn:
        cur = conn.execute("DELETE FROM bookmarks WHERE id = ?", (args.id,))
    if cur.rowcount == 0:
        raise UsageError(3, "no bookmark with id %d" % args.id)
    return 0


def neutralise(cell):
    cell = str(cell)
    return "'" + cell if cell.startswith(FORMULA_PREFIXES) else cell


def cmd_export(conn, args):
    rows = fetch_all(conn)
    if args.format == "json":
        data = [{"id": bid, "url": url, "title": title, "tags": tags}
                for bid, url, title, tags in rows]
        print(json.dumps(data, indent=2))
        return 0
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["id", "url", "title", "tags"])
    for bid, url, title, tags in rows:
        writer.writerow([bid, neutralise(url), neutralise(title), neutralise(",".join(tags))])
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bookmarks")
    parser.add_argument("--db", default="bookmarks.db")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("add")
    p.add_argument("url")
    p.add_argument("--title", default="")
    p.add_argument("--tags", default="")
    p = sub.add_parser("list")
    p.add_argument("--tag", default=None)
    p = sub.add_parser("search")
    p.add_argument("text")
    p = sub.add_parser("delete")
    p.add_argument("id", type=int)
    p = sub.add_parser("export")
    p.add_argument("--format", choices=["csv", "json"], required=True)
    args = parser.parse_args(argv)

    handlers = {"add": cmd_add, "list": cmd_list, "search": cmd_search,
                "delete": cmd_delete, "export": cmd_export}
    try:
        conn = connect(args.db)
    except sqlite3.Error as exc:
        print("bookmarks: cannot open database %s: %s" % (args.db, exc), file=sys.stderr)
        return 1
    try:
        return handlers[args.command](conn, args)
    except UsageError as exc:
        print("bookmarks: %s" % exc, file=sys.stderr)
        return exc.code
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
