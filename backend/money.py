"""Single source of every money figure. Integer cents only."""
PRICE_CENTS = 109000
SLOTS = 3
FEE_BPS = 290
FEE_FIXED_CENTS = 30
COMPUTE_CENTS = 2000
FLOOR_CENTS = 100000
CURRENCY = "usd"
HOLD_MINUTES = 45


def fee_cents(amount: int) -> int:
    return (amount * FEE_BPS + 5000) // 10000 + FEE_FIXED_CENTS


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)


FEE_PER_CLOSE_CENTS = fee_cents(PRICE_CENTS)
CONTRIBUTION_PER_CLOSE_CENTS = PRICE_CENTS - FEE_PER_CLOSE_CENTS - COMPUTE_CENTS
FULL_REFUND_CONTRIBUTION_CENTS = -(FEE_PER_CLOSE_CENTS + COMPUTE_CENTS)
CLOSES_FOR_FLOOR = ceil_div(FLOOR_CENTS, CONTRIBUTION_PER_CLOSE_CENTS)

assert FEE_PER_CLOSE_CENTS == 3191
assert CONTRIBUTION_PER_CLOSE_CENTS == 103809
assert FULL_REFUND_CONTRIBUTION_CENTS == -5191
assert CLOSES_FOR_FLOOR == 1


def closes_remaining(contribution_cents: int) -> int:
    return max(0, ceil_div(FLOOR_CENTS - contribution_cents, CONTRIBUTION_PER_CLOSE_CENTS))


def as_dict() -> dict:
    return {
        "price_cents": PRICE_CENTS,
        "slots": SLOTS,
        "fee_bps": FEE_BPS,
        "fee_fixed_cents": FEE_FIXED_CENTS,
        "fee_per_close_cents": FEE_PER_CLOSE_CENTS,
        "compute_cents": COMPUTE_CENTS,
        "floor_cents": FLOOR_CENTS,
        "currency": CURRENCY,
        "hold_minutes": HOLD_MINUTES,
        "contribution_per_close_cents": CONTRIBUTION_PER_CLOSE_CENTS,
        "full_refund_contribution_cents": FULL_REFUND_CONTRIBUTION_CENTS,
        "closes_for_floor": CLOSES_FOR_FLOOR,
    }
