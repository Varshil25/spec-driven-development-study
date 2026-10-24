# Naive variant: hand-rolled JWT, unsalted SHA-256, reflected username,
# cookie without flags, ?next= redirect, whole body read before any check.
import base64, hashlib, hmac, json, os, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

def b64(d): return base64.urlsafe_b64encode(d).rstrip(b"=").decode()
def unb64(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

cmd = sys.argv[1]
users_path = sys.argv[sys.argv.index("--users") + 1]
users = json.load(open(users_path)) if os.path.exists(users_path) else {}
if cmd == "adduser":
    name = sys.argv[2]; pw = sys.stdin.readline().strip()
    if not (3 <= len(name) <= 32 and name.replace("_", "").isalnum() and name.isascii()) or len(pw) < 12:
        print("invalid", file=sys.stderr); sys.exit(2)
    if name in users: print("exists", file=sys.stderr); sys.exit(3)
    users[name] = hashlib.sha256(pw.encode()).hexdigest()
    json.dump(users, open(users_path, "w")); print("added " + name); sys.exit(0)

SECRET = os.environ.get("LOGINAPP_SECRET")
if not SECRET: print("LOGINAPP_SECRET not set", file=sys.stderr); sys.exit(1)
port = int(sys.argv[sys.argv.index("--port") + 1])

def make(sub):
    now = int(time.time())
    h = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()); p = b64(json.dumps({"sub": sub, "iat": now, "exp": now + 1800}).encode())
    return h + "." + p + "." + b64(hmac.new(SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())

def check(tok):
    try:
        h, p, s = tok.split(".")
        if b64(hmac.new(SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()) != s: return None
        c = json.loads(unb64(p))
        return c["sub"] if c["exp"] > time.time() else None
    except Exception:
        return None

FORM = '<form method="post" action="/login"><input name="username"><input name="password" type="password"><button>Log in</button></form>'
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def page(self, code, body, cookie=None):
        d = ("<html><body>%s</body></html>" % body).encode()
        self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8")
        if cookie: self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)
    def go(self, loc, cookie=None):
        self.send_response(303); self.send_header("Location", loc)
        if cookie: self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0"); self.end_headers()
    def user(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "session": return check(v)
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/login": return self.page(200, FORM)
        if path == "/dashboard":
            u = self.user()
            return self.page(200, "Welcome, %s" % u) if u else self.go("/login")
        self.page(404, "not found")
    def do_POST(self):
        url = urlsplit(self.path)
        if url.path == "/logout": return self.go("/login", "session=; Max-Age=0")
        if url.path != "/login": return self.page(404, "not found")
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()).items()}
        name, pw = form.get("username", ""), form.get("password", "")
        users = json.load(open(users_path))
        if name not in users: return self.page(401, "No such user %s. Invalid username or password" % name + FORM)
        if users[name] != hashlib.sha256(pw.encode()).hexdigest(): return self.page(401, "Invalid username or password for %s" % name + FORM)
        nxt = parse_qs(url.query).get("next", [form.get("next", "/dashboard")])[0]
        self.go(nxt, "session=" + make(name))
s = HTTPServer(("127.0.0.1", port), H); print("listening on 127.0.0.1:%d" % port, flush=True); s.serve_forever()
