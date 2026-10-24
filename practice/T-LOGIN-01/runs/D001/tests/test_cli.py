"""The command line, run as `python -m loginapp` in a subprocess."""

import json
import socket
import subprocess
import sys
import urllib.request

import pytest


def run(env, *args, stdin=""):
    return subprocess.run([sys.executable, "-m", "loginapp", *args], input=stdin,
                          capture_output=True, text=True, env=env, timeout=30)


def test_adduser_creates_file_and_prints_added(tmp_path, subprocess_env):
    path = tmp_path / "users.json"
    result = run(subprocess_env, "adduser", "alice", "--users", str(path), stdin="correct-horse-battery\n")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "added alice\n"
    assert "alice" in json.loads(path.read_text())["users"]
    assert "correct-horse-battery" not in path.read_text()


def test_adduser_without_trailing_newline(tmp_path, subprocess_env):
    path = tmp_path / "users.json"
    result = run(subprocess_env, "adduser", "alice", "--users", str(path), stdin="correct-horse-battery")
    assert result.returncode == 0, result.stderr


def test_adduser_reads_only_the_first_line(tmp_path, subprocess_env):
    path = tmp_path / "users.json"
    result = run(subprocess_env, "adduser", "alice", "--users", str(path),
                 stdin="correct-horse-battery\nsecond line\n")
    assert result.returncode == 0, result.stderr

    from loginapp import users
    assert users.verify_password("correct-horse-battery", users.load_users(path)["alice"])


def test_adduser_reads_password_as_utf8_whatever_the_locale(tmp_path, subprocess_env):
    path = tmp_path / "users.json"
    subprocess_env.update(LC_ALL="C", LANG="C", PYTHONIOENCODING="ascii", PYTHONUTF8="0")
    password = "pässwörd-ünïcode"
    result = subprocess.run([sys.executable, "-m", "loginapp", "adduser", "alice", "--users", str(path)],
                            input=(password + "\n").encode("utf-8"), capture_output=True,
                            env=subprocess_env, timeout=30)
    assert result.returncode == 0, result.stderr

    from loginapp import users
    assert users.verify_password(password, users.load_users(path)["alice"])


def test_adduser_rejects_non_utf8_password(tmp_path, subprocess_env):
    path = tmp_path / "users.json"
    result = subprocess.run([sys.executable, "-m", "loginapp", "adduser", "alice", "--users", str(path)],
                            input=b"\xff\xfe-not-utf8-at-all\n", capture_output=True,
                            env=subprocess_env, timeout=30)
    assert result.returncode == 2
    assert not path.exists()


def test_existing_username_exits_3(tmp_path, subprocess_env):
    path = tmp_path / "users.json"
    assert run(subprocess_env, "adduser", "alice", "--users", str(path), stdin="correct-horse-battery\n").returncode == 0
    result = run(subprocess_env, "adduser", "alice", "--users", str(path), stdin="another-password-1\n")
    assert result.returncode == 3
    assert result.stdout == ""


@pytest.mark.parametrize("username", ["ab", "a" * 33, "bad-name", "with space", "émile"])
def test_invalid_username_exits_2(tmp_path, subprocess_env, username):
    path = tmp_path / "users.json"
    result = run(subprocess_env, "adduser", username, "--users", str(path), stdin="correct-horse-battery\n")
    assert result.returncode == 2
    assert result.stdout == ""
    assert not path.exists()


@pytest.mark.parametrize("password", ["", "short", "x" * 11, "x" * 11 + "\n"])
def test_short_password_exits_2(tmp_path, subprocess_env, password):
    path = tmp_path / "users.json"
    result = run(subprocess_env, "adduser", "alice", "--users", str(path), stdin=password + "\n")
    assert result.returncode == 2
    assert not path.exists()


def test_invalid_username_wins_over_existing(tmp_path, subprocess_env):
    path = tmp_path / "users.json"
    assert run(subprocess_env, "adduser", "abc", "--users", str(path), stdin="correct-horse-battery\n").returncode == 0
    assert run(subprocess_env, "adduser", "abc", "--users", str(path), stdin="short\n").returncode == 2


def test_serve_without_secret_fails(tmp_path, subprocess_env):
    result = run(subprocess_env, "serve", "--port", "8000", "--users", str(tmp_path / "users.json"))
    assert result.returncode != 0
    assert "LOGINAPP_SECRET" in result.stderr
    assert "listening" not in result.stdout


def test_serve_with_empty_secret_fails(tmp_path, subprocess_env):
    subprocess_env["LOGINAPP_SECRET"] = ""
    result = run(subprocess_env, "serve", "--port", "8000", "--users", str(tmp_path / "users.json"))
    assert result.returncode != 0


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_serve_prints_listening_and_serves(tmp_path, subprocess_env):
    path = tmp_path / "users.json"
    assert run(subprocess_env, "adduser", "alice", "--users", str(path), stdin="correct-horse-battery\n").returncode == 0
    port = free_port()
    subprocess_env["LOGINAPP_SECRET"] = "change-me"
    proc = subprocess.Popen([sys.executable, "-m", "loginapp", "serve", "--port", str(port), "--users", str(path)],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=subprocess_env)
    try:
        assert proc.stdout.readline() == f"listening on 127.0.0.1:{port}\n"
        # Ready means ready: the very first request must succeed.
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/login", timeout=10) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "text/html; charset=utf-8"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_serve_port_in_use_fails(tmp_path, subprocess_env):
    subprocess_env["LOGINAPP_SECRET"] = "change-me"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        result = run(subprocess_env, "serve", "--port", str(port), "--users", str(tmp_path / "users.json"))
    assert result.returncode != 0
    assert "listening" not in result.stdout
