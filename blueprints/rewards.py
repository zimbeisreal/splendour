# blueprints/rewards.py
from decimal import Decimal
from datetime import datetime, timezone
from flask import Blueprint, jsonify, session

from extensions import db
from models import User, Package, Referral, Transaction, Wallet, RewardsLedger

bp = Blueprint("rewards", __name__)


# ============================================================
# CONFIG
# ============================================================
ACTIVE_REFERRALS_FOR_LEVEL = 3
ACTIVE_REFERRALS_REWARD = Decimal("15000")

REFERRALS_PER_CYCLE = 20
PER_REFERRAL_VALUE = Decimal("100")
CYCLE_REWARD = PER_REFERRAL_VALUE * REFERRALS_PER_CYCLE   # 5000


# ============================================================
# HELPERS
# ============================================================
def _get_referral_stats(user_id: int):
    """
    Returns (joined, active_count, inactive_count, active_invested).
    - joined:      total referrals ever
    - active_count: referrals with >=1 active non-expired package
    - inactive:    joined - active
    - active_invested: sum of package_amount for active packages
    """
    referred_ids = [
        r.referred_id for r in
        Referral.query.filter_by(referrer_id=user_id).all()
        if r.referred_id
    ]

    if not referred_ids:
        return 0, 0, 0, Decimal("0")

    now = datetime.now(timezone.utc)

    active_pkgs = (
        db.session.query(Package)
        .filter(
            Package.user_id.in_(referred_ids),
            Package.status == "active",
            Package.expires_at > now,
        )
        .all()
    )

    active_user_ids = {p.user_id for p in active_pkgs}
    active_invested = sum(
        (Decimal(str(p.package_amount or 0)) for p in active_pkgs),
        Decimal("0"),
    )

    joined = len(referred_ids)
    active_count = len(active_user_ids)
    inactive_count = max(0, joined - active_count)

    return joined, active_count, inactive_count, active_invested


def _already_paid(user_id: int, reward_type: str) -> bool:
    return RewardsLedger.query.filter_by(
        user_id=user_id, type=reward_type
    ).first() is not None


def _credit_locked_balance(user: User, amount: Decimal, ledger_type: str, notes: str):
    """Credit amount to wallet.locked_balance and write ledger + transaction rows."""
    if not user.wallet:
        user.wallet = Wallet(user_id=user.id, balance=0, locked_balance=0)
        db.session.add(user.wallet)
        db.session.flush()

    current_locked = Decimal(str(user.wallet.locked_balance or 0))
    user.wallet.locked_balance = float(current_locked + amount)

    db.session.add(RewardsLedger(
        user_id=user.id,
        type=ledger_type,
        amount=float(amount),
        notes=notes,
    ))

    db.session.add(Transaction(
        user_id=user.id,
        wallet_id=user.wallet.id,
        type=ledger_type,
        amount=amount,
        status="completed",
        reference=f"RWD-{ledger_type[:6].upper()}-{int(datetime.now().timestamp())}",
    ))


# ============================================================
# MAIN DASHBOARD
# ============================================================
@bp.route("/api/user/rewards", methods=["GET"])
def user_rewards():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    joined, active_count, inactive_count, active_invested = _get_referral_stats(user.id)

    # -------- Reward 1: 3 active referrals → 20,000 (claimable) --------
    level_reward_already_paid = _already_paid(user.id, "active_referral_reward")
    level_qualified = active_count >= ACTIVE_REFERRALS_FOR_LEVEL

    level_reward = {
        "requirement": ACTIVE_REFERRALS_FOR_LEVEL,
        "current": active_count,
        "reward": float(ACTIVE_REFERRALS_REWARD),
        "qualified": level_qualified,
        "paid": level_reward_already_paid,
        "can_claim": level_qualified and not level_reward_already_paid,
    }

    # -------- Reward 2: every 50 referrals → 5,000 (auto-paid, resets) --------
    paid_cycles = RewardsLedger.query.filter_by(
        user_id=user.id, type="referral_cycle_payout"
    ).count()

    total_paid_referrals = paid_cycles * REFERRALS_PER_CYCLE
    referrals_since_last_payout = max(0, joined - total_paid_referrals)
    cycle_progress = referrals_since_last_payout % REFERRALS_PER_CYCLE
    cycle_ready = referrals_since_last_payout >= REFERRALS_PER_CYCLE

    cycle_reward = {
        "per_referral_value": float(PER_REFERRAL_VALUE),
        "cycle_size": REFERRALS_PER_CYCLE,
        "cycle_reward": float(CYCLE_REWARD),
        "progress": cycle_progress,
        "remaining": max(0, REFERRALS_PER_CYCLE - cycle_progress),
        "percent": round((cycle_progress / REFERRALS_PER_CYCLE) * 100, 1),
        "ready": cycle_ready,
        "paid_cycles": paid_cycles,
    }

    # Auto-payout when a cycle completes
    if cycle_ready:
        cycles_to_pay = referrals_since_last_payout // REFERRALS_PER_CYCLE
        amount = CYCLE_REWARD * cycles_to_pay
        _credit_locked_balance(
            user,
            amount,
            ledger_type="referral_cycle_payout",
            notes=f"Auto-paid {cycles_to_pay} cycle(s) × {REFERRALS_PER_CYCLE} referrals",
        )
        db.session.commit()

        cycle_reward["paid_cycles"] += cycles_to_pay
        cycle_reward["progress"] = 0
        cycle_reward["remaining"] = REFERRALS_PER_CYCLE
        cycle_reward["percent"] = 0.0
        cycle_reward["ready"] = False

    return jsonify({
        "stats": {
            "referrals_joined": joined,
            "referrals_active": active_count,
            "referrals_inactive": inactive_count,
            "active_invested": float(active_invested),
        },
        "level_reward": level_reward,
        "cycle_reward": cycle_reward,
    }), 200


# ============================================================
# CLAIM — only the 3-active-referral 20,000 reward is claimable
# ============================================================
@bp.route("/api/user/rewards/claim", methods=["POST"])
def claim_rewards():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    _, active_count, _, _ = _get_referral_stats(user.id)

    if active_count < ACTIVE_REFERRALS_FOR_LEVEL:
        return jsonify({
            "error": f"You need {ACTIVE_REFERRALS_FOR_LEVEL} active referrals to claim",
            "current": active_count,
            "required": ACTIVE_REFERRALS_FOR_LEVEL,
        }), 400

    if _already_paid(user.id, "active_referral_reward"):
        return jsonify({"error": "Reward already claimed"}), 409

    _credit_locked_balance(
        user,
        ACTIVE_REFERRALS_REWARD,
        ledger_type="active_referral_reward",
        notes=f"{active_count} active referrals",
    )
    db.session.commit()

    return jsonify({
        "success": True,
        "claimed": float(ACTIVE_REFERRALS_REWARD),
        "credited_to": "locked_balance",
        "message": f"UGX {ACTIVE_REFERRALS_REWARD:,.0f} credited to locked balance",
    }), 200