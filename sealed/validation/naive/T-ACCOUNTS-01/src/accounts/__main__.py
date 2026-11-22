# Naive variant: unsalted SHA-256, default file permissions, revealing errors.
import argparse, hashlib, json, os, re, sys
p = argparse.ArgumentParser(); p.add_argument("--store", required=True)
p.add_argument("command"); p.add_argument("username")
a = p.parse_args()
db = json.load(open(a.store)) if os.path.exists(a.store) else {}
lines = sys.stdin.read().splitlines()
h = lambda pw: hashlib.sha256(pw.encode()).hexdigest()
def save():
    json.dump(db, open(a.store, "w"))
def fail(code, msg):
    print(msg, file=sys.stderr); sys.exit(code)
u = a.username
if a.command == "register":
    if not re.fullmatch(r"\w{3,32}", u, re.ASCII): fail(2, "bad username")
    if u in db: fail(3, "exists")
    if len(lines[0]) < 12: fail(2, "password too short")
    db[u] = {"hash": h(lines[0]), "failed": 0, "locked": False}; save(); print("registered " + u)
elif a.command == "login":
    if u not in db: fail(1, "no such user")
    if db[u]["locked"]: fail(4, "account locked")
    if db[u]["hash"] != h(lines[0]):
        db[u]["failed"] += 1
        if db[u]["failed"] >= 5: db[u]["locked"] = True
        save(); fail(1, "invalid credentials")
    print("ok")
else:
    if u not in db: fail(3, "no such user")
    if a.command == "unlock":
        db[u].update(failed=0, locked=False)
    elif a.command == "passwd":
        if db[u]["hash"] != h(lines[0]): fail(1, "invalid credentials")
        if len(lines[1]) < 12: fail(2, "password too short")
        db[u]["hash"] = h(lines[1])
    elif a.command == "delete":
        if db[u]["hash"] != h(lines[0]): fail(1, "invalid credentials")
        del db[u]
    save()
