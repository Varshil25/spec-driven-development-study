"""Parser tests: happy-path CSV + participant parsing (T009 US1).

Validation/error-taxonomy tests are appended in T014 (US2). Covers FR-002.
"""

import pytest

from splitter.parser import (
    Expense,
    ValidationError,
    parse_expenses,
    parse_participants,
)


def write_csv(tmp_path, text):
    p = tmp_path / "expenses.csv"
    p.write_text(text)
    return str(p)


class TestParseParticipants:
    def test_splits_on_commas(self):
        assert parse_participants("Alice,Bob,Carol") == ["Alice", "Bob", "Carol"]

    def test_trims_surrounding_whitespace(self):
        assert parse_participants(" Alice , Bob ,Carol") == ["Alice", "Bob", "Carol"]

    def test_preserves_supplied_order(self):
        assert parse_participants("Carol,Alice,Bob") == ["Carol", "Alice", "Bob"]


class TestParseExpenses:
    def test_valid_csv_one_expense_per_row(self, tmp_path):
        path = write_csv(
            tmp_path,
            "payer,amount,description\nAlice,30.00,Hotel\nBob,0,none\n",
        )
        exps = parse_expenses(path, ["Alice", "Bob"])
        assert exps == [
            Expense(payer="Alice", amount_cents=3000, description="Hotel"),
            Expense(payer="Bob", amount_cents=0, description="none"),
        ]

    def test_amount_is_int_cents(self, tmp_path):
        path = write_csv(
            tmp_path, "payer,amount,description\nAlice,12.50,Cab\n"
        )
        (expense,) = parse_expenses(path, ["Alice"])
        assert expense.amount_cents == 1250
        assert isinstance(expense.amount_cents, int)

    def test_description_is_informational(self, tmp_path):
        path = write_csv(
            tmp_path, "payer,amount,description\nAlice,5.00,anything here\n"
        )
        (expense,) = parse_expenses(path, ["Alice"])
        assert expense.description == "anything here"


class TestParticipantValidation:
    def test_empty_participant_list_rejected(self):
        with pytest.raises(ValidationError):
            parse_participants("")

    def test_whitespace_only_participant_list_rejected(self):
        with pytest.raises(ValidationError):
            parse_participants("   ")

    def test_duplicate_names_rejected_naming_duplicate(self):
        with pytest.raises(ValidationError, match="Alice"):
            parse_participants("Alice,Bob,Alice")

    def test_duplicate_after_trimming_rejected(self):
        with pytest.raises(ValidationError, match="Alice"):
            parse_participants("Alice, Alice ")


class TestExpenseValidation:
    PARTS = ["Alice", "Bob"]

    def test_missing_file_rejected(self, tmp_path):
        missing = str(tmp_path / "nope.csv")
        with pytest.raises(ValidationError):
            parse_expenses(missing, self.PARTS)

    def test_missing_header_column_rejected(self, tmp_path):
        path = write_csv(tmp_path, "payer,amount\nAlice,5.00\n")
        with pytest.raises(ValidationError):
            parse_expenses(path, self.PARTS)

    def test_misnamed_header_rejected(self, tmp_path):
        path = write_csv(tmp_path, "who,amount,description\nAlice,5.00,x\n")
        with pytest.raises(ValidationError):
            parse_expenses(path, self.PARTS)

    def test_blank_payer_rejected(self, tmp_path):
        path = write_csv(tmp_path, "payer,amount,description\n,5.00,x\n")
        with pytest.raises(ValidationError, match="payer"):
            parse_expenses(path, self.PARTS)

    def test_blank_amount_rejected(self, tmp_path):
        path = write_csv(tmp_path, "payer,amount,description\nAlice,,x\n")
        with pytest.raises(ValidationError, match="amount"):
            parse_expenses(path, self.PARTS)

    def test_unknown_payer_rejected_naming_payer(self, tmp_path):
        path = write_csv(tmp_path, "payer,amount,description\nCarol,5.00,x\n")
        with pytest.raises(ValidationError, match="Carol"):
            parse_expenses(path, self.PARTS)

    def test_non_numeric_amount_rejected(self, tmp_path):
        path = write_csv(tmp_path, "payer,amount,description\nAlice,abc,x\n")
        with pytest.raises(ValidationError, match="abc"):
            parse_expenses(path, self.PARTS)

    def test_negative_amount_rejected(self, tmp_path):
        path = write_csv(tmp_path, "payer,amount,description\nAlice,-5.00,x\n")
        with pytest.raises(ValidationError, match="-5.00"):
            parse_expenses(path, self.PARTS)

    def test_over_precise_amount_rejected(self, tmp_path):
        path = write_csv(tmp_path, "payer,amount,description\nAlice,12.505,x\n")
        with pytest.raises(ValidationError, match="12.505"):
            parse_expenses(path, self.PARTS)

    def test_error_names_the_row(self, tmp_path):
        path = write_csv(
            tmp_path,
            "payer,amount,description\nAlice,5.00,x\nBob,abc,y\n",
        )
        with pytest.raises(ValidationError, match="row 3"):
            parse_expenses(path, self.PARTS)
