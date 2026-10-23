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
    f"SKYLINE · Position opened\n"
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
    f"SKYLINE :     Daily yield credited\n"
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