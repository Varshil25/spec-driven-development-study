"""Sign-in lock tests: FR-030, FR-016."""

import statistics
import threading
import time

from conftest import (
    ALICE_PW,
    BOB_PW,
    FakeClock,
    dashboard,
    http,
    post_login,
    session_token,
    stop_server,
)
from loginapp import server

FORM_CT = ("Content-Type", "application/x-www-form-urlencoded")


def fake_server(inproc_server, users_file, clock=None):
    clock = clock or FakeClock()
    srv = inproc_server(users_file, clock=clock.time, sleep=clock.sleep)
    return srv.server_address[1], clock


def set_time(clock, when):
    clock.advance(when - clock.time())


def assert_refused(resp):
    assert resp.status == 401
    assert resp.body == server.login_page(True)
    assert resp.headers_named("Set-Cookie") == []


def assert_signed_in(resp):
    assert resp.status == 303
    assert resp.header("Location") == "/dashboard"
    assert len(resp.headers_named("Set-Cookie")) == 1


def fail_times(port, count, username="alice"):
    for i in range(count):
        assert_refused(post_login(port, username, f"wrong-password-{i}"))


def lock_alice(port, clock):
    """Five wrong passwords in a row; return the time of the fifth failure."""
    fail_times(port, 5)
    return clock.time()


# ---------------------------------------------------------------- FR-030 transitions


def test_fr030_five_failures_lock(users_file, inproc_server):
    """FR-030: after 5 failures in a row, even the correct password gets the standard 401."""
    port, clock = fake_server(inproc_server, users_file)
    fail_times(port, 5)
    assert_refused(post_login(port, "alice", ALICE_PW))


def test_fr030_lock_ends_at_900_seconds(users_file, inproc_server):
    """FR-030: the lock ends exactly 900 s after the fifth failure."""
    port, clock = fake_server(inproc_server, users_file)
    locked_at = lock_alice(port, clock)
    set_time(clock, locked_at + 899)
    assert_refused(post_login(port, "alice", ALICE_PW))
    set_time(clock, locked_at + 900)
    assert_signed_in(post_login(port, "alice", ALICE_PW))


def test_fr030_success_resets_count(users_file, inproc_server):
    """FR-030: a successful sign-in resets the failure count to zero."""
    port, clock = fake_server(inproc_server, users_file)
    fail_times(port, 4)
    assert_signed_in(post_login(port, "alice", ALICE_PW))
    fail_times(port, 4)
    assert_signed_in(post_login(port, "alice", ALICE_PW))


def test_fr030_locked_attempts_not_counted_or_extending(users_file, inproc_server):
    """FR-030: attempts while locked are refused, are not counted and do not extend the lock."""
    port, clock = fake_server(inproc_server, users_file)
    locked_at = lock_alice(port, clock)
    for offset in (1, 899):
        set_time(clock, locked_at + offset)
        assert_refused(post_login(port, "alice", "wrong-password-x"))
        assert_refused(post_login(port, "alice", ALICE_PW))
    set_time(clock, locked_at + 900)
    assert_signed_in(post_login(port, "alice", ALICE_PW))
    fail_times(port, 4)
    assert_signed_in(post_login(port, "alice", ALICE_PW))


def test_fr030_lock_is_per_username(users_file, inproc_server):
    """FR-030: a lock applies to one username only."""
    port, clock = fake_server(inproc_server, users_file)
    lock_alice(port, clock)
    assert_signed_in(post_login(port, "bob", BOB_PW))
    assert_refused(post_login(port, "alice", ALICE_PW))


def test_fr030_unknown_case_variant_and_malformed_not_counted(users_file, inproc_server):
    """FR-030: unknown usernames, case variants and malformed submissions count for no one."""
    port, clock = fake_server(inproc_server, users_file)
    fail_times(port, 5, username="nobody")
    fail_times(port, 5, username="ALICE")
    malformed = [b"username=alice&password=", b"username=alice&password=wrong-1&password=wrong-2"]
    for i in range(5):
        assert_refused(http(port, "POST", "/login", headers=[FORM_CT], body=malformed[i % 2]))
    assert_signed_in(post_login(port, "alice", ALICE_PW))


# ---------------------------------------------------------------- FR-030 sessions, concurrency, restarts


def test_fr030_existing_session_survives_lock(users_file, inproc_server):
    """FR-030: a lock affects only new sign-ins; existing sessions stay valid."""
    port, clock = fake_server(inproc_server, users_file)
    token = session_token(post_login(port, "alice", ALICE_PW))
    fail_times(port, 5)
    assert_refused(post_login(port, "alice", ALICE_PW))
    assert dashboard(port, token).status == 200


def test_fr030_concurrent_failures_lock(users_file, inproc_server):
    """FR-030: 10 simultaneous wrong passwords lock the username."""
    port, clock = fake_server(inproc_server, users_file)
    barrier = threading.Barrier(10)
    statuses = []
    statuses_lock = threading.Lock()

    def attempt(i):
        barrier.wait(timeout=10)
        status = post_login(port, "alice", f"wrong-password-{i}").status
        with statuses_lock:
            statuses.append(status)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert statuses == [401] * 10
    assert_refused(post_login(port, "alice", ALICE_PW))


def test_fr030_new_server_has_no_locks(users_file, inproc_server):
    """FR-030: failure counts and locks are kept only while the server runs."""
    clock = FakeClock()
    first = inproc_server(users_file, clock=clock.time, sleep=clock.sleep)
    lock_alice(first.server_address[1], clock)
    assert_refused(post_login(first.server_address[1], "alice", ALICE_PW))
    stop_server(first)
    second = inproc_server(users_file, clock=clock.time, sleep=clock.sleep)
    assert_signed_in(post_login(second.server_address[1], "alice", ALICE_PW))


def test_fr030_locked_response_identical(users_file, inproc_server):
    """FR-030: the locked response equals an ordinary failure in status, headers (apart from Date) and body."""
    port, clock = fake_server(inproc_server, users_file)
    lock_alice(port, clock)
    locked = post_login(port, "alice", ALICE_PW)
    wrong = post_login(port, "bob", "wrong-password-1")
    unknown = post_login(port, "nobody", "wrong-password-1")
    for resp in (locked, wrong, unknown):
        assert_refused(resp)
    assert locked.body == wrong.body == unknown.body
    assert locked.headers_without_date() == wrong.headers_without_date() == unknown.headers_without_date()


# ---------------------------------------------------------------- FR-016


def _timed(port, username, password):
    start = time.perf_counter()
    resp = post_login(port, username, password)
    elapsed = time.perf_counter() - start
    assert_refused(resp)
    return elapsed


def test_fr016_failure_timing_within_factor_2(users_file, inproc_server):
    """FR-016: unknown-username, wrong-password and locked-username failures have medians within 2x."""
    port = inproc_server(users_file).server_address[1]
    fail_times(port, 5)  # lock alice (real clock: 900 s)
    unknown, wrong, locked = [], [], []
    for i in range(7):
        unknown.append(_timed(port, "nobody", f"wrong-password-{i}"))
        wrong.append(_timed(port, "bob", f"wrong-password-{i}"))
        locked.append(_timed(port, "alice", ALICE_PW))
        if i % 4 == 3:
            assert_signed_in(post_login(port, "bob", BOB_PW))  # keep bob unlocked (untimed)
    medians = [statistics.median(x) for x in (unknown, wrong, locked)]
    assert max(medians) / min(medians) <= 2, medians
