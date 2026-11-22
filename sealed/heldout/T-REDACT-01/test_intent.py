"""T-REDACT-01 tier B (intent): points the task description leaves open.

Each test checks the answer recorded in the product-owner answer sheet
(operator/answer-sheets/T-REDACT-01.md). An implementation can only be
expected to match these if it asked, or guessed the same way.
"""


def test_i1_missing_file_among_several_does_not_stop_processing(run, workdir):
    (workdir / "a.log").write_text("first a@x.io\n")
    (workdir / "c.log").write_text("third 10.0.0.1\n")
    r = run("a.log", "missing.log", "c.log")
    assert r.returncode == 2, r
    assert "first [EMAIL]" in r.stdout
    assert "third [IP]" in r.stdout
    assert "missing.log" in r.stderr


def test_i2_count_is_one_total_line_for_all_inputs(run, workdir):
    (workdir / "a.log").write_text("a@x.io\n")
    (workdir / "b.log").write_text("b@y.io 10.0.0.1\n")
    r = run("--count", "a.log", "b.log")
    assert r.returncode == 0, r
    summaries = [line for line in r.stderr.splitlines() if "emails=" in line]
    assert summaries == ["emails=2 ips=1 cards=0"], r


def test_i3_longer_dotted_number_is_not_an_ip(run):
    r = run(input="version 1.2.3.4.5 released\n")
    assert r.stdout == "version 1.2.3.4.5 released\n", r


def test_i4_digit_run_longer_than_19_is_not_a_card(run):
    # The first 16 digits alone would be a valid card number.
    r = run(input="id 41111111111111111234 end\n")
    assert r.stdout == "id 41111111111111111234 end\n", r
