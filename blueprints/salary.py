"""
blueprints/salary.py  -  Splendour salary: ONE self-contained, deployable file.

Contains everything (no separate rules module to import):
  1. Rules            monthly salary + team bonus, pure functions (compute_state)
  2. Ledger model     SalaryPayout  (UNIQUE per user/kind/period => never paid twice)
  3. Crediting        process_user_salary / process_all_salaries (idempotent)
  4. Notifications    one message per payout, saved in the same transaction
  5. Routes           GET /api/salary, GET /api/salary/history, POST /api/salary/run
  6. Wiring           salary_bp, init_app(app), CLI: flask salary-init-db / salary-run

RULES (direct referrals only, so the same money is never counted twice)
  * Active referral  = a direct referral (User.referred_by) who has EVER bought a product.
                       Counts forever, so progress never goes down.
  * Monthly salary   UGX 10,000 every 30 days once direct active referrals' cumulative
                       investments reach UGX 250,000.
  * Team bonus       UGX 5,000 per complete group of 3 active referrals (6 -> 10,000).
                       Each group is paid once, then the count starts again from 0.

DEPLOY
  1. Put this file at blueprints/salary.py
  2. app.py:   from blueprints.salary import init_app as init_salary;  init_salary(app)
               (or: from blueprints.salary import salary_bp;  app.register_blueprint(salary_bp))
  3. Create the table:  flask salary-init-db      (or run the SQL below / Alembic autogenerate)
  4. Schedule daily:    flask salary-run          (or POST /api/salary/run + X-Salary-Token header)
  Config (optional): SALARY_LAZY_CREDIT=True (credit when the user opens the page),
                     SALARY_CRON_TOKEN="..." (enables POST /api/salary/run)

SQL (PostgreSQL)
  CREATE TABLE salary_payouts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind VARCHAR(20) NOT NULL,
    period_key VARCHAR(40) NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
    snapshot JSON,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_salary_payout_period UNIQUE (user_id, kind, period_key)
  );
  CREATE INDEX ix_salary_payouts_user_id ON salary_payouts(user_id);
"""
import hmac
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from typing import Iterable, List, Optional

from flask import Blueprint, current_app, g, jsonify, request, session
from sqlalchemy import UniqueConstraint, and_, case, func
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Notification, Package, Transaction, User, Wallet, SalaryPayout

logger = logging.getLogger(__name__)
salary_bp = Blueprint("salary_api", __name__, url_prefix="/api/salary")


# =====================================================================
# 1. RULES  (pure logic: no Flask / DB use below this banner until section 2)
# =====================================================================
MONTHLY_AMOUNT = Decimal("50000")
MONTHLY_THRESHOLD = Decimal("250000")
MONTHLY_INTERVAL_DAYS = 26
MONTHLY_FIRST_PAY_DELAY_DAYS = 0      # 0 = first salary the moment they qualify
GROUP_SIZE = 3
GROUP_AMOUNT = Decimal("5000")

KIND_MONTHLY = "monthly"
KIND_GROUP = "group"

# Package.status values that count as an investment (cancelled/failed/refunded never count).
COUNTED_PACKAGE_STATUSES = ("active", "completed", "expired", "matured")


def rules_config() -> dict:
    """Rules as sent to the frontend so screens never hard-code them."""
    return {
        "monthly_amount": float(MONTHLY_AMOUNT),
        "monthly_threshold": float(MONTHLY_THRESHOLD),
        "monthly_interval_days": MONTHLY_INTERVAL_DAYS,
        "group_size": GROUP_SIZE,
        "group_amount": float(GROUP_AMOUNT),
    }


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def month_key(k: int) -> str:
    return f"month-{k}"


def group_key(i: int) -> str:
    return f"group-{i}"


@dataclass
class Due:
    kind: str
    period_key: str
    amount: Decimal


@dataclass
class SalaryState:
    active_referrals: int
    direct_investment: Decimal
    qualified: bool
    first_earned_at: Optional[datetime]
    set_first_earned_at: bool          # caller must persist first_earned_at
    next_monthly_at: Optional[datetime]
    monthly_progress_pct: float
    monthly_remaining: Decimal
    groups_completed: int
    group_in_progress: int             # 0..GROUP_SIZE-1
    group_needed_for_next: int         # 1..GROUP_SIZE
    due: List[Due] = field(default_factory=list)

    @property
    def due_total(self) -> Decimal:
        return sum((d.amount for d in self.due), Decimal("0"))


