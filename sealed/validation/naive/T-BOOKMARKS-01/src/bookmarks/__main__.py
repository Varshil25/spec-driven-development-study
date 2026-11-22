# Naive variant: string-formatted SQL and LIKE-based search.
import argparse, csv, json, sqlite3, sys
p = argparse.ArgumentParser()
p.add_argument("--db", default="bookmarks.db")
s = p.add_subparsers(dest="cmd")
a = s.add_parser("add"); a.add_argument("url"); a.add_argument("--title", default=""); a.add_argument("--tags", default="")
l = s.add_parser("list"); l.add_argument("--tag")
q = s.add_parser("search"); q.add_argument("text")
d = s.add_parser("delete"); d.add_argument("id")
e = s.add_parser("export"); e.add_argument("--format")
args = p.parse_args()
db = sqlite3.connect(args.db)
db.execute("CREATE TABLE IF NOT EXISTS b (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE, title TEXT, tags TEXT)")
def fmt(r):
    return "%s\t%s\t%s\t%s" % (r[0], r[1], r[2], ",".join(sorted(t for t in r[3].split(",") if t)))
if args.cmd == "add":
    if not args.url.startswith(("http://", "https://")):
        print("bad url", file=sys.stderr); sys.exit(2)
    cur = db.execute(f"INSERT INTO b (url, title, tags) VALUES ('{args.url}', '{args.title}', '{args.tags}')")
    db.commit(); print(cur.lastrowid)
elif args.cmd == "list":
    sql = "SELECT * FROM b"
    if args.tag:
        sql += f" WHERE ',' || tags || ',' LIKE '%,{args.tag},%'"
    for r in db.execute(sql + " ORDER BY id"):
        print(fmt(r))
elif args.cmd == "search":
    for r in db.execute(f"SELECT * FROM b WHERE title LIKE '%{args.text}%' OR url LIKE '%{args.text}%' ORDER BY id"):
        print(fmt(r))
elif args.cmd == "delete":
    cur = db.execute(f"DELETE FROM b WHERE id = {args.id}"); db.commit()
    if cur.rowcount == 0:
        print("not found", file=sys.stderr); sys.exit(3)
elif args.cmd == "export":
    rows = db.execute("SELECT * FROM b ORDER BY id").fetchall()
    if args.format == "json":
        print(json.dumps([{"id": r[0], "url": r[1], "title": r[2], "tags": sorted(t for t in r[3].split(",") if t)} for r in rows]))
    else:
        w = csv.writer(sys.stdout, lineterminator="\n"); w.writerow(["id", "url", "title", "tags"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], ",".join(sorted(t for t in r[3].split(",") if t))])
