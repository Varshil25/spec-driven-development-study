"""Command-line orchestration: argument parsing, output, exit codes.

Results go to stdout, diagnostics to stderr; exit 0 on success (contracts/cli.md).
US2 adds the error-handling branch that maps validation failures to stderr and a
non-zero exit with nothing on stdout.
"""

import argparse
import sys

from splitter import money
from splitter.parser import ValidationError, parse_expenses, parse_participants
from splitter.settle import settle

ALREADY_SETTLED = "Already settled — no payments needed."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="splitter",
        description="Compute a minimal settlement for shared group expenses.",
    )
    parser.add_argument("expenses_csv", help="Path to the CSV file of expenses")
    parser.add_argument(
        "--participants",
        required=True,
        help='Comma-separated participant names, e.g. "Alice,Bob,Carol"',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the tool. Returns the process exit code (0 = success)."""
    args = _build_parser().parse_args(argv)

    # All parsing/validation happens before any stdout write, so a rejection
    # leaves stdout untouched (FR-016; Constitution Principle III).
    try:
        participants = parse_participants(args.participants)
        expenses = parse_expenses(args.expenses_csv, participants)
        payments = settle(participants, expenses)
    except ValidationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not payments:
        print(ALREADY_SETTLED)
        return 0

    for payment in payments:
        print(
            f"{payment.from_name} pays {payment.to_name} "
            f"{money.format_cents(payment.amount_cents)}"
        )
    return 0