def compute_state(active_referrals, direct_investment, first_earned_at, paid_keys: Iterable[tuple],
                  now: Optional[datetime] = None) -> SalaryState:
    """
    paid_keys: iterable of (kind, period_key) already paid (the ledger).
    Returns progress numbers plus the payouts that are still DUE.
    """
    now = _utc(now) or datetime.now(timezone.utc)
    invested = Decimal(str(direct_investment or 0))
    active = max(0, int(active_referrals or 0))
    paid = set(paid_keys)
    first = _utc(first_earned_at)

    # team bonus (groups of 3)
    completed = active // GROUP_SIZE
    in_progress = active % GROUP_SIZE
    needed = GROUP_SIZE - in_progress
    due: List[Due] = []
    for i in range(1, completed + 1):
        if (KIND_GROUP, group_key(i)) not in paid:
            due.append(Due(KIND_GROUP, group_key(i), GROUP_AMOUNT))

    # monthly salary
    qualified = invested >= MONTHLY_THRESHOLD
    set_first = False
    next_at = None
    if qualified:
        if first is None:
            first = now
            set_first = True
        start = first + timedelta(days=MONTHLY_FIRST_PAY_DELAY_DAYS)
        interval = timedelta(days=MONTHLY_INTERVAL_DAYS)
        due_months = 0 if now < start else int((now - start) // interval) + 1
        for k in range(due_months):
            if (KIND_MONTHLY, month_key(k)) not in paid:
                due.append(Due(KIND_MONTHLY, month_key(k), MONTHLY_AMOUNT))
        next_at = start + interval * due_months

    pct = float(min(Decimal("100"), invested / MONTHLY_THRESHOLD * 100))
    return SalaryState(
        active_referrals=active, direct_investment=invested, qualified=qualified,
        first_earned_at=first, set_first_earned_at=set_first, next_monthly_at=next_at,
        monthly_progress_pct=round(pct, 2), monthly_remaining=max(Decimal("0"), MONTHLY_THRESHOLD - invested),
        groups_completed=completed, group_in_progress=in_progress, group_needed_for_next=needed, due=due,
    )


# =====================================================================
# 2. LEDGER MODEL
# =====================================================================

# =====================================================================
# 3. AUTH + QUERIES
# =====================================================================
def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        uid = session.get("user_id")
        if not uid:
            return jsonify({"error": "Authentication required"}), 401
        g.user_id = uid
        return f(*a, **kw)
    return wrapper


def direct_referral_rows(user_id):
    """One row per DIRECT referral (User.referred_by): id, username, joined, invested, product count."""
    counted = and_(Package.user_id == User.id, Package.status.in_(COUNTED_PACKAGE_STATUSES))
    invested = func.coalesce(func.sum(Package.package_amount), 0)
    return (
        db.session.query(User.id, User.username, User.member_since,
                         invested.label("invested"), func.count(Package.id).label("pkg_count"))
        .outerjoin(Package, counted)
        .filter(User.referred_by == user_id, User.id != user_id)
        .group_by(User.id, User.username, User.member_since)
        .order_by(invested.desc(), User.member_since.desc())
        .all()
    )


def _aggregate(rows):
    active = sum(1 for r in rows if (r.pkg_count or 0) > 0)
    invested = sum((Decimal(str(r.invested or 0)) for r in rows), Decimal("0"))
    return active, invested


def _paid_keys(user_id):
    return {(k, p) for k, p in db.session.query(SalaryPayout.kind, SalaryPayout.period_key).filter_by(user_id=user_id)}


# =====================================================================
# 4. NOTIFICATIONS (added to the session; the caller commits)
# =====================================================================
def _ugx(n):
    return f"UGX {float(n):,.0f}"


def notify_salary(user_id, kind, amount):
    if kind == KIND_MONTHLY:
        msg = (f"Monthly salary paid: {_ugx(amount)}\n"
               "Your friends' investments reached the salary target.\n"
               "It was added to your balance. Next salary in 30 days.")
    else:
        msg = (f"Team bonus paid: {_ugx(amount)}\n"
               f"{GROUP_SIZE} more of your friends have invested.\n"
               "It was added to your balance. The next group starts from 0.")
    n = Notification(user_id=user_id, message=msg[:500], notification_type="salary", is_read=False)
    db.session.add(n)
    return n


# =====================================================================
# 5. CREDITING SERVICE (idempotent)
# =====================================================================
def process_user_salary(user_id, now=None):
    """
    Credit every salary payment currently due for this user.
    Safe to call repeatedly / concurrently: the user row is locked and the ledger's
    UNIQUE constraint is the final guard against double payment.
    Returns {"paid": [...], "total": float}.
    """
    now = now or datetime.now(timezone.utc)
    try:
        user = db.session.query(User).filter(User.id == user_id).with_for_update().first()
        if not user:
            return {"paid": [], "total": 0.0}

        rows = direct_referral_rows(user_id)
        active, invested = _aggregate(rows)
        state = compute_state(active, invested, user.salary_first_earned_at, _paid_keys(user_id), now)

        if state.set_first_earned_at:
            user.salary_first_earned_at = state.first_earned_at
        if not state.due:
            db.session.commit()     # persists first_earned_at if it was set
            return {"paid": [], "total": 0.0}

        wallet = user.wallet or Wallet(user_id=user.id, balance=0)
        if wallet.id is None:
            db.session.add(wallet)
            db.session.flush()

        paid = []
        for d in state.due:
            tx = Transaction(wallet_id=wallet.id, user_id=user.id, type="salary", amount=d.amount,
                             status="completed", reference=f"SAL-{user.id}-{d.kind}-{d.period_key}",
                             purchase_type=f"salary_{d.kind}", completed_at=now)
            db.session.add(tx)
            db.session.flush()
            db.session.add(SalaryPayout(
                user_id=user.id, kind=d.kind, period_key=d.period_key, amount=d.amount, transaction_id=tx.id,
                snapshot={"active_referrals": state.active_referrals,
                          "direct_investment": float(state.direct_investment)}))
            user.actual_balance = (user.actual_balance or Decimal("0")) + d.amount
            notify_salary(user.id, d.kind, d.amount)          # saved or lost together with the payout
            paid.append({"kind": d.kind, "period_key": d.period_key, "amount": float(d.amount)})

        user.salary_last_paid_at = now
        db.session.commit()
        logger.info("salary paid user=%s total=%s items=%s", user_id, state.due_total, len(paid))
        return {"paid": paid, "total": float(state.due_total)}

    except IntegrityError:
        db.session.rollback()       # another worker paid first; nothing to do
        logger.warning("salary double-pay prevented for user=%s", user_id)
        return {"paid": [], "total": 0.0}
    except Exception:
        db.session.rollback()
        raise


def process_all_salaries(now=None):
    """Run for every user who has at least one direct referral."""
    ids = [r[0] for r in db.session.query(User.referred_by).filter(User.referred_by.isnot(None)).distinct().all()]
    totals = {"users": 0, "payments": 0, "amount": 0.0, "errors": 0}
    for uid in ids:
        try:
            res = process_user_salary(uid, now)
            if res["paid"]:
                totals["users"] += 1
                totals["payments"] += len(res["paid"])
                totals["amount"] += res["total"]
        except Exception:
            totals["errors"] += 1
            logger.exception("salary run failed for user=%s", uid)
    return totals


# =====================================================================
# 6. SUMMARY + ROUTES
# =====================================================================
def _iso(dt):
    if not dt:
        return None
    return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).isoformat()


