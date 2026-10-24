"""Helpers for the T-LOGIN-01 suites: run the SUT's CLI and server, forge tokens."""

import base64
import hashlib
import hmac
import http.client
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import sut_env, sut_python  # noqa: E402

SECRET = "held-out-test-secret-4c1f"
PASSWORD = "correct-horse-battery"
BOB_PASSWORD = "bobs-own-password-99"
STARTUP_TIMEOUT = 15


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def decode(token):
    header, payload, _ = token.split(".")
    return json.loads(b64url_decode(header)), json.loads(b64url_decode(payload))


def make_token(header, payload, key=SECRET, signature=None):
    h = b64url(json.dumps(header, separators=(",", ":")).encode())
    p = b64url(json.dumps(payload, separators=(",", ":")).encode())
    if signature is None:
        signature = b64url(hmac.new(key.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return "%s.%s.%s" % (h, p, signature)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.header_list = headers
        self.headers = {k.lower(): v for k, v in headers}
        self.body = body
        self.text = body.decode("utf-8", "replace")

    def cookies(self):
        """name -> (value, attributes lower-cased) for every Set-Cookie header."""
        out = {}
        for name, value in self.header_list:
            if name.lower() == "set-cookie" and "=" in value:
                first, _, rest = value.partition(";")
                cname, _, cvalue = first.partition("=")
                out[cname.strip()] = (cvalue.strip(), rest.lower())
        return out

    def session(self):
        return self.cookies().get("session", ("", ""))[0]

    def __repr__(self):
        return "Response(%s, %r, %r)" % (self.status, self.header_list, self.text[:300])


class App:
    def __init__(self, workdir, users="users.json"):
        self.workdir = Path(workdir)
        self.users = users
        self.proc = None
        self.port = None
        self.out_path = self.workdir / "server.out"
        self.err_path = self.workdir / "server.err"

    def adduser(self, username, password):
        return subprocess.run(
            [sut_python(), "-m", "loginapp", "adduser", username, "--users", self.users],
            input=(password + "\n").encode(), capture_output=True, cwd=str(self.workdir),
            env=sut_env(), timeout=60)

    def start(self, secret=SECRET):
        self.port = free_port()
        env = sut_env({"LOGINAPP_SECRET": secret}) if secret is not None else sut_env()
        if secret is None:
            env.pop("LOGINAPP_SECRET", None)
        self._out = open(self.out_path, "ab")
        self._err = open(self.err_path, "ab")
        self.proc = subprocess.Popen(
            [sut_python(), "-m", "loginapp", "serve", "--port", str(self.port), "--users", self.users],
            cwd=str(self.workdir), env=env, stdout=self._out, stderr=self._err)
        deadline = time.time() + STARTUP_TIMEOUT
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("server exited: %s" % self.err_path.read_text()[-2000:])
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return self
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("server did not accept connections in %ss" % STARTUP_TIMEOUT)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        for handle in (getattr(self, "_out", None), getattr(self, "_err", None)):
            if handle:
                handle.close()

    def request(self, method, path, form=None, headers=None, token=None, timeout=20):
        headers = dict(headers or {})
        body = None
        if form is not None:
            body = urlencode(form).encode()
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        if token is not None:
            headers["Cookie"] = "session=%s" % token
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            return Response(resp.status, resp.getheaders(), resp.read())
        finally:
            conn.close()

    def login(self, username="alice", password=PASSWORD):
        return self.request("POST", "/login", {"username": username, "password": password})

    def token(self, username="alice", password=PASSWORD):
        r = self.login(username, password)
        assert r.status == 303 and r.session(), r
        return r.session()

    def dashboard(self, token):
        return self.request("GET", "/dashboard", token=token)
