"""Integer-cent money helpers (Constitution Principle II; research.md Decision 1).

Money is represented as ``int`` cents everywhere in the program. ``decimal.Decimal``
is used *only* to parse a human-authored decimal string into an exact cent count,
and formatting back to a decimal string happens *only* at the output boundary. No
float ever holds money.
"""

from decimal import Decimal, InvalidOperation

_CENTS = Decimal(100)


def parse_to_cents(text: str) -> int:
    """Parse a currency string into an exact ``int`` number of cents.

    Accepts a plain decimal with at most two fractional digits (e.g. ``"30.00"``,
    ``"12.5"``, ``"0"``). Rejects non-numeric, negative, and over-precise (more
    than two decimal places) values by raising :class:`ValueError` (FR-013).
    """
    raw = text.strip()
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"amount {text!r} is not a valid number")

    # Reject NaN / infinities, which Decimal accepts as valid literals.
    if not value.is_finite():
        raise ValueError(f"amount {text!r} is not a valid number")

    if value < 0:
        raise ValueError(f"amount {text!r} must not be negative")

    cents = value * _CENTS
    # More than two fractional digits leaves a non-integral cent count.
    if cents != cents.to_integral_value():
        raise ValueError(f"amount {text!r} has more than two decimal places")

    return int(cents)


def format_cents(cents: int) -> str:
    """Render ``int`` cents as a plain decimal with exactly two fractional digits.

    No locale symbol or thousands separator (FR-018). Output-boundary only.
    """
    quotient, remainder = divmod(cents, 100)
    return f"{quotient}.{remainder:02d}"
