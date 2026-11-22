"""T-REDACT-01-CR tier B (intent): points the change request leaves open.

Each test checks the answer recorded in operator/answer-sheets/T-REDACT-01-CR.md.
"""


def test_i1_same_name_inputs_stop_before_writing(run, workdir):
    (workdir / "a").mkdir()
    (workdir / "b").mkdir()
    (workdir / "a" / "app.log").write_text("a@b.io\n")
    (workdir / "b" / "app.log").write_text("c@d.io\n")
    r = run("--out-dir", "out", "a/app.log", "b/app.log")
    assert r.returncode == 3, r
    assert "app.log" in r.stderr, r
    out = workdir / "out"
    assert not out.exists() or not any(out.iterdir()), r


def test_i2_out_dir_without_files_is_rejected(run, workdir):
    r = run("--out-dir", "out", input="a@b.io\n")
    assert r.returncode == 2, r
    assert r.stderr.strip(), r
    assert "[EMAIL]" not in r.stdout, r


def test_i3_plus_number_that_passes_luhn_is_a_phone(run):
    # 4222222222222 is a valid 13-digit card number.
    r = run(input="ref +4222222222222 end\n")
    assert r.stdout == "ref [PHONE] end\n", r


def test_i4_spaced_phone_number_is_left_alone(run):
    r = run(input="call +1 415 555 2671 now\n")
    assert r.stdout == "call +1 415 555 2671 now\n", r
