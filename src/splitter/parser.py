"""CSV reading, participant-list parsing, and input validation.

Rejections raise the typed :class:`ValidationError` carrying a human-readable
message that names the offending element (research.md Decision 5). ``cli.py`` maps
these to a stderr message + non-zero exit. All amounts are parsed to exact integer
cents via :mod:`splitter.money`.
"""

import csv
from dataclasses import dataclass

from splitter import money

HEADER = ["payer", "amount", "description"]


class ValidationError(Exception):
    """Raised for any malformed input; message names the offending element."""


@dataclass(frozen=True)
class Expense:
    """A single expense read from one CSV data row.

    ``description`` is informational only and never used in computation.
    """

    payer: str
    amount_cents: int
    description: str


def parse_participants(text: str) -> list[str]:
    """Split the ``--participants`` string on commas, trimming each name.

    Rejects an empty list (FR-014) and duplicate names after trimming (spec Edge
    Cases), naming the duplicate. Supplied order is preserved and drives all
    deterministic output (FR-017).
    """
    names = [name.strip() for name in text.split(",")]
    names = [name for name in names if name]

    if not names:
        raise ValidationError("participant list must not be empty")

    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ValidationError(f"duplicate participant name {name!r}")
        seen.add(name)

    return names


def parse_expenses(path: str, participants: list[str]) -> list[Expense]:
    """Read and validate an expenses CSV into a list of :class:`Expense`.

    Enforces the full error taxonomy (data-model.md): unreadable file (FR-011),
    missing/misnamed header or column (FR-002, FR-015), blank payer/amount
    (FR-015), unknown payer (FR-012), and bad amounts (FR-013). Row numbers count
    the header as row 1, so the first data row is row 2.
    """
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
    except OSError as error:
        reason = error.strerror or "unreadable"
        raise ValidationError(
            f"cannot read expenses file {path!r}: {reason.lower()}"
        )

    if not rows:
        raise ValidationError(
            "CSV header must have columns: payer, amount, description"
        )

    header = [column.strip() for column in rows[0]]
    if header != HEADER:
        raise ValidationError(
            "CSV header must have columns: payer, amount, description"
        )

    participant_set = set(participants)
    expenses: list[Expense] = []
    for line_number, row in enumerate(rows[1:], start=2):
        payer = row[0].strip() if len(row) > 0 else ""
        amount = row[1].strip() if len(row) > 1 else ""
        description = row[2] if len(row) > 2 else ""

        if not payer:
            raise ValidationError(
                f"row {line_number}: missing required field 'payer'"
            )
        if not amount:
            raise ValidationError(
                f"row {line_number}: missing required field 'amount'"
            )
        if payer not in participant_set:
            raise ValidationError(
                f"row {line_number}: payer {payer!r} is not in the participant list"
            )
        try:
            amount_cents = money.parse_to_cents(amount)
        except ValueError as error:
            raise ValidationError(f"row {line_number}: {error}")

        expenses.append(
            Expense(payer=payer, amount_cents=amount_cents, description=description)
        )

    return expenses
