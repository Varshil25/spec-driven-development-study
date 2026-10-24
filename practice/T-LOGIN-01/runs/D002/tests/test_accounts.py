"""Account record and accounts-file unit tests: FR-005, FR-006."""

import base64
import hashlib
import re
import stat

from conftest import run_cli
from loginapp import accounts

PASSWORD = "correct-horse-battery"


def test_fr005_record_has_pinned_scrypt_settings():
    """FR-005: a record stores only scrypt with the pinned settings, a salt and a hash."""
    rec = accounts.make_record(PASSWORD)
    assert set(rec) == {"algorithm", "n", "r", "p", "salt", "hash"}
    assert rec["algorithm"] == "scrypt"
    assert rec["n"] == 131072 and type(rec["n"]) is int
    assert rec["r"] == 8 and type(rec["r"]) is int
    assert rec["p"] == 1 and type(rec["p"]) is int
    assert re.fullmatch(r"[0-9a-f]{32}", rec["salt"])
    assert re.fullmatch(r"[0-9a-f]{64}", rec["hash"])
    assert accounts.SCRYPT_N == 2**17
    assert accounts.SCRYPT_R == 8
    assert accounts.SCRYPT_P == 1
    assert accounts.DKLEN == 32
    assert accounts.SALT_BYTES == 16


def test_fr005_hash_matches_hashlib_scrypt():
    """FR-005: the stored hash is hashlib.scrypt over the UTF-8 password with the stored salt."""
    rec = accounts.make_record(PASSWORD)
    expected = hashlib.scrypt(
        PASSWORD.encode("utf-8"),
        salt=bytes.fromhex(rec["salt"]),
        n=131072,
        r=8,
        p=1,
        dklen=32,
        maxmem=268435456,
    ).hex()
    assert expected == rec["hash"]
    assert accounts.verify(PASSWORD, rec) is True
    assert accounts.verify("correct-horse-batterz", rec) is False


def test_fr005_same_password_different_records():
    """FR-005: two accounts with the same password get different salts and hashes."""
    first = accounts.make_record(PASSWORD)
    second = accounts.make_record(PASSWORD)
    assert first["salt"] != second["salt"]
    assert first["hash"] != second["hash"]


def test_fr005_password_absent_from_file(tmp_path):
    """FR-005: the password appears in the accounts file in no readable form."""
    result = run_cli("adduser", "alice", "--users", "users.json", stdin=(PASSWORD + "\n").encode(), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    data = (tmp_path / "users.json").read_bytes()
    raw = PASSWORD.encode("utf-8")
    for needle in (
        raw,
        raw.hex().encode("ascii"),
        base64.b64encode(raw),
        base64.urlsafe_b64encode(raw),
        base64.b64encode(raw).rstrip(b"="),
    ):
        assert needle not in data


def test_fr006_save_sets_mode_0600_and_leaves_no_temp_file(tmp_path):
    """FR-006: save() writes the file with owner-only mode 0600 and leaves no temporary file."""
    path = tmp_path / "users.json"
    rec = {
        "algorithm": "scrypt",
        "n": 131072,
        "r": 8,
        "p": 1,
        "salt": "00112233445566778899aabbccddeeff",
        "hash": "ab" * 32,
    }
    accounts.save(str(path), {"alice": rec})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(tmp_path.glob(".users.json.*.tmp")) == []
    assert accounts.load(str(path), missing_ok=False) == {"alice": rec}
