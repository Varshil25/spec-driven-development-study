"""bookmarks reference implementation.

Safety design (why the probes in test_security.py pass):
  * Every SQL statement uses ? placeholders; user text never becomes SQL
    (CWE-89).
  * Search is a plain substring test done in Python, so % and _ in the
    search text are literal characters, not LIKE wildcards (CWE-155).
  * CSV cells that a spreadsheet would treat as a formula are prefixed with a
    single quote on export (CWE-1236).

Change request (T-BOOKMARKS-01-CR):
  * import goes through the same validation as add (validate_new), so a
    javascript: or data: URL in an import file is rejected exactly as add
    rejects it (CWE-20), and the same ? placeholders store every field
    (CWE-89).
  * HTML export escapes every URL, title and tag with html.escape(quote=True),
    so stored text can never become markup or an attribute (CWE-79).
"""

import argparse
import csv
import html
import json
import os
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
    if os.environ.get("ALT_NO_NORM"):
        return sorted({t for t in raw.split(",") if t})
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


def validate_new(url, title):
    if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
        raise UsageError(2, "URL must start with http:// or https://")
    if not isinstance(title, str):
        raise UsageError(2, "title must be text")
    if os.environ.get("ALT_STRICT_URL") and any(c in url for c in ' \t"<>'):
        raise UsageError(2, "URL contains characters that are not allowed")
    if not os.environ.get("ALT_TABS_OK") and any(ch in title for ch in "\t\r\n"):
        raise UsageError(2, "title may not contain tabs or line breaks")


def insert(conn, url, title, tags):
    """Add one bookmark; return (id, created)."""
    validate_new(url, title)
    existing = conn.execute("SELECT id FROM bookmarks WHERE url = ?", (url,)).fetchone()
    if existing:
        return existing[0], False
    with conn:
        cur = conn.execute("INSERT INTO bookmarks (url, title) VALUES (?, ?)", (url, title))
        bid = cur.lastrowid
        conn.executemany("INSERT INTO bookmark_tags (bookmark_id, tag) VALUES (?, ?)",
                         [(bid, t) for t in normalise_tags(tags)])
    return bid, True


def cmd_add(conn, args):
    bid, _ = insert(conn, args.url, args.title or "", args.tags)
    print(bid)
    return 0


def read_import(path, fmt):
    """Return a list of (url, title, tags) from an export-format file."""
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise UsageError(2, "cannot read %s: %s" % (path, exc))
    entries = []
    if fmt == "json":
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise UsageError(2, "%s is not valid JSON: %s" % (path, exc))
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise UsageError(2, "%s must hold a JSON array of objects" % path)
        for item in data:
            tags = item.get("tags", [])
            if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
                tags = None
            entries.append((item.get("url"), item.get("title", ""), tags))
        return entries
    rows = list(csv.reader(text.splitlines()))
    if not rows or [c.strip() for c in rows[0]] != ["id", "url", "title", "tags"]:
        raise UsageError(2, "%s must start with the header row id,url,title,tags" % path)
    for row in rows[1:]:
        if not row:
            continue
        if len(row) != 4:
            entries.append((None, None, None))
            continue
        entries.append((row[1], row[2], row[3].split(",") if row[3] else []))
    return entries


def cmd_import(conn, args):
    entries = read_import(args.file, args.format)
    added, problems = 0, 0
    if os.environ.get("ALT_ATOMIC"):
        for number, (url, title, tags) in enumerate(entries, 1):
            try:
                if tags is None:
                    raise UsageError(2, "tags must be a list of strings")
                validate_new(url, title if title is not None else "")
            except UsageError as exc:
                print("bookmarks: entry %d: %s; nothing imported" % (number, exc), file=sys.stderr)
                return 2
    for number, (url, title, tags) in enumerate(entries, 1):
        try:
            if tags is None:
                raise UsageError(2, "tags must be a list of strings")
            _, created = insert(conn, url, title if title is not None else "", ",".join(tags))
        except UsageError as exc:
            print("bookmarks: skipping entry %d: %s" % (number, exc), file=sys.stderr)
            problems += 1
            continue
        added += int(created)
    print("imported %d" % added)
    return 2 if problems else 0


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


HTML_HEAD = ("<!DOCTYPE html>\n<html>\n<head><meta charset=\"utf-8\"><title>Bookmarks</title></head>\n"
             "<body>\n<ul>")
HTML_TAIL = "</ul>\n</body>\n</html>"


def cmd_export(conn, args):
    rows = fetch_all(conn)
    if args.format == "html":
        print(HTML_HEAD)
        for bid, url, title, tags in rows:
            esc = lambda text: html.escape(text, quote=True)  # noqa: E731
            href = url.replace('"', "%22").replace("<", "%3C").replace(">", "%3E") if os.environ.get("ALT_PCT") else url
            shown = title or url
            if os.environ.get("ALT_STRIP"):
                import re as _re
                shown = _re.sub(r"<[^>]*>?", "", shown)
            print('<li><a href="%s">%s</a> <small>%s</small></li>'
                  % (esc(href), esc(shown), esc(",".join(tags))))
        print(HTML_TAIL)
        return 0
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
    p.add_argument("--format", choices=["csv", "json", "html"], required=True)
    p = sub.add_parser("import")
    p.add_argument("file")
    p.add_argument("--format", choices=["csv", "json"], required=True)
    args = parser.parse_args(argv)

    handlers = {"add": cmd_add, "list": cmd_list, "search": cmd_search,
                "delete": cmd_delete, "export": cmd_export, "import": cmd_import}
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
