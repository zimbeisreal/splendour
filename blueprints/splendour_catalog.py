"""
Splendour product catalog + request validators.

SINGLE SOURCE OF TRUTH for every investment product. Pure Python (no Flask, no DB) so it is
unit-testable. The frontend's js/catalog.js is GENERATED from this file:

    python splendour_catalog.py --emit-js > js/catalog.js

Money rules (confirmed by the business):
  * Daily plans: 0.03% of the amount per day, 26 days, credited by the backend every 24 hours,
    the invested amount is returned at the end.
  * Lock plans: fixed payout after a fixed number of days (payout = amount + profit).
  * Deposits: minimum UGX 20,000.
The client is never trusted for amounts, rates, payouts or lock terms: it only names a product key.
"""
import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

# ------------------------------------------------------------------ plan tables (edit here only)
DAILY_RATE_PCT = Decimal("0.03")     # percent per day
DAILY_DAYS = 26
DAILY_PLANS = [("Quartz", 20000), ("Topaz", 40000), ("Amber", 60000), ("Garnet", 100000),
               ("Opal", 200000), ("Citrine", 300000), ("Sapphire", 500000), ("Emerald", 700000),
               ("Ruby", 1000000), ("Amethyst", 2000000), ("Diamond", 4000000)]
# (amount locked, total paid at maturity, days)
LOCK_PLANS = [(50000, 52000, 30), (80000, 83000, 30), (100000, 105000, 60), (150000, 160000, 30),
              (200000, 210000, 50), (500000, 550000, 120), (1000000, 1060000, 120)]

MIN_DEPOSIT = 20000
MAX_DEPOSIT = 10_000_000
MIN_INVEST = min(a for _, a in DAILY_PLANS)
_PHONE_RE = re.compile(r"^07\d{8}$")
_PHONE_PREFIXES = {"70", "73", "74", "75", "76", "77", "78", "79"}   # Airtel + MTN, matches detect_provider()


def _tag(a):
    return f"{a // 1_000_000}M" if a >= 1_000_000 else f"{a // 1000}K"


