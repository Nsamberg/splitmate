"""Money is handled as integer cents everywhere to avoid floating-point rounding
bugs. These helpers are the only place dollar strings get parsed/formatted."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def parse_amount_to_cents(amount_str: str) -> int:
    """Parse a user-entered amount (e.g. "12.5") into integer cents.

    Raises ValueError if the input isn't a valid positive amount.
    """
    if not amount_str or not amount_str.strip():
        raise ValueError("Amount is required")
    try:
        value = Decimal(amount_str.strip())
    except InvalidOperation as exc:
        raise ValueError("Invalid amount") from exc
    if value <= 0:
        raise ValueError("Amount must be greater than zero")
    cents = (value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def split_equally(total_cents: int, participant_count: int) -> list[int]:
    """Split total_cents equally among participant_count people.

    Any leftover cent(s) from integer division go to the first participants,
    so the shares always sum back up to exactly total_cents.
    """
    if participant_count <= 0:
        raise ValueError("Need at least one participant")
    base = total_cents // participant_count
    remainder = total_cents - base * participant_count
    shares = [base] * participant_count
    for i in range(remainder):
        shares[i] += 1
    return shares
