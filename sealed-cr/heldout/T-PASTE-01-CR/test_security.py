"""T-PASTE-01-CR tier C (security probes), each mapped to a CWE.

  C1  CWE-362  Race condition: concurrent reads of a burn-after-reading paste
               must deliver it at most once.
  C2  CWE-256  Paste passwords must not be stored in plaintext.
  C3  CWE-200  A paste's password must never appear in any response.

That a failed (403) read does not burn a protected paste follows from the
stated rule ("the first successful read ... deletes it"), so it is tested in
tier A (test_s12), not here.
"""

import threading


def concurrent_reads(server, path, count=20):
    barrier = threading.Barrier(count)
    statuses = []
    lock = threading.Lock()

    def read():
        barrier.wait()
        r = server.request("GET", path, timeout=20)
        with lock:
            statuses.append(r.status)

    threads = [threading.Thread(target=read) for _ in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return statuses


ROUNDS = 20  # one round catches a read-then-delete race about a third of the time


def test_c1_cwe362_burn_paste_is_delivered_at_most_once(server):
    for _ in range(ROUNDS):
        paste = server.create("x" * 60_000, burn_after_reading=True)
        statuses = concurrent_reads(server, "/pastes/%s/raw" % paste["id"])
        assert statuses.count(200) <= 1, statuses


def test_c2_cwe256_password_is_not_stored_in_plaintext(server):
    password = "correct-horse-battery-staple-42"
    server.create("hello", password=password)
    stored = b"".join(p.read_bytes() for p in server.data_dir.rglob("*") if p.is_file())
    assert password.encode("utf-8") not in stored


def test_c3_cwe200_password_is_never_echoed(server):
    password = "do-not-echo-me-9876"
    created = server.request("POST", "/pastes", {"content": "hello", "password": password})
    assert created.status == 201, created
    paste_id = created.json()["id"]
    bodies = [created.text]
    for path in ("/pastes/%s" % paste_id, "/pastes/%s/raw" % paste_id):
        bodies.append(server.request("GET", path, headers={"X-Paste-Password": password}).text)
        bodies.append(server.request("GET", path, headers={"X-Paste-Password": "wrong"}).text)
    assert all(password not in body for body in bodies), bodies
