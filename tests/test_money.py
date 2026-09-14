import pytest

from app.money import format_cents, parse_amount_to_cents, split_equally


def test_parse_amount_to_cents():
    assert parse_amount_to_cents("12.34") == 1234
    assert parse_amount_to_cents("5") == 500
    assert parse_amount_to_cents("0.1") == 10


def test_parse_amount_rejects_non_positive_or_invalid():
    with pytest.raises(ValueError):
        parse_amount_to_cents("0")
    with pytest.raises(ValueError):
        parse_amount_to_cents("-5")
    with pytest.raises(ValueError):
        parse_amount_to_cents("abc")
    with pytest.raises(ValueError):
        parse_amount_to_cents("")


def test_format_cents():
    assert format_cents(1234) == "12.34"
    assert format_cents(5) == "0.05"
    assert format_cents(-150) == "-1.50"
    assert format_cents(0) == "0.00"


def test_split_equally_exact():
    assert split_equally(300, 3) == [100, 100, 100]


def test_split_equally_with_remainder_sums_to_total():
    shares = split_equally(100, 3)
    assert sum(shares) == 100
    assert shares == [34, 33, 33]


def test_split_equally_rejects_zero_participants():
    with pytest.raises(ValueError):
        split_equally(100, 0)