def build_summary(user_id, now=None):
    now = now or datetime.now(timezone.utc)
    user = db.session.get(User, user_id)
    rows = direct_referral_rows(user_id)
    active, invested = _aggregate(rows)
    paid = _paid_keys(user_id)
    state = compute_state(active, invested, user.salary_first_earned_at if user else None, paid, now)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    sums = db.session.query(
        func.coalesce(func.sum(SalaryPayout.amount), 0),
        func.coalesce(func.sum(case((SalaryPayout.kind == KIND_MONTHLY, SalaryPayout.amount), else_=0)), 0),
        func.coalesce(func.sum(case((SalaryPayout.kind == KIND_GROUP, SalaryPayout.amount), else_=0)), 0),
        func.coalesce(func.sum(case((SalaryPayout.created_at >= month_start, SalaryPayout.amount), else_=0)), 0),
    ).filter(SalaryPayout.user_id == user_id).one()

    months_paid = sum(1 for k, _ in paid if k == KIND_MONTHLY)
    groups_paid = sum(1 for k, _ in paid if k == KIND_GROUP)

    return {
        "success": True,
        "config": rules_config(),
        "monthly": {
            "qualified": state.qualified,
            "direct_active_investment": float(state.direct_investment),
            "threshold": float(MONTHLY_THRESHOLD),
            "remaining": float(state.monthly_remaining),
            "progress_pct": state.monthly_progress_pct,
            "amount": float(MONTHLY_AMOUNT),
            "months_paid": months_paid,
            "first_earned_at": _iso(state.first_earned_at if state.qualified else None),
            "last_paid_at": _iso(user.salary_last_paid_at) if user else None,
            "next_pay_at": _iso(state.next_monthly_at),
            "total_paid": float(sums[1]),
        },
        "team": {
            "active_referrals": state.active_referrals,
            "total_referrals": len(rows),
            "group_size": GROUP_SIZE,
            "groups_completed": state.groups_completed,
            "groups_paid": groups_paid,
            "in_progress": state.group_in_progress,
            "needed_for_next": state.group_needed_for_next,
            "next_reward": float(GROUP_AMOUNT),
            "total_paid": float(sums[2]),
        },
        "totals": {
            "total_paid": float(sums[0]),
            "paid_this_month": float(sums[3]),
            "due_now": float(state.due_total),     # >0 only if crediting has not run yet
        },
        # usernames, never phone numbers
        "referrals": [
            {"username": r.username, "is_active": (r.pkg_count or 0) > 0,
             "total_invested": float(r.invested or 0), "joined_at": _iso(r.member_since)}
            for r in rows[:200]
        ],
    }


