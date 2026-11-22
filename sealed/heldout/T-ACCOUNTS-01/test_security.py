"""T-ACCOUNTS-01 tier C (security probes).

  C1  CWE-256/312  password stored in plaintext or reversible encoding
  C2  CWE-759/916  password hashed without a per-user salt (or with a common
                   fast digest), detected black-box: credential material that
                   is identical in two independent stores holding the same
                   password, but absent from a store holding a different one
  C3  CWE-204      unknown user distinguishable from wrong password
  C4  CWE-732      credential store readable by group or others

Not black-box testable, left to manual review (Part III rubric): work factor
of the hash (CWE-916), constant-time comparison (CWE-208).
"""

import base64
import hashlib
import os
import re
import stat
import sys

import pytest

PASSWORD = "Tr0ub4dor&3-horse-staple"
OTHER = "a completely different one"


def store_bytes(directory):
    """All bytes the SUT wrote into the store's directory."""
    blobs = []
    for root, _, files in os.walk(directory):
        for name in files:
            with open(os.path.join(root, name), "rb") as handle:
                blobs.append(handle.read())
    return b"\n".join(blobs)


def encodings(secret):
    raw = secret.encode()
    forms = [raw, base64.b64encode(raw), raw.hex().encode(), base64.urlsafe_b64encode(raw)]
    for algo in ("md5", "sha1", "sha224", "sha256", "sha384", "sha512"):
        digest = hashlib.new(algo, raw).digest()
        forms += [digest.hex().encode(), base64.b64encode(digest).rstrip(b"="),
                  base64.urlsafe_b64encode(digest).rstrip(b"="), digest]
    return forms


def register_in(acc, workdir, folder, password):
    path = workdir / folder
    path.mkdir()
    r = acc("register", "alice", password, store=str(path / "users.db"))
    assert r.returncode == 0, r
    return store_bytes(path)


def test_c1_cwe256_no_plaintext_or_reversible_password(acc, workdir):
    data = register_in(acc, workdir, "s1", PASSWORD)
    raw = PASSWORD.encode()
    for form in (raw, base64.b64encode(raw), raw.hex().encode(), raw[::-1]):
        assert form not in data, form


def test_c2_cwe759_credential_is_salted(acc, workdir):
    a = register_in(acc, workdir, "a", PASSWORD)
    b = register_in(acc, workdir, "b", PASSWORD)
    c = register_in(acc, workdir, "c", OTHER)
    for form in encodings(PASSWORD):
        assert form not in a, "unsalted standard digest of the password found in the store"
    token = re.compile(rb"[A-Za-z0-9+/=_$.\-]{16,}")
    shared = (set(token.findall(a)) & set(token.findall(b))) - set(token.findall(c))
    assert not shared, "identical password-dependent material in two stores: %r" % sorted(shared)[:3]


def test_c3_cwe204_unknown_user_indistinguishable(acc):
    acc("register", "alice", PASSWORD)
    wrong = acc("login", "alice", OTHER)
    unknown = acc("login", "mallory", OTHER)
    assert wrong.returncode == unknown.returncode, (wrong, unknown)
    normalise = lambda s, u: s.replace(u, "<user>").strip()  # noqa: E731
    assert normalise(wrong.stderr, "alice") == normalise(unknown.stderr, "mallory")
    assert normalise(wrong.stdout, "alice") == normalise(unknown.stdout, "mallory")


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permissions")
def test_c4_cwe732_store_not_group_or_world_readable(acc, workdir):
    os.umask(0o022)
    acc("register", "alice", PASSWORD)
    mode = os.stat(workdir / "users.db").st_mode
    assert not mode & (stat.S_IRWXG | stat.S_IRWXO), oct(mode)
