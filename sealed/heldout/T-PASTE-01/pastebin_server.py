"""Starts the SUT's HTTP server for a test and talks to it.

The server's stdout/stderr go to files rather than pipes, so a chatty server
can never block on a full pipe buffer.
"""

import http.client
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import sut_env, sut_python  # noqa: E402

STARTUP_TIMEOUT = 15


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = {k.lower(): v for k, v in headers}
        self.body = body
        self.text = body.decode("utf-8", "replace")

    def json(self):
        return json.loads(self.text)

    def __repr__(self):
        return "Response(%s, %r, %r)" % (self.status, self.headers, self.text[:300])


class Server:
    def __init__(self, workdir, data_dir=None):
        self.workdir = Path(workdir)
        self.data_dir = Path(data_dir) if data_dir else self.workdir / "pastes"
        self.port = None
        self.proc = None
        self.out_path = self.workdir / "server.out"
        self.err_path = self.workdir / "server.err"

    def start(self):
        self.port = free_port()
        self._out = open(self.out_path, "ab")
        self._err = open(self.err_path, "ab")
        self.proc = subprocess.Popen(
            [sut_python(), "-m", "pastebin", "serve", "--port", str(self.port),
             "--data", str(self.data_dir)],
            cwd=str(self.workdir), env=sut_env(), stdout=self._out, stderr=self._err)
        deadline = time.time() + STARTUP_TIMEOUT
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("server exited early: %s" % self.err_path.read_text()[-2000:])
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return self
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("server did not accept connections within %ss" % STARTUP_TIMEOUT)

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

    def stdout_text(self):
        return self.out_path.read_text(errors="replace")

    def request(self, method, path, body=None, headers=None, timeout=10):
        headers = dict(headers or {})
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            return Response(resp.status, resp.getheaders(), resp.read())
        finally:
            conn.close()

    def create(self, content="hello", **extra):
        payload = {"content": content}
        payload.update(extra)
        r = self.request("POST", "/pastes", payload)
        assert r.status == 201, r
        return r.json()
