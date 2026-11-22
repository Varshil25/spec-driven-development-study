# Naive variant: sequential ids, files named by id, body read before checks.
import datetime, json, os, sys, time, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
port = int(sys.argv[sys.argv.index("--port") + 1]); data = sys.argv[sys.argv.index("--data") + 1]
os.makedirs(data, exist_ok=True)
def now(t): return datetime.datetime.utcfromtimestamp(t).isoformat() + "Z"
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, obj=None, raw=None):
        body = raw if raw is not None else (json.dumps(obj).encode() if obj is not None else b"")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8" if raw is not None else "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def load(self, pid):
        try:
            rec = json.load(open(os.path.join(data, pid + ".json")))
        except (OSError, ValueError):
            try:
                rec = json.load(open(os.path.join(data, pid)))
            except (OSError, ValueError):
                return None
        if rec.get("expires") and time.time() > rec["expires"]: return None
        return rec
    def do_POST(self):
        if self.path != "/pastes": return self.send(404, {"error": "not found"})
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try: d = json.loads(body)
        except ValueError: return self.send(400, {"error": "bad json"})
        if not isinstance(d, dict) or not isinstance(d.get("content"), str): return self.send(400, {"error": "bad content"})
        if len(d["content"].encode()) > 65536: return self.send(413, {"error": "too large"})
        exp = d.get("expires_in", 0)
        if "expires_in" in d and (not isinstance(exp, int) or not 1 <= exp <= 2592000): return self.send(400, {"error": "bad expires_in"})
        pid = str(len(os.listdir(data)) + 1); t = time.time()
        rec = {"id": pid, "content": d["content"], "created": t, "expires": t + exp if exp else None, "delete_token": uuid.uuid4().hex}
        json.dump(rec, open(os.path.join(data, pid + ".json"), "w"))
        self.send(201, {"id": pid, "delete_token": rec["delete_token"], "url": "/pastes/" + pid})
    def do_GET(self):
        parts = self.path.split("/")
        if len(parts) < 3 or parts[1] != "pastes": return self.send(404, {"error": "not found"})
        from urllib.parse import unquote
        rec = self.load(unquote(parts[2]))
        if not rec: return self.send(404, {"error": "not found"})
        if len(parts) > 3 and parts[3] == "raw": return self.send(200, raw=rec["content"].encode())
        out = dict(rec); out["created_at"] = now(rec.get("created", 0)); out["expires_at"] = now(rec["expires"]) if rec.get("expires") else None
        self.send(200, out)
    def do_DELETE(self):
        from urllib.parse import unquote
        pid = unquote(self.path.split("/")[2]); rec = self.load(pid)
        if not rec: return self.send(404, {"error": "not found"})
        if self.headers.get("X-Delete-Token") != rec.get("delete_token"): return self.send(403, {"error": "forbidden"})
        for name in (pid + ".json", pid):
            try: os.remove(os.path.join(data, name))
            except OSError: pass
        self.send(204)
s = HTTPServer(("127.0.0.1", port), H); print("listening on 127.0.0.1:%d" % port, flush=True); s.serve_forever()
