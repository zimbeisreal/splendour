# rewards_config.py
from decimal import Decimal

LEVELS = {
    1: {
        "name": "Bronze", "icon": "🥉",
        "referrals_required": 20,
        "investment_required": Decimal("1000000"),
        "reward": Decimal("100000"),
        "rate": Decimal("0.1000"),     # 10.00%
        "salary": Decimal("50000"),
    },
    2: {
        "name": "Silver", "icon": "🥈",
        "referrals_required": 40,
        "investment_required": Decimal("2500000"),
        "reward": Decimal("180000"),
        "rate": Decimal("0.0720"),     # 7.20%
        "salary": Decimal("100000"),
    },
    3: {
        "name": "Gold", "icon": "🥇",
        "referrals_required": 60,
        "investment_required": Decimal("4000000"),
        "reward": Decimal("250000"),
        "rate": Decimal("0.0625"),     # 6.25%
        "salary": Decimal("150000"),
    },
}

SALARY_CYCLE_DAYS = 26
REWARD_ACCRUAL_DIVISOR = Decimal("30")     # daily = invested * rate / 30
CLAIM_COOLDOWN_DAYS = 7
CLAIM_CAP_DAYS = 30

def compute_level(active_invested: Decimal) -> int:
    """Return the level (0-3) the user qualifies for."""
    for lvl in (3, 2, 1):
        if active_invested >= LEVELS[lvl]["investment_required"]:
            return lvl
    return 0