@salary_bp.route("", methods=["GET"])
@login_required
def get_salary():
    try:
        if current_app.config.get("SALARY_LAZY_CREDIT", True):
            try:
                process_user_salary(g.user_id)
            except Exception:
                logger.exception("lazy salary credit failed user=%s", g.user_id)
        return jsonify(build_summary(g.user_id)), 200
    except Exception:
        logger.exception("salary summary failed user=%s", g.user_id)
        return jsonify({"error": "Failed to load salary data"}), 500


@salary_bp.route("/history", methods=["GET"])
@login_required
def get_history():
    page = max(1, request.args.get("page", 1, type=int))
    per = min(max(1, request.args.get("per_page", 20, type=int)), 50)
    q = (SalaryPayout.query.filter_by(user_id=g.user_id)
         .order_by(SalaryPayout.created_at.desc(), SalaryPayout.id.desc()))
    total = q.count()
    items = q.offset((page - 1) * per).limit(per).all()
    return jsonify({
        "success": True, "page": page, "per_page": per, "total": total,
        "payouts": [{"id": p.id, "kind": p.kind, "period_key": p.period_key, "amount": float(p.amount),
                     "created_at": _iso(p.created_at),
                     "reference": f"SAL-{p.user_id}-{p.kind}-{p.period_key}"} for p in items],
    }), 200


@salary_bp.route("/run", methods=["POST"])
def run_all():
    """External cron trigger. Header X-Salary-Token must equal config SALARY_CRON_TOKEN."""
    expected = current_app.config.get("SALARY_CRON_TOKEN") or ""
    given = request.headers.get("X-Salary-Token", "")
    if not expected or not hmac.compare_digest(expected, given):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({"success": True, "result": process_all_salaries()}), 200


# =====================================================================
# 7. WIRING
# =====================================================================
def init_app(app):
    """Register the blueprint and the CLI commands."""
    import click

    app.register_blueprint(salary_bp)

    @app.cli.command("salary-init-db")
    def salary_init_db():
        """Create the salary_payouts table if it does not exist."""
        SalaryPayout.__table__.create(bind=db.engine, checkfirst=True)
        click.echo("salary_payouts ready")

    @app.cli.command("salary-run")
    def salary_run():
        """Credit all due salaries (run daily from cron)."""
        click.echo(process_all_salaries())
