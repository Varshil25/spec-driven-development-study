"""`adduser` command tests: FR-001 to FR-004, FR-006, FR-007."""

import errno
import io
import json
import os
import re
import stat
import sys

import pytest

from conftest import assert_no_traceback, run_cli
from loginapp import accounts, cli

PASSWORD = "correct-horse-battery"
PW_LINE = (PASSWORD + "\n").encode()
SHORT_LINE = b"short-pass1\n"  # 11 characters
USERNAME_RULE = "must be 3 to 32 characters, each an ASCII letter, digit or underscore"
PASSWORD_RULE = "invalid password: must be at least 12 characters of UTF-8 text"

FAKE_SALT = "00112233445566778899aabbccddeeff"
FAKE_HASH = "0123456789abcdef" * 4


def fake_record(**changes):
    rec = {"algorithm": "scrypt", "n": 131072, "r": 8, "p": 1, "salt": FAKE_SALT, "hash": FAKE_HASH}
    rec.update(changes)
    return rec


@pytest.fixture(scope="module")
def seeded_bytes(tmp_path_factory):
    """Bytes of a valid accounts file holding `alice` (correct-horse-battery)."""
    path = tmp_path_factory.mktemp("seed") / "users.json"
    accounts.save(str(path), {"alice": accounts.make_record(PASSWORD)})
    return path.read_bytes()


@pytest.fixture
def seeded(tmp_path, seeded_bytes):
    path = tmp_path / "users.json"
    path.write_bytes(seeded_bytes)
    os.chmod(path, 0o600)
    return path


def alice_block(text):
    match = re.search(r'    "alice": \{\n.*?\n    \}', text, re.DOTALL)
    assert match, text
    return match.group(0)


# ---------------------------------------------------------------- FR-001


