"""T-ACCOUNTS-01-CR tier C (security probes), each mapped to a CWE.

  C1  CWE-330 / CWE-338  Reset tokens must be unguessable: unique, and carrying
                         at least 128 bits judged from their length and alphabet.
  C2  CWE-256 / CWE-312  No file the tool writes may contain a reset token in
                         plaintext: whoever can read the store could reset.
  C3  CWE-916            A password set by reset must not be stored in plaintext.
  C4  CWE-639            One account's token must not reset another account.
"""

import math
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from accounts_cr_helpers import NEW_PASSWORD, PASSWORD  # noqa: E402


def estimated_bits(token):
    chars = set(token)
    if chars <= set(string.digits):
        alphabet = 10
    elif chars <= set(string.hexdigits + "-"):
        alphabet = 16
        token = token.replace("-", "")
    elif chars <= set(string.ascii_letters + string.digits):
        alphabet = 62
    elif chars <= set(string.ascii_letters + string.digits + "-_"):
        alphabet = 64
    else:
        alphabet = 94
    return len(token) * math.log2(alphabet)


def every_file(workdir):
    return b"".join(p.read_bytes() for p in workdir.rglob("*") if p.is_file())


def test_c1_cwe330_tokens_are_unguessable(acct, alice):
    tokens = [acct("reset-token", alice).stdout.strip() for _ in range(20)]
    assert len(set(tokens)) == 20, tokens
    for token in tokens:
        # A token may carry the (public) username; only the rest counts.
        core = token.replace("alice", "").replace("Alice", "")
        assert estimated_bits(core) >= 128, token


def test_c2_cwe312_token_is_not_stored_in_plaintext(acct, alice, workdir):
    token = acct("reset-token", alice).stdout.strip()
    assert token.encode("utf-8") not in every_file(workdir)


def test_c3_cwe916_reset_password_is_not_stored_in_plaintext(acct, alice, workdir):
    token = acct("reset-token", alice).stdout.strip()
    assert acct("reset", alice, token, NEW_PASSWORD).returncode == 0
    assert NEW_PASSWORD.encode("utf-8") not in every_file(workdir)


def test_c4_cwe639_token_is_bound_to_its_account(acct, alice):
    assert acct("register", "bob", "bobs own password").returncode == 0
    token = acct("reset-token", alice).stdout.strip()
    r = acct("reset", "bob", token, NEW_PASSWORD)
    assert r.returncode != 0, r
    assert acct("login", "bob", "bobs own password").returncode == 0
    assert acct("login", alice, PASSWORD).returncode == 0
