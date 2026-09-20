"""Tests for integer-cent parsing/formatting (T006).

Covers FR-009 (exact integer cents), FR-013 (reject bad amounts), FR-018
(two-fractional-digit output). Money is `int` cents throughout; no float ever
holds money (Constitution Principle II).
"""

import pytest

from splitter.money import format_cents, parse_to_cents


class TestParseToCents:
    def test_whole_dollars(self):
        assert parse_to_cents("30.00") == 3000

    def test_zero(self):
        assert parse_to_cents("0") == 0

    def test_fractional(self):
        assert parse_to_cents("12.50") == 1250

    def test_single_decimal_place(self):
        assert parse_to_cents("12.5") == 1250

    def test_integer_dollars_no_decimal(self):
        assert parse_to_cents("30") == 3000

    def test_rejects_non_numeric(self):
        with pytest.raises(ValueError):
            parse_to_cents("abc")

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            parse_to_cents("-5.00")

    def test_rejects_more_than_two_decimals(self):
        with pytest.raises(ValueError):
            parse_to_cents("12.505")


class TestFormatCents:
    def test_two_fractional_digits(self):
        assert format_cents(1500) == "15.00"

    def test_sub_dollar(self):
        assert format_cents(5) == "0.05"

    def test_zero(self):
        assert format_cents(0) == "0.00"

    def test_no_locale_symbol(self):
        rendered = format_cents(123456)
        assert rendered == "1234.56"
        assert "$" not in rendered and "," not in rendered
