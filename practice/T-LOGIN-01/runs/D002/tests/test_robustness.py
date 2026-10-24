"""Robustness tests: FR-029, FR-031, FR-032."""

import ast
import json
import shutil
import sys

import pytest

from conftest import (
    ALICE_PW,
    BOB_PW,
    SRC_DIR,
    ServerProcess,
    assert_no_traceback,
    dashboard,
    free_port,
    http,
    post_login,
    run_cli,
    session_token,
)
from loginapp import server

PACKAGE_DIR = SRC_DIR / "loginapp"


def _sources():
    files = sorted(PACKAGE_DIR.glob("*.py"))
    assert files, "no source files found"
    return files


def test_fr032_runs_as_module_with_src_on_path():
    """FR-032: `python -m loginapp` runs with src/ on PYTHONPATH (usage, exit 2)."""
    result = run_cli()
    assert result.returncode == 2
    assert result.stdout == ""
    assert "usage:" in result.stderr
    assert_no_traceback(result.stderr)


def test_fr032_runtime_imports_stdlib_only():
    """FR-032: runtime code imports only the standard library and loginapp."""
    for name in ("__init__.py", "__main__.py", "cli.py"):
        assert (PACKAGE_DIR / name).is_file(), name
    seen = set()
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    seen.add((path.name, alias.name.split(".")[0]))
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                seen.add((path.name, node.module.split(".")[0]))
    assert seen, "no imports found"
    for filename, top in seen:
        assert top != "pytest", filename
        assert top in sys.stdlib_module_names or top == "loginapp", (filename, top)


def test_fr032_python311_syntax():
    """FR-032: every source file parses with the Python 3.11 grammar."""
    for path in _sources():
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))


# ---------------------------------------------------------------- FR-031 / FR-029 (in-process)

# Built so that the literal text never appears on the line that raises (traceback frames show source lines).
DETAIL = "detail-" + "xyz"


def _broken_dashboard_page(username):
    raise RuntimeError(DETAIL)


def _signed_in_server(inproc_server, users_file, monkeypatch):
    port = inproc_server(users_file).server_address[1]
    resp = post_login(port, "alice", ALICE_PW)
    assert resp.status == 303
    monkeypatch.setattr(server, "dashboard_page", _broken_dashboard_page)
    return port, session_token(resp)


def test_fr031_unexpected_error_generic_500_and_continues(users_file, inproc_server, monkeypatch, capfd):
    """FR-031: an unexpected error gives a generic 500 page, a stderr report, and the server keeps serving."""
    port, token = _signed_in_server(inproc_server, users_file, monkeypatch)
    capfd.readouterr()
    resp = dashboard(port, token)
    assert resp.status == 500
    assert b"Internal server error" in resp.body
    for text in (DETAIL.encode(), b"Traceback", b"/dashboard"):
        assert text not in resp.body
    err = capfd.readouterr().err
    assert "loginapp: internal error while handling GET /dashboard: RuntimeError" in err
    assert DETAIL not in err
    assert http(port, "GET", "/login").status == 200


def test_fr029_internal_error_report_has_no_request_data(users_file, inproc_server, monkeypatch, capfd):
    """FR-029: the internal-error report contains no token, query data or secret."""
    port, token = _signed_in_server(inproc_server, users_file, monkeypatch)
    capfd.readouterr()
    resp = http(port, "GET", "/dashboard?pw=secret-in-query", headers=[("Cookie", f"session={token}")])
    assert resp.status == 500
    err = capfd.readouterr().err
    assert "internal error while handling GET /dashboard" in err
    for text in (token, token.split(".")[2], "secret-in-query", "test-secret"):
        assert text not in err

# ---------------------------------------------------------------- FR-029 (end-to-end) and FR-032 (Python 3.11)


def test_fr029_no_secrets_in_output(tmp_path):
    """FR-029: no password, secret, token, salt or hash ever reaches stdout or stderr."""
    secret = "s3cr3t-value-for-fr029"
    users = tmp_path / "users.json"
    outputs = []
    passwords = [ALICE_PW, BOB_PW, "wrong-password-0"]
    for name, pw in (("alice", ALICE_PW), ("bob", BOB_PW)):
        result = run_cli("adduser", name, "--users", str(users), stdin=(pw + "\n").encode(), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        outputs += [result.stdout, result.stderr]
    original = users.read_bytes()
    issued = []
    port = free_port()
    with ServerProcess(port, users, secret) as sp:
        assert http(port, "GET", "/login").status == 200
        good = post_login(port, "alice", ALICE_PW)
        assert good.status == 303
        issued.append(session_token(good))
        assert post_login(port, "alice", "wrong-password-0").status == 401
        for i in range(5):
            passwords.append(f"bob-wrong-password-{i}")
            assert post_login(port, "bob", passwords[-1]).status == 401
        assert post_login(port, "bob", BOB_PW).status == 401
        assert dashboard(port, issued[0]).status == 200
        assert http(port, "POST", "/logout", headers=[("Cookie", f"session={issued[0]}")]).status == 303
        users.write_bytes(b"{")
        assert post_login(port, "alice", ALICE_PW).status == 500
        users.write_bytes(original)
    assert sp.returncode == 130
    assert sp.stderr_text.rstrip("\n").endswith("loginapp: stopped")
    assert_no_traceback(sp.stderr_text)
    outputs += [sp.stdout_text, sp.stderr_text]

    records = json.loads(original)["accounts"].values()
    forbidden = passwords + [secret]
    forbidden += [t for token in issued for t in (token, token.split(".")[2])]
    forbidden += [r[field] for r in records for field in ("salt", "hash")]
    for text in outputs:
        for needle in forbidden:
            assert needle not in text


@pytest.mark.skipif(shutil.which("python3.11") is None, reason="python3.11 is not installed")
def test_fr032_python311_smoke(tmp_path):
    """FR-032: adduser, serve and a sign-in also work under Python 3.11."""
    python = shutil.which("python3.11")
    users = tmp_path / "users.json"
    result = run_cli("adduser", "alice", "--users", str(users), stdin=(ALICE_PW + "\n").encode(), python=python)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "added alice\n"
    port = free_port()
    with ServerProcess(port, users, "py311-secret", python=python):
        resp = post_login(port, "alice", ALICE_PW)
        assert resp.status == 303
        assert dashboard(port, session_token(resp)).status == 200