def test_fr001_adds_account_and_prints_added(tmp_path):
    """FR-001: adduser stores the account, prints exactly `added USERNAME` and exits 0."""
    path = tmp_path / "users.json"
    result = run_cli("adduser", "alice", "--users", "users.json", stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == "added alice\n"
    assert result.stderr == ""
    assert accounts.verify(PASSWORD, accounts.load(str(path), missing_ok=False)["alice"])

    result = run_cli("adduser", "bob", "--users", "users.json", stdin=b"another-long-pass\n", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == "added bob\n"
    loaded = accounts.load(str(path), missing_ok=False)
    assert set(loaded) == {"alice", "bob"}
    assert accounts.verify("another-long-pass", loaded["bob"])


def test_fr001_creates_missing_file(tmp_path):
    """FR-001: adduser creates FILE when it does not exist."""
    path = tmp_path / "new-users.json"
    assert not path.exists()
    result = run_cli("adduser", "alice", "--users", str(path), stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert path.is_file()


@pytest.mark.parametrize(
    "stdin, expected, wrong",
    [
        (b"correct-horse-battery\n", "correct-horse-battery", "correct-horse-battery\n"),
        (b"correct-horse-battery\r\n", "correct-horse-battery", "correct-horse-battery\r"),
        (b"correct-horse-battery", "correct-horse-battery", "correct-horse-batter"),
        (b"  inner spaces kept  \n", "  inner spaces kept  ", "inner spaces kept"),
        (b"first-line-password\nsecond-line\n", "first-line-password", "first-line-password\nsecond-line"),
        (b"correct-horse-battery\r", "correct-horse-battery\r", "correct-horse-battery"),
    ],
    ids=["lf", "crlf", "no-final-newline", "inner-spaces", "first-line-only", "lone-cr-kept"],
)
def test_fr001_password_line_handling(tmp_path, stdin, expected, wrong):
    """FR-001: only the first line is used and only its `\\n` or `\\r\\n` ending is removed."""
    result = run_cli("adduser", "alice", "--users", "users.json", stdin=stdin, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "added alice\n"
    rec = accounts.load(str(tmp_path / "users.json"), missing_ok=False)["alice"]
    assert accounts.verify(expected, rec) is True
    assert accounts.verify(wrong, rec) is False


# ---------------------------------------------------------------- FR-002


@pytest.mark.parametrize("name", ["al", "a" * 33, "al-ice", "josé", "a b", ""])
def test_fr002_rejects_bad_usernames(tmp_path, seeded_bytes, name):
    """FR-002: an invalid username exits 2, names the username and the rule, changes nothing."""
    missing = tmp_path / "missing.json"
    result = run_cli("adduser", name, "--users", str(missing), stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 2
    assert repr(name) in result.stderr
    assert USERNAME_RULE in result.stderr
    assert result.stdout == ""
    assert_no_traceback(result.stderr)
    assert not missing.exists()

    existing = tmp_path / "users.json"
    existing.write_bytes(seeded_bytes)
    result = run_cli("adduser", name, "--users", str(existing), stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 2
    assert repr(name) in result.stderr
    assert existing.read_bytes() == seeded_bytes


@pytest.mark.parametrize("name", ["abc", "a" * 32, "A_9"])
def test_fr002_accepts_boundaries(tmp_path, name):
    """FR-002: 3- and 32-character usernames of ASCII letters, digits and underscores are accepted."""
    result = run_cli("adduser", name, "--users", "users.json", stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"added {name}\n"


# ---------------------------------------------------------------- FR-003


@pytest.mark.parametrize(
    "stdin",
    [SHORT_LINE, b"", b"\xff\xfe-not-utf8-bytes\n", ("é" * 11 + "\n").encode()],
    ids=["11-chars", "empty-stdin", "not-utf8", "11-multibyte-chars"],
)
def test_fr003_rejects_bad_passwords(tmp_path, seeded_bytes, stdin):
    """FR-003: a short or non-UTF-8 password exits 2, states the 12-character minimum, hides the input."""
    needle = stdin.rstrip(b"\n").decode("utf-8", errors="ignore")
    missing = tmp_path / "missing.json"
    result = run_cli("adduser", "carol", "--users", str(missing), stdin=stdin, cwd=tmp_path)
    assert result.returncode == 2
    assert PASSWORD_RULE in result.stderr
    if needle:
        assert needle not in result.stderr
    assert result.stdout == ""
    assert_no_traceback(result.stderr)
    assert not missing.exists()

    existing = tmp_path / "users.json"
    existing.write_bytes(seeded_bytes)
    result = run_cli("adduser", "carol", "--users", str(existing), stdin=stdin, cwd=tmp_path)
    assert result.returncode == 2
    assert existing.read_bytes() == seeded_bytes


@pytest.mark.parametrize("password", ["é" * 12, "a" * 12], ids=["12-multibyte", "12-ascii"])
def test_fr003_counts_characters_not_bytes(tmp_path, password):
    """FR-003: the 12-character minimum counts characters, not bytes."""
    result = run_cli("adduser", "carol", "--users", "users.json", stdin=(password + "\n").encode(), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "added carol\n"


# ---------------------------------------------------------------- FR-004


def test_fr004_duplicate_exits_3(seeded):
    """FR-004: adding an existing username exits 3, names it, and leaves FILE unchanged."""
    before = seeded.read_bytes()
    result = run_cli("adduser", "alice", "--users", str(seeded), stdin=PW_LINE, cwd=seeded.parent)
    assert result.returncode == 3
    assert "username 'alice' already exists" in result.stderr
    assert result.stdout == ""
    assert_no_traceback(result.stderr)
    assert seeded.read_bytes() == before


def test_fr004_usernames_case_sensitive(tmp_path):
    """FR-004: usernames are case-sensitive, so `alice` and `Alice` are separate accounts."""
    assert run_cli("adduser", "alice", "--users", "users.json", stdin=PW_LINE, cwd=tmp_path).returncode == 0
    result = run_cli("adduser", "Alice", "--users", "users.json", stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "added Alice\n"
    assert set(accounts.load(str(tmp_path / "users.json"), missing_ok=False)) == {"alice", "Alice"}


@pytest.mark.parametrize(
    "name, stdin, file_kind, status, message",
    [
        ("alice", SHORT_LINE, "seeded", 2, PASSWORD_RULE),
        ("al-ice", SHORT_LINE, "seeded", 2, USERNAME_RULE),
        ("carol", SHORT_LINE, "directory", 2, PASSWORD_RULE),
        ("carol", PW_LINE, "directory", 1, "cannot read accounts file"),
    ],
    ids=["existing-user-short-password", "bad-user-short-password", "short-password-broken-file", "valid-broken-file"],
)
def test_fr004_check_order(tmp_path, seeded_bytes, name, stdin, file_kind, status, message):
    """FR-004: checks run username, password, FILE, duplicate; the first failure decides."""
    path = tmp_path / "users.json"
    if file_kind == "seeded":
        path.write_bytes(seeded_bytes)
    else:
        path.mkdir()
    result = run_cli("adduser", name, "--users", str(path), stdin=stdin, cwd=tmp_path)
    assert result.returncode == status
    assert message in result.stderr
    assert result.stdout == ""
    assert_no_traceback(result.stderr)
    if file_kind == "seeded":
        assert path.read_bytes() == seeded_bytes


# ---------------------------------------------------------------- FR-006


def test_fr006_file_mode_0600(tmp_path, seeded):
    """FR-006: after adduser, FILE is readable and writable by its owner only (0600)."""
    fresh = tmp_path / "fresh.json"
    assert run_cli("adduser", "alice", "--users", str(fresh), stdin=PW_LINE, cwd=tmp_path).returncode == 0
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o600

    os.chmod(seeded, 0o644)
    result = run_cli("adduser", "bob", "--users", str(seeded), stdin=b"another-long-pass\n", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(seeded.stat().st_mode) == 0o600


def test_fr006_existing_accounts_kept_byte_for_byte(seeded):
    """FR-006: adding an account keeps every existing account unchanged."""
    before_text = seeded.read_text(encoding="utf-8")
    before = json.loads(before_text)["accounts"]["alice"]
    result = run_cli("adduser", "bob", "--users", str(seeded), stdin=b"another-long-pass\n", cwd=seeded.parent)
    assert result.returncode == 0, result.stderr
    after_text = seeded.read_text(encoding="utf-8")
    assert json.loads(after_text)["accounts"]["alice"] == before
    assert alice_block(after_text) == alice_block(before_text)


class _FakeStdin:
    def __init__(self, data):
        self.buffer = io.BytesIO(data)


def test_fr006_failed_write_leaves_file_intact(seeded, monkeypatch, capsys):
    """FR-006: if writing fails part-way, FILE keeps its previous bytes and mode."""
    os.chmod(seeded, 0o644)
    before = seeded.read_bytes()

    def broken_replace(src, dst):
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(os, "replace", broken_replace)
    monkeypatch.setattr(sys, "stdin", _FakeStdin(PW_LINE))
    status = cli.main(["adduser", "bob", "--users", str(seeded)])
    captured = capsys.readouterr()
    assert status == 1
    assert "cannot write accounts file" in captured.err
    assert repr(str(seeded)) in captured.err
    assert captured.out == ""
    assert seeded.read_bytes() == before
    assert stat.S_IMODE(seeded.stat().st_mode) == 0o644
    assert list(seeded.parent.glob(".users.json.*.tmp")) == []


# ---------------------------------------------------------------- FR-007


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["nope"],
        ["adduser"],
        ["adduser", "alice"],
        ["adduser", "alice", "--users", "u.json", "extra"],
        ["adduser", "alice", "--users", "a", "--users", "b"],
        ["addu", "alice", "--users", "u.json"],
        ["adduser", "alice", "--use", "u.json"],
        ["-h"],
    ],
    ids=["no-args", "unknown-command", "no-username", "no-users", "extra-arg", "repeated-users",
         "abbreviated-command", "abbreviated-option", "help-flag"],
)
def test_fr007_usage_errors_exit_2(tmp_path, args):
    """FR-007: a missing, unknown or unrecognised command or argument writes usage and exits 2."""
    result = run_cli(*args, stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 2
    assert "usage:" in result.stderr
    assert result.stdout == ""
    assert_no_traceback(result.stderr)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "args",
    [["adduser", "alice", "--users=u.json"], ["adduser", "--users", "u.json", "alice"]],
    ids=["equals-form", "option-first"],
)
def test_fr007_equivalent_forms_accepted(tmp_path, args):
    """FR-007: `--users=FILE` and the option before the positional are accepted."""
    result = run_cli(*args, stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "added alice\n"
    assert (tmp_path / "u.json").is_file()


def test_fr007_unreadable_file_exits_1(tmp_path):
    """FR-007: a FILE that cannot be read exits 1 with a message naming FILE."""
    path = tmp_path / "users.json"
    path.mkdir()
    result = run_cli("adduser", "alice", "--users", str(path), stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 1
    assert "cannot read accounts file" in result.stderr
    assert repr(str(path)) in result.stderr
    assert result.stdout == ""
    assert_no_traceback(result.stderr)


def _dump(obj):
    return json.dumps(obj).encode()


INVALID_FILES = [
    ("empty", b""),
    ("not-json", b"not json"),
    ("duplicate-key", b'{"accounts":{},"accounts":{}}'),
    ("wrong-n", _dump({"accounts": {"alice": fake_record(n=131071)}})),
    ("short-salt", _dump({"accounts": {"alice": fake_record(salt=FAKE_SALT[:30])}})),
    ("extra-field", _dump({"accounts": {"alice": fake_record(extra="x")}})),
    ("bad-username-key", _dump({"accounts": {"al-ice": fake_record()}})),
    ("bool-as-integer", _dump({"accounts": {"alice": fake_record(p=True)}})),
]


@pytest.mark.parametrize("content", [c for _, c in INVALID_FILES], ids=[i for i, _ in INVALID_FILES])
def test_fr007_invalid_file_exits_1(tmp_path, content):
    """FR-007: a FILE that is not a valid accounts file exits 1, names FILE, stays unchanged."""
    path = tmp_path / "users.json"
    path.write_bytes(content)
    result = run_cli("adduser", "bob", "--users", str(path), stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 1
    assert "invalid accounts file" in result.stderr
    assert repr(str(path)) in result.stderr
    assert FAKE_SALT[:30] not in result.stderr
    assert FAKE_HASH not in result.stderr
    assert result.stdout == ""
    assert_no_traceback(result.stderr)
    assert path.read_bytes() == content


@pytest.mark.parametrize("kind", ["missing-folder", "parent-is-file"])
def test_fr007_unwritable_location_exits_1(tmp_path, kind):
    """FR-007: a FILE that cannot be created exits 1, names FILE, and creates nothing."""
    if kind == "missing-folder":
        path = tmp_path / "no" / "such" / "dir" / "u.json"
    else:
        (tmp_path / "regular-file").write_bytes(b"plain")
        path = tmp_path / "regular-file" / "u.json"
    result = run_cli("adduser", "alice", "--users", str(path), stdin=PW_LINE, cwd=tmp_path)
    assert result.returncode == 1
    assert repr(str(path)) in result.stderr
    assert result.stdout == ""
    assert_no_traceback(result.stderr)
    if kind == "missing-folder":
        assert not (tmp_path / "no").exists()
    else:
        assert (tmp_path / "regular-file").read_bytes() == b"plain"
    assert sorted(p.name for p in tmp_path.iterdir()) == ([] if kind == "missing-folder" else ["regular-file"])
