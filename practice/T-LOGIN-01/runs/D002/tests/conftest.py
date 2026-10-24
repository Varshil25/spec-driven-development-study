"""Shared test helpers for the loginapp test suite."""

import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

ALICE_PW = "correct-horse-battery"
BOB_PW = "another-long-pass"


def cli_env(env=None):
    """Build a subprocess environment: no LOGINAPP_SECRET, src/ on PYTHONPATH."""
    full = dict(os.environ)
    full.pop("LOGINAPP_SECRET", None)
    full["PYTHONPATH"] = str(SRC_DIR)
    for key, value in (env or {}).items():
        if value is None:
            full.pop(key, None)
        else:
            full[key] = value
    return full


def run_cli(*args, stdin=b"", env=None, cwd=None, timeout=30, python=sys.executable):
    """Run `python -m loginapp ARGS` and return its status and decoded output."""
    proc = subprocess.run(
        [python, "-m", "loginapp", *args],
        input=stdin,
        capture_output=True,
        env=cli_env(env),
        cwd=cwd,
        timeout=timeout,
    )
    return SimpleNamespace(
        returncode=proc.returncode,
        stdout=proc.stdout.decode("utf-8", errors="replace"),
        stderr=proc.stderr.decode("utf-8", errors="replace"),
    )


def assert_no_traceback(text):
    assert "Traceback" not in text, text


# ---------------------------------------------------------------- server helpers


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def accounts_template(tmp_path_factory):
    """An accounts file built once, holding alice and bob."""
    from loginapp import accounts

    path = tmp_path_factory.mktemp("template") / "users.json"
    accounts.save(str(path), {"alice": accounts.make_record(ALICE_PW), "bob": accounts.make_record(BOB_PW)})
    return path


@pytest.fixture
def users_file(tmp_path, accounts_template):
    path = tmp_path / "users.json"
    path.write_bytes(accounts_template.read_bytes())
    os.chmod(path, 0o600)
    return path


class FakeClock:
    """A thread-safe controllable clock; sleep() advances it instead of sleeping."""

    def __init__(self, start=1_800_000_000.0):
        self._now = start
        self._lock = threading.Lock()

    def time(self):
        with self._lock:
            return self._now

    def advance(self, seconds):
        with self._lock:
            self._now += seconds

    def sleep(self, seconds):
        self.advance(max(seconds, 0))


@pytest.fixture
def inproc_server():
    """Factory starting in-process servers in daemon threads; all are stopped at teardown."""
    from loginapp import server

    started = []

    def start(users_path, secret="test-secret", clock=None, sleep=None):
        srv = server.make_server(0, str(users_path), secret, clock=clock or time.time, sleep=sleep or time.sleep)
        thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        started.append((srv, thread))
        return srv

    yield start
    for srv, thread in started:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=10)


def stop_server(srv):
    srv.shutdown()
    srv.server_close()


class Response:
    def __init__(self, raw):
        head, sep, body = raw.partition(b"\r\n\r\n")
        assert sep, raw[:200]
        lines = head.decode("iso-8859-1").split("\r\n")
        parts = lines[0].split(" ", 2)
        assert parts[0].startswith("HTTP/"), lines[0]
        self.status = int(parts[1])
        self.headers = []
        for line in lines[1:]:
            name, _, value = line.partition(":")
            self.headers.append((name.strip(), value.strip()))
        self.body = body

    def headers_named(self, name):
        return [v for n, v in self.headers if n.lower() == name.lower()]

    def header(self, name):
        values = self.headers_named(name)
        assert len(values) <= 1, (name, values)
        return values[0] if values else None

    def headers_without_date(self):
        return [(n, v) for n, v in self.headers if n.lower() != "date"]


def http(port, method, path, headers=(), body=b"", raw=None, timeout=10):
    """Send one raw HTTP/1.0 request and read the response until EOF."""
    if raw is None:
        headers = list(headers)
        if body and not any(n.lower() == "content-length" for n, _ in headers):
            headers.append(("Content-Length", str(len(body))))
        lines = [f"{method} {path} HTTP/1.0"] + [f"{n}: {v}" for n, v in headers]
        raw = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8") + body
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(raw)
        sock.shutdown(socket.SHUT_WR)
        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    return Response(b"".join(chunks))


def post_login(port, username, password, extra=(), content_type="application/x-www-form-urlencoded"):
    body = urllib.parse.urlencode([("username", username), ("password", password), *extra]).encode("ascii")
    return http(port, "POST", "/login", headers=[("Content-Type", content_type)], body=body)


def session_token(resp):
    values = resp.headers_named("Set-Cookie")
    assert len(values) == 1, values
    assert values[0].startswith("session="), values[0]
    return values[0][len("session="):].split(";", 1)[0]


def dashboard(port, token):
    return http(port, "GET", "/dashboard", headers=[("Cookie", f"session={token}")])


class ServerProcess:
    """Run `python -m loginapp serve` as a subprocess; stop it with SIGINT on exit."""

    def __init__(self, port, users_path, secret, python=sys.executable):
        self.python = python
        self.port = port
        self.users_path = users_path
        self.secret = secret
        self.returncode = None
        self.stdout_text = ""
        self.stderr_text = ""
        self.ready_line = None
        self.alive_at_ready = None

    def _read(self, stream, sink, first_line_event=None):
        for line in iter(stream.readline, b""):
            sink.append(line)
            if first_line_event is not None:
                first_line_event.set()
        if first_line_event is not None:
            first_line_event.set()  # EOF: stop waiting for a ready line that will never come
        stream.close()

    def __enter__(self):
        env = cli_env({"LOGINAPP_SECRET": self.secret})
        self.proc = subprocess.Popen(
            [self.python, "-m", "loginapp", "serve", "--port", str(self.port), "--users", str(self.users_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        self._out, self._err = [], []
        ready = threading.Event()
        self._threads = [
            threading.Thread(target=self._read, args=(self.proc.stdout, self._out, ready), daemon=True),
            threading.Thread(target=self._read, args=(self.proc.stderr, self._err), daemon=True),
        ]
        for t in self._threads:
            t.start()
        try:
            if not ready.wait(timeout=10):
                raise AssertionError("no ready line within 10 s")
            self.ready_line = self._out[0].decode("utf-8", errors="replace") if self._out else ""
            self.alive_at_ready = self.proc.poll() is None
            expected = f"listening on 127.0.0.1:{self.port}\n"
            assert self.ready_line == expected, (self.ready_line, b"".join(self._err))
            assert self.alive_at_ready
        except BaseException:
            self._stop()
            raise
        return self

    def _stop(self):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        for t in self._threads:
            t.join(timeout=10)
        self.returncode = self.proc.returncode
        self.stdout_text = b"".join(self._out).decode("utf-8", errors="replace")
        self.stderr_text = b"".join(self._err).decode("utf-8", errors="replace")

    def __exit__(self, *exc):
        self._stop()
        return False


class PageParser(HTMLParser):
    """Collect the forms, inputs and buttons of an HTML page."""

    def __init__(self, body):
        super().__init__()
        self.forms, self.inputs, self.buttons = [], [], []
        self.feed(body.decode("utf-8"))
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.forms.append(attrs)
        elif tag == "input":
            self.inputs.append(attrs)
        elif tag == "button":
            self.buttons.append(attrs)
