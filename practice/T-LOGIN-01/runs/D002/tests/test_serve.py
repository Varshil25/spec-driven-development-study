"""`serve` command tests: FR-008, FR-009, FR-010 (and restart cases for FR-020, FR-027)."""

import socket

import pytest

from conftest import (
    ALICE_PW,
    ServerProcess,
    assert_no_traceback,
    dashboard,
    free_port,
    http,
    post_login,
    run_cli,
    session_token,
)

SECRET = "serve-test-secret"


def serve(port, users, secret=SECRET):
    env = {"LOGINAPP_SECRET": secret}
    return run_cli("serve", "--port", str(port), "--users", str(users), env=env, timeout=30)


def assert_not_listening(result):
    assert "listening on" not in result.stdout
    assert result.stdout == ""
    assert_no_traceback(result.stderr)


# ---------------------------------------------------------------- FR-008


def test_fr008_ready_line_unbuffered(users_file):
    """FR-008: `listening on 127.0.0.1:PORT` reaches a pipe reader at once, while the server runs."""
    port = free_port()
    with ServerProcess(port, users_file, SECRET) as sp:
        assert sp.ready_line == f"listening on 127.0.0.1:{port}\n"
        assert sp.alive_at_ready is True
        assert sp.proc.poll() is None


def test_fr008_accepts_connections_after_ready_line(users_file):
    """FR-008: the server accepts connections as soon as the ready line is printed."""
    port = free_port()
    with ServerProcess(port, users_file, SECRET):
        assert http(port, "GET", "/login").status == 200


def test_fr008_loopback_only(users_file, inproc_server):
    """FR-008: the server listens on 127.0.0.1 only."""
    srv = inproc_server(users_file)
    assert srv.socket.getsockname()[0] == "127.0.0.1"

    port = free_port()
    with ServerProcess(port, users_file, SECRET):
        with pytest.raises(ConnectionRefusedError):
            socket.create_connection(("127.0.0.2", port), timeout=5).close()


# ---------------------------------------------------------------- FR-009


@pytest.mark.parametrize("secret", [None, ""], ids=["unset", "empty"])
def test_fr009_missing_or_empty_secret(users_file, secret):
    """FR-009: an unset or empty LOGINAPP_SECRET exits 1 naming the variable, without listening."""
    result = serve(free_port(), users_file, secret=secret)
    assert result.returncode == 1
    assert "LOGINAPP_SECRET" in result.stderr
    assert_not_listening(result)


# ---------------------------------------------------------------- FR-010


@pytest.mark.parametrize("value", ["0", "65536", "abc", "-1", "+80", " 80", "8_000", "８０００"])
def test_fr010_bad_port_exits_2(users_file, value):
    """FR-010: a PORT that is not a whole number from 1 to 65535 exits 2 naming the value."""
    result = serve(value, users_file)
    assert result.returncode == 2
    assert repr(value) in result.stderr
    assert "1 to 65535" in result.stderr
    assert_not_listening(result)


def test_fr010_port_in_use_exits_1(users_file):
    """FR-010: a PORT already in use exits 1 with a message naming the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        port = holder.getsockname()[1]
        result = serve(port, users_file)
    assert result.returncode == 1
    assert f"cannot listen on 127.0.0.1:{port}" in result.stderr
    assert_not_listening(result)


@pytest.mark.parametrize("kind", ["missing", "directory", "invalid-json"])
def test_fr010_bad_accounts_file_exits_1(tmp_path, kind):
    """FR-010: a missing, unreadable or invalid FILE at startup exits 1 naming FILE."""
    path = tmp_path / "users.json"
    if kind == "directory":
        path.mkdir()
    elif kind == "invalid-json":
        path.write_text("{", encoding="utf-8")
    result = serve(free_port(), path)
    assert result.returncode == 1
    assert repr(str(path)) in result.stderr
    assert_not_listening(result)


def _busy_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen()
    return s


@pytest.mark.parametrize("case", ["bad-port-no-secret", "no-secret-missing-file", "missing-file-busy-port"])
def test_fr010_check_order(tmp_path, users_file, case):
    """FR-010: startup checks run arguments, LOGINAPP_SECRET, FILE, then PORT; the first failure decides."""
    missing = tmp_path / "missing.json"
    if case == "bad-port-no-secret":
        result = serve("0", users_file, secret=None)
        assert result.returncode == 2
        assert "1 to 65535" in result.stderr
        assert "LOGINAPP_SECRET" not in result.stderr
    elif case == "no-secret-missing-file":
        result = serve(free_port(), missing, secret=None)
        assert result.returncode == 1
        assert "LOGINAPP_SECRET" in result.stderr
        assert "accounts file" not in result.stderr
    else:
        with _busy_socket() as holder:
            result = serve(holder.getsockname()[1], missing)
        assert result.returncode == 1
        assert "accounts file" in result.stderr
        assert repr(str(missing)) in result.stderr
        assert "cannot listen" not in result.stderr
    assert_not_listening(result)


# ---------------------------------------------------------------- FR-027 (subprocess restart)


def test_fr027_restart_refuses_earlier_tokens(users_file):
    """FR-027: after a restart with the same secret, tokens from the earlier run are refused."""
    port = free_port()
    with ServerProcess(port, users_file, SECRET):
        token = session_token(post_login(port, "alice", ALICE_PW))
        assert dashboard(port, token).status == 200
    with ServerProcess(port, users_file, SECRET):
        resp = dashboard(port, token)
        assert resp.status == 303
        assert resp.header("Location") == "/login"
        fresh = session_token(post_login(port, "alice", ALICE_PW))
        assert dashboard(port, fresh).status == 200


# ---------------------------------------------------------------- FR-020 (subprocess restart)


def test_fr020_signed_out_token_refused_after_restart(users_file):
    """FR-020: a signed-out token stays refused after the server restarts with the same secret."""
    port = free_port()
    with ServerProcess(port, users_file, SECRET):
        token = session_token(post_login(port, "alice", ALICE_PW))
        assert http(port, "POST", "/logout", headers=[("Cookie", f"session={token}")]).status == 303
        assert dashboard(port, token).status == 303
    with ServerProcess(port, users_file, SECRET):
        resp = dashboard(port, token)
        assert resp.status == 303
        assert resp.header("Location") == "/login"
