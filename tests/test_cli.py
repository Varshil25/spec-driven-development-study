"""End-to-end CLI tests (T010 US1; T015/T020/T023 appended later).

Exercises the process-level contract in contracts/cli.md via ``cli.main`` with
captured stdout/stderr and return code. Covers FR-010, FR-017, FR-018.
"""

from splitter.cli import main


def write_csv(tmp_path, text, name="expenses.csv"):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


class TestSuccessOutput:
    def test_basic_settlement(self, tmp_path, capsys):
        path = write_csv(
            tmp_path,
            "payer,amount,description\nAlice,30.00,Hotel\nBob,0,none\n",
        )
        rc = main([path, "--participants", "Alice,Bob"])
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.out == "Bob pays Alice 15.00\n"
        assert captured.err == ""

    def test_already_settled(self, tmp_path, capsys):
        path = write_csv(
            tmp_path,
            "payer,amount,description\nAlice,10.00,Lunch\nBob,10.00,Dinner\n",
        )
        rc = main([path, "--participants", "Alice,Bob"])
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.out.strip() == "Already settled — no payments needed."
        assert captured.err == ""


class TestErrorOutput:
    """Every malformed variant: non-zero exit, empty stdout, clear stderr."""

    def _assert_fails(self, capsys, rc, names):
        captured = capsys.readouterr()
        assert rc != 0
        assert captured.out == ""  # no partial/best-guess settlement (FR-016)
        assert names in captured.err

    def test_missing_file(self, tmp_path, capsys):
        rc = main([str(tmp_path / "nope.csv"), "--participants", "Alice,Bob"])
        self._assert_fails(capsys, rc, "nope.csv")

    def test_unknown_payer(self, tmp_path, capsys):
        path = write_csv(tmp_path, "payer,amount,description\nCarol,5.00,x\n")
        rc = main([path, "--participants", "Alice,Bob"])
        self._assert_fails(capsys, rc, "Carol")

    def test_negative_amount(self, tmp_path, capsys):
        path = write_csv(tmp_path, "payer,amount,description\nAlice,-5.00,x\n")
        rc = main([path, "--participants", "Alice,Bob"])
        self._assert_fails(capsys, rc, "-5.00")

    def test_over_precise_amount(self, tmp_path, capsys):
        path = write_csv(tmp_path, "payer,amount,description\nAlice,12.505,x\n")
        rc = main([path, "--participants", "Alice,Bob"])
        self._assert_fails(capsys, rc, "12.505")

    def test_empty_participant_list(self, tmp_path, capsys):
        path = write_csv(tmp_path, "payer,amount,description\nAlice,5.00,x\n")
        rc = main([path, "--participants", ""])
        self._assert_fails(capsys, rc, "participant")

    def test_missing_header_column(self, tmp_path, capsys):
        path = write_csv(tmp_path, "payer,amount\nAlice,5.00\n")
        rc = main([path, "--participants", "Alice,Bob"])
        self._assert_fails(capsys, rc, "header")

    def test_duplicate_participants(self, tmp_path, capsys):
        path = write_csv(tmp_path, "payer,amount,description\nAlice,5.00,x\n")
        rc = main([path, "--participants", "Alice,Alice"])
        self._assert_fails(capsys, rc, "Alice")


class TestUnevenSplit:
    """US3 (T020): uneven split conserves every cent end to end (Scenario 3)."""

    def _parse_payments(self, out):
        # Lines look like "Bob pays Alice 3.34".
        payments = []
        for line in out.splitlines():
            debtor, _pays, creditor, amount = line.split()
            payments.append((debtor, creditor, int(round(float(amount) * 100))))
        return payments

    def test_uneven_split_zeroes_all_balances(self, tmp_path, capsys):
        path = write_csv(tmp_path, "payer,amount,description\nAlice,10.00,Coffee\n")
        rc = main([path, "--participants", "Alice,Bob,Carol"])
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.err == ""

        payments = self._parse_payments(captured.out)
        # Alice paid 1000, shares 334/333/333 -> nets +666 / -333 / -333.
        nets = {"Alice": 666, "Bob": -333, "Carol": -333}
        assert sum(amt for _f, _t, amt in payments) == 666  # total imbalance
        for debtor, creditor, amount in payments:
            nets[debtor] += amount
            nets[creditor] -= amount
        assert all(v == 0 for v in nets.values())


class TestDeterminism:
    """Polish (T023): two runs on identical input are byte-identical (SC-005)."""

    def test_output_is_byte_identical_across_runs(self, tmp_path, capsys):
        path = write_csv(tmp_path, "payer,amount,description\nAlice,10.00,Coffee\n")

        main([path, "--participants", "Alice,Bob,Carol"])
        first = capsys.readouterr().out
        main([path, "--participants", "Alice,Bob,Carol"])
        second = capsys.readouterr().out

        assert first == second
        assert first != ""
