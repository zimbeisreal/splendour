# routes/notifications.py

from flask import jsonify, Blueprint, session
from models import Notification, User
from extensions import db
from datetime import datetime
from decimal import Decimal
from flask import current_app


notification_bp = Blueprint("notifications", __name__)


def get_current_user():
    """Helper: get authenticated user safely"""
    user_id = session.get("user_id")
    if not user_id:
        return None

    return User.query.get(user_id)


@notification_bp.route('/api/notifications', methods=['GET'])
def get_notifications():
    """Get latest notifications for logged-in user"""

    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401

        notifications = (
            Notification.query
            .filter_by(user_id=user.id)
            .order_by(Notification.created_at.desc())
            .limit(10)
            .all()
        )

        return jsonify([n.to_dict() for n in notifications]), 200

    except Exception:
        return jsonify({"error": "Failed to fetch notifications"}), 500


@notification_bp.route('/api/notifications/<int:notif_id>/read', methods=['PUT'])
def mark_notification_read(notif_id):
    """Mark notification as read"""
 

    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401

        notification = Notification.query.get(notif_id)
        if not notification:
            return jsonify({"error": "Notification not found"}), 404

        # 🔐 Security check (VERY IMPORTANT)
        if notification.user_id != user.id:
            return jsonify({"error": "Forbidden"}), 403

        notification.is_read = True
        db.session.commit()

        return jsonify({"success": True}), 200

    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to update notification"}), 500
    
def send_package_activation_notifications(user, package_obj):
    """
    Send package activation and first bonus notifications.
    Call this after successfully creating a user package.
    
    Args:
        user: User object
        package_obj: PackageCatalog object
    """
    try:
        daily_bonus_amount = Decimal(str(package_obj.amount)) * Decimal("0.05")
        
        # Notification 1: Package Activation
        activation_notification = Notification(
            user_id=user.id,
      message=(
    f"splendour · Position opened\n"
    f"Package:  {package_obj.name}\n"
    f"Amount:   UGX {package_obj.amount:,.0f}\n"
    f"Yield:    UGX {daily_bonus_amount:,.0f}/day\n"
    f"Status:   Active · first credit in 24h"
),
            notification_type='package_activation',
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.session.add(activation_notification)
        
        # Notification 2: First Bonus Credited (if bonus was credited immediately)
        first_bonus_notification = Notification(
            user_id=user.id,
         message=(
    f"splendour :     Daily yield credited\n"
    f"Amount:   UGX {daily_bonus_amount:,.0f}\n"
    f"Source:   {package_obj.name}\n"
    f"Status:   Maturing · releases in 24h"
),
            notification_type='daily_bonus',
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.session.add(first_bonus_notification)
        
        current_app.logger.info(f"Package activation notifications sent for user {user.id}, package {package_obj.name}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Failed to send package activation notifications: {e}")
        return False



"""
splendour_notifications.py - Splendour wording for general notifications.

Replaces the old splendour helper `send_package_activation_notifications`, which
hard-coded a 5% daily yield, said "splendour", and claimed a daily bonus was
credited at purchase. At Splendour the first profit arrives after 24 hours and
lock plans earn no daily profit.

All helpers only db.session.add(); the CALLER commits, so a notification is
saved or lost together with the money movement it describes.
Message column is String(500): every message here stays well under that.
Messages are plain text: first line = title, other lines = details.
"""
from datetime import timedelta

from extensions import db
from models import Notification


def _ugx(n):
    return f"UGX {float(n):,.0f}"


def add_notification(user_id, message, ntype="general"):
    n = Notification(user_id=user_id, message=message[:500], notification_type=ntype, is_read=False)
    db.session.add(n)
    return n


def notify_package_activated(user, catalog, lock_end_date=None):
    """catalog = the PackageCatalog row that was bought."""
    f = catalog.features or {}
    name = catalog.display_name or catalog.name
    if catalog.is_locking_package:
        days = catalog.duration_days
        lines = [f"Lock plan started: {name}",
                 f"Locked: {_ugx(catalog.amount)} for {days} days",
                 f"You receive: {_ugx(f.get('total_returns', 0))}"]
        if lock_end_date:
            lines.append(f"Available on: {lock_end_date.strftime('%d %b %Y')}")
        lines.append("Your money is safe and cannot be withdrawn until then.")
        return add_notification(user.id, "\n".join(lines), "package_activation")
    lines = [f"Plan started: {name}",
             f"Invested: {_ugx(catalog.amount)}",
             f"Earns: {_ugx(f.get('daily_profit', 0))} a day for {catalog.duration_days} days",
             "First profit: after 24 hours",
             f"Your {_ugx(catalog.amount)} returns on day {catalog.duration_days}."]
    return add_notification(user.id, "\n".join(lines), "package_activation")


def notify_salary(user_id, kind, amount, active_referrals=None):
    if kind == "monthly":
        msg = (f"Monthly salary paid: {_ugx(amount)}\n"
               "Your friends' investments reached the salary target.\n"
               "It was added to your balance. Next salary in 30 days.")
    else:
        msg = (f"Team bonus paid: {_ugx(amount)}\n"
               "3 more of your friends have invested.\n"
               "It was added to your balance. The next group starts from 0.")
    return add_notification(user_id, msg, "salary")