def _money(d):
    return int(Decimal(d).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _build():
    cat = {}
    for name, amount in DAILY_PLANS:
        daily = Decimal(amount) * DAILY_RATE_PCT / Decimal(100)
        profit = daily * DAILY_DAYS
        total = Decimal(amount) + profit
        key = f"daily_{amount}"
        cat[key] = {
            "name": f"{name} {_tag(amount)}", "display_name": name, "amount": amount,
            "bonus_percentage": float(DAILY_RATE_PCT), "duration_days": DAILY_DAYS,
            "reward_description": f"Invest UGX {amount:,}. Earn UGX {_money(daily):,} a day for {DAILY_DAYS} days. "
                                  f"Total returns: UGX {_money(total):,}.",
            "features": {"daily_profit": float(daily), "total_profit": float(profit), "total_returns": float(total),
                         "capital": amount, "daily_rate": float(DAILY_RATE_PCT), "total_rate": float(DAILY_RATE_PCT * DAILY_DAYS),
                         "referral_bonus": 0, "support_level": "Daily", "machine_emoji": ""},
            "is_active": True, "is_locking_package": False, "locking_bonus_rate": 0.0,
            "machine_eligible": True, "machine_type": "daily",
            "lock_minimum_days": 0, "lock_maximum_days": 0, "lock_bonus_tiers": {},
        }
    for amount, payout, days in LOCK_PLANS:
        profit = payout - amount
        rate = round(profit / amount * 100, 4)
        key = f"lock_{amount}_{days}"
        cat[key] = {
            "name": f"Vault {_tag(amount)}", "display_name": f"Vault {_tag(amount)}", "amount": amount,
            "bonus_percentage": rate, "duration_days": days,
            "reward_description": f"Lock UGX {amount:,} for {days} days. Total payout: UGX {payout:,}.",
            "features": {"daily_profit": 0, "total_profit": profit, "total_returns": payout,
                         "capital": amount, "daily_rate": 0.0, "total_rate": rate,
                         "referral_bonus": 0, "support_level": f"{days}-Day", "machine_emoji": ""},
            "is_active": True, "is_locking_package": True, "locking_bonus_rate": 0.0,
            "machine_eligible": True, "machine_type": "locked",
            "lock_minimum_days": days, "lock_maximum_days": days, "lock_bonus_tiers": {},
        }
    return cat


CATALOG = _build()


# ------------------------------------------------------------------ helpers
def err(message, code, status):
    return {"error": message, "code": code}, status


def _int(v):
    """Strict whole-number parse. Rejects bool, fractions, negatives, junk."""
    if isinstance(v, bool):
        raise ValueError
    if isinstance(v, int):
        if v < 0:
            raise ValueError
        return v
    if isinstance(v, float) and v.is_integer() and v >= 0:
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    raise ValueError


def lock_details_for(key):
    """Server-computed lock terms. total_return is the FULL payout (amount + profit): the maturity
    transfer moves Package.lock_earnings into actual_balance and the amount was already deducted."""
    c = CATALOG[key]
    if not c["is_locking_package"]:
        return None
    f = c["features"]
    return {"is_locking": True, "lock_days": c["duration_days"], "duration_days": c["duration_days"],
            "bonus_percentage": 0.0, "daily_rate": 0.0, "daily_return": Decimal("0"),
            "total_return": Decimal(str(f["total_returns"])), "profit": Decimal(str(f["total_profit"])),
            "principal": Decimal(str(c["amount"])), "base_rate": f["total_rate"]}


# ------------------------------------------------------------------ validators (return (data, None) or (None, (body, status)))
def validate_investment(data):
    """Buying a plan with the user's balance. No phone, no payment method."""
    if not isinstance(data, dict):
        return None, err("Invalid request", "BAD_REQUEST", 400)
    product = data.get("product")
    if not isinstance(product, str) or not product.strip():
        return None, err("Product name required", "PRODUCT_REQUIRED", 400)
    key = product.strip().lower()
    catalog = CATALOG.get(key)
    if not catalog or not catalog["is_active"]:
        return None, err("This product is not available.", "PRODUCT_NOT_FOUND", 404)
    try:
        amount = _int(data.get("amount"))
    except ValueError:
        return None, err("Invalid amount", "AMOUNT_INVALID", 400)
    if amount != catalog["amount"]:
        return None, err(f"Amount mismatch. Expected: {catalog['amount']}, Got: {amount}", "AMOUNT_MISMATCH", 400)

    is_lock = catalog["is_locking_package"]
    claimed = data.get("lock_days")
    if claimed not in (None, "", 0, "0"):
        try:
            claimed = _int(claimed)
        except ValueError:
            return None, err("Invalid lock days", "LOCK_DAYS_INVALID", 400)
        if not is_lock:
            return None, err("This product does not support locking.", "LOCK_NOT_SUPPORTED", 400)
        if claimed != catalog["duration_days"]:
            return None, err(f"Lock days must be {catalog['duration_days']}", "LOCK_DAYS_MISMATCH", 400)
    # data.get("lock_total"), "phone", "payment_method" are deliberately ignored.
    return {"amount": amount, "phone": None, "product": key, "product_name": catalog["name"],
            "payment_type": "package", "payment_method": "balance", "catalog": catalog,
            "lock_days": catalog["duration_days"] if is_lock else 0, "is_locking": is_lock,
            "lock_details": lock_details_for(key)}, None


def validate_deposit(data):
    """Mobile money deposit: minimum UGX 20,000, phone 07XXXXXXXX."""
    if not isinstance(data, dict):
        return None, err("Invalid request", "BAD_REQUEST", 400)
    try:
        amount = _int(data.get("amount"))
    except ValueError:
        return None, err("Invalid amount", "AMOUNT_INVALID", 400)
    if amount < MIN_DEPOSIT:
        return None, err(f"Minimum deposit is UGX {MIN_DEPOSIT:,}", "DEPOSIT_TOO_SMALL", 400)
    if amount > MAX_DEPOSIT:
        return None, err(f"Maximum deposit is UGX {MAX_DEPOSIT:,}", "DEPOSIT_TOO_LARGE", 400)
    phone = str(data.get("phone") or "").strip().replace(" ", "")
    if not _PHONE_RE.match(phone):
        return None, err("Phone must be 10 digits starting with 07.", "PHONE_INVALID", 400)
    if os.environ.get("PESAJET_SANDBOX") != "1" and phone[1:3] not in _PHONE_PREFIXES:
        return None, err("We support MTN and Airtel numbers only.", "PHONE_NETWORK", 400)
    return {"amount": amount, "phone": phone, "payment_type": "deposit"}, None


# ------------------------------------------------------------------ public views
def public_catalog():
    """What the frontend needs. Numbers are plain ints/floats."""
    out = []
    for key, c in CATALOG.items():
        if not c["is_active"]:
            continue
        f = c["features"]
        out.append({"key": key, "name": c["display_name"], "kind": "lock" if c["is_locking_package"] else "daily",
                    "amount": c["amount"], "days": c["duration_days"], "daily": _money(f["daily_profit"]),
                    "profit": _money(f["total_profit"]), "total": _money(f["total_returns"])})
    return out


def emit_js():
    body = json.dumps({"minDeposit": MIN_DEPOSIT, "minInvest": MIN_INVEST, "plans": public_catalog()}, indent=1)
    return "/* GENERATED from backend splendour_catalog.py. Do not edit by hand. */\nwindow.SPLENDOUR_CATALOG = " + body + ";\n"


if __name__ == "__main__":
    if "--emit-js" in sys.argv:
        sys.stdout.write(emit_js())
    else:
        print(json.dumps(public_catalog(), indent=1))
