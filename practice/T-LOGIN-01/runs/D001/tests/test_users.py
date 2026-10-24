import json
import os
import stat

import pytest

from loginapp import users


@pytest.mark.parametrize("name", ["abc", "a" * 32, "Alice_99", "___", "A1b"])
def test_valid_usernames(name):
    assert users.is_valid_username(name)


@pytest.mark.parametrize("name", [
    "", "ab", "a" * 33, "bad-name", "has space", "dot.ted", "émile", "abc\n", "１２３", None, 123,
])
def test_invalid_usernames(name):
    assert not users.is_valid_username(name)


def test_password_length():
    assert not users.is_valid_password("x" * 11)
    assert users.is_valid_password("x" * 12)


def test_hash_is_salted_and_verifies():
    first = users.hash_password("correct-horse-battery")
    second = users.hash_password("correct-horse-battery")
    assert first != second
    assert first.startswith("scrypt$")
    assert "correct-horse-battery" not in first
    assert users.verify_password("correct-horse-battery", first)
    assert users.verify_password("correct-horse-battery", second)
    assert not users.verify_password("correct-horse-batterz", first)


@pytest.mark.parametrize("stored", [
    "", "garbage", "plain-text-password", "md5$abc", "scrypt$1$8$1$AAAA$AAAA",
    "scrypt$16384$8$1$not base64$AAAA", "scrypt$1048576$64$64$AAAA$AAAA",
])
def test_malformed_stored_hash_never_matches(stored):
    assert not users.verify_password("anything-at-all", stored)


def test_add_user_creates_private_file(tmp_path, fast_hashing):
    path = tmp_path / "users.json"
    users.add_user(path, "alice", "correct-horse-battery")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    document = json.loads(path.read_text())
    assert set(document["users"]) == {"alice"}
    assert "correct-horse-battery" not in path.read_text()
    assert users.verify_password("correct-horse-battery", users.load_users(path)["alice"])


def test_add_user_keeps_existing_accounts(tmp_path, fast_hashing):
    path = tmp_path / "users.json"
    users.add_user(path, "alice", "correct-horse-battery")
    users.add_user(path, "bob", "another-long-password")
    assert set(users.load_users(path)) == {"alice", "bob"}


def test_add_existing_user_raises_and_leaves_file_unchanged(tmp_path, fast_hashing):
    path = tmp_path / "users.json"
    users.add_user(path, "alice", "correct-horse-battery")
    before = path.read_bytes()
    with pytest.raises(users.UserExistsError):
        users.add_user(path, "alice", "a-different-password")
    assert path.read_bytes() == before


def test_missing_file_is_empty(tmp_path):
    assert users.load_users(tmp_path / "nope.json") == {}


@pytest.mark.parametrize("content", ["not json", "[]", '{"users": []}', '{"users": {"a": "x"}}', "\xff"])
def test_malformed_file_raises(tmp_path, content):
    path = tmp_path / "users.json"
    path.write_text(content, encoding="latin-1")
    with pytest.raises(users.UsersFileError):
        users.load_users(path)
