
from flask import Blueprint, jsonify, session, render_template, redirect, url_for,g, current_app
from models import User, db, Package, Wallet, ReferralBonus
from decimal import Decimal, ROUND_DOWN
from flask import session, jsonify, current_app, url_for, request
from models import Bonus, calculate_package_progress, Transaction, PackageCatalog
import os
import uuid
from werkzeug.utils import secure_filename
from flask_login import current_user, login_required
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func, and_, or_
import logging
from utils import ensure_utc, utc_iso
from sqlalchemy.orm import joinedload



bp = Blueprint('profile',__name__, url_prefix="")

# ----------------------------------------------------------------------------------
# 1️⃣ JAVASCRIPT GETS THIS DATA TO DYNAMICALLY UPDATE/ LOAD USER DATA
# ----------------------------------------------------------------------------------

@bp.route("/user/profile", methods=["GET"])
def get_user_profile():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # ============================================================
    # ✅ MODEL B: Mature any pending bonuses before reading balances
    # ============================================================
    # try:
    #     from bonus.daily import DailyBonusProcessor
    #     DailyBonusProcessor.mature_pending_bonuses(user.id)
    # except Exception as e:
    #     # Never let maturation failure block profile load
    #     logger.warning(f"Maturation failed for user {user.id}: {e}")
    
    # Refresh user object — maturations may have updated wallet.balance
    # db.session.refresh(user)
    
    data = user.to_dict()
    
    # Profile photo
    data["profile_photo"] = None
    if user.profile_photo:
        data["profile_photo"] = url_for(
            'static',
            filename=f'uploads/profiles/{user.profile_photo}'
        )
    
    # ============================================================
    # ✅ MODEL B: Build pending bonus payload
    # ============================================================

    
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    
    pending_txs = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.type.in_(['bonus_credit', 'bonus_credit_locked']),
        Transaction.status == 'pending',
        Transaction.matures_at != None,          # noqa: E711
    ).order_by(Transaction.matures_at.asc()).all()
    
    pending_total = sum(
        (Decimal(str(tx.amount)) for tx in pending_txs),
        Decimal("0"),
    )
    
    next_matures_at = pending_txs[0].matures_at if pending_txs else None
    
    data["pending_bonus"] = {
        "total": float(pending_total),
        "count": len(pending_txs),
        "next_matures_at": next_matures_at.isoformat() if next_matures_at else None,
        "items": [
            {
                "id": tx.id,
                "amount": float(tx.amount),
                "matures_at": tx.matures_at.isoformat() if tx.matures_at else None,
            }
            for tx in pending_txs[:20]   # cap payload size
        ],
    }
    
    # Get package details
    packages_data = []
    active_count = 0

    if user.packages:
    

        for package in user.packages:
            print(f"🔍 Checking package {package.id}")
            catalog = PackageCatalog.query.filter_by(name=package.package).first()
            print(f"   → catalog lookup result: {catalog}")

            try:
                if catalog and package.status in ['active', 'completed']:
                    features = catalog.features or {}
                    
                    if package.status == 'active':
                        active_count += 1
                    
                    # Progress
                    duration_days = catalog.duration_days or 26
                    days_active = 0
                    progress = 0
                    if package.activated_at:
                        activated = package.activated_at
                        if activated.tzinfo is None:
                            activated = activated.replace(tzinfo=timezone.utc)
                        now = datetime.now(timezone.utc)
                        days_active = max(0, (now - activated).days)
                        progress = min(round((days_active / duration_days) * 100), 100) if duration_days > 0 else 0
                    days_remaining = max(0, duration_days - days_active)
                    
                    # Lock details
                    is_locked = getattr(package, 'is_locked', False)
                    lock_duration = getattr(package, 'lock_duration_days', 0)
                    lock_end_date = getattr(package, 'lock_end_date', None)
                    daily_bonus_rate = float(package.daily_bonus_rate) if package.daily_bonus_rate else 0
                    
                    packages_data.append({
                        'id': package.id,
                        'name': catalog.name,
                        'display_name': catalog.display_name or catalog.name,
                        'amount': catalog.amount,
                        'status': package.status,
                        'daily_profit': features.get('daily_profit', 0),
                        'total_profit': features.get('total_profit', 0),
                        'total_returns': features.get('total_returns', 0),
                        'daily_bonus_rate': daily_bonus_rate * 100 if daily_bonus_rate else 0,
                        'duration_days': duration_days,
                        'days_active': days_active,
                        'days_remaining': days_remaining,
                        'progress': progress,
                        'is_locked': is_locked,
                        'lock_duration_days': lock_duration,
                        'lock_end_date': lock_end_date.isoformat() if lock_end_date else None,
                        'lock_earnings': float(package.lock_earnings or 0),                    # ← ADD
                        'lock_bonus_rate': float(package.lock_bonus_rate or 0),                # ← ADD
                        'lock_start_date': package.lock_start_date.isoformat() if getattr(package, 'lock_start_date', None) else None, 
                        'activated_at': package.activated_at.isoformat() if package.activated_at else None,
                        'expires_at': package.expires_at.isoformat() if package.expires_at else None,
                        'machine_details': getattr(package, 'machine_details', {}),
                        'machine_id': getattr(package, 'machine_id', None),
                    })
                    print(f"   ✅ APPENDED package {package.id} (now {len(packages_data)} items)")
                else:
                    print(f"   ⏭️ SKIPPED package {package.id}")
            except Exception as e:
                import traceback
                print(f"   ❌ EXCEPTION on package {package.id}: {e}")
                traceback.print_exc()

        print(f"🏁 Loop done. packages_data has {len(packages_data)} items")

    data['packages'] = packages_data
    data['active_packages_count'] = active_count

    return jsonify(data), 200
# @bp.route("/user/profile", methods=["GET"])
# def get_user_profile():
#     user_id = session.get("user_id")
#     if not user_id:
#         return jsonify({"error": "Unauthorized"}), 401

#     user = User.query.get(user_id)
#     if not user:
#         return jsonify({"error": "User not found"}), 404
    
#     data = user.to_dict()
    
#     # Profile photo
#     data["profile_photo"] = None
#     if user.profile_photo:
#         data["profile_photo"] = url_for(
#             'static',
#             filename=f'uploads/profiles/{user.profile_photo}'
#         )
    
#     # Get package details
#     packages_data = []
#     active_count = 0

#     if user.packages:
#         from models import PackageCatalog
#         from datetime import datetime, timezone
        
#         for package in user.packages:
#             # ✅ Check if catalog exists
#             catalog = PackageCatalog.query.filter_by(name=package.package).first()
            
#             if catalog and package.status in ['active', 'completed']:
#                 features = catalog.features or {}
                
#                 # ✅ Count active packages
#                 if package.status == 'active':
#                     active_count += 1
                
#                 # ✅ Calculate progress
#                 duration_days = catalog.duration_days or 26
#                 days_active = 0
#                 progress = 0
                
#                 if package.activated_at:
#                     activated = package.activated_at
#                     if activated.tzinfo is None:
#                         activated = activated.replace(tzinfo=timezone.utc)
#                     now = datetime.now(timezone.utc)
#                     days_active = max(0, (now - activated).days)
#                     progress = min(round((days_active / duration_days) * 100), 100) if duration_days > 0 else 0
                
#                 # ✅ Calculate days remaining
#                 days_remaining = max(0, duration_days - days_active)
                
#                 # ✅ Check if package is locked
#                 is_locked = getattr(package, 'is_locked', False)
#                 lock_duration = getattr(package, 'lock_duration_days', 0)
#                 lock_end_date = getattr(package, 'lock_end_date', None)
                
#                 # ✅ Get daily bonus rate
#                 daily_bonus_rate = float(package.daily_bonus_rate) if package.daily_bonus_rate else 0
                
#                 packages_data.append({
#                     # ✅ Core details
#                     'id': package.id,
#                     'name': catalog.name,
#                     'display_name': catalog.display_name or catalog.name,
#                     'amount': catalog.amount,
#                     'status': package.status,
                    
#                     # ✅ Financial details
#                     'daily_profit': features.get('daily_profit', 0),
#                     'total_profit': features.get('total_profit', 0),
#                     'total_returns': features.get('total_returns', 0),
#                     'daily_bonus_rate': daily_bonus_rate * 100 if daily_bonus_rate else 0,  # Show as percentage
                    
#                     # ✅ Duration details
#                     'duration_days': duration_days,
#                     'days_active': days_active,
#                     'days_remaining': days_remaining,
#                     'progress': progress,
                    
#                     # ✅ Lock details
#                     'is_locked': is_locked,
#                     'lock_duration_days': lock_duration,
#                     'lock_end_date': lock_end_date.isoformat() if lock_end_date else None,
                    
#                     # ✅ Dates
#                     'activated_at': package.activated_at.isoformat() if package.activated_at else None,
#                     'expires_at': package.expires_at.isoformat() if package.expires_at else None,
                    
#                     # ✅ Machine details (if any)
#                     'machine_details': getattr(package, 'machine_details', {}),
#                     'machine_id': getattr(package, 'machine_id', None),
#                 })

#     # ✅ Add active count to response
#     data['packages'] = packages_data
#     data['active_packages_count'] = active_count

#     return jsonify(data), 200


#==========================================================================
# THIS IS THE PROFILE PAGE FOR USERS

@bp.route("/profile")
def my_profile():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    user = User.query.get_or_404(session["user_id"])
    return render_template("partials/profile.html", user=user, is_admin_view=False)

#===================================================================================

@bp.route('/api/user/profile', methods=['PUT'])
def update_user_profile():
    """Update user profile and return fresh data"""
    user_id = session.get('user_id')
 
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

#=======================================================================================
#      USER VERIFICATION ENDPOINT
#=======================================================================================
    
@bp.route("/api/user/<int:user_id>/", methods=["GET"])
def get_user_network(user_id):
    """
    Get user's referral network for verification and debugging
    """
    try:
        from bonus.refferral_tree import ReferralTreeHelper
        
        network_summary = ReferralTreeHelper.get_user_network_summary(user_id)
        
        return jsonify({
            "success": True,
            "network": network_summary
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting network for user {user_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

logger = logging.getLogger(__name__)
#=========================================================================
#=======================================================================


@bp.route('/api/user/total-earnings', methods=['GET'])
def get_current_user_total_earnings():
    """
    Calculate total earnings and referral statistics for the currently logged-in user
    """
    print("🎯 EARNINGS ENDPOINT HIT - WITH REFERRAL STATS")
    
    # Use session authentication like your other routes
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "error": "Authentication required",
            "message": "Please log in to access this endpoint"
        }), 401
    
    try:
        from models import User, Wallet, ReferralBonus, Bonus, Transaction, Referral, db
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        print(f"✅ Processing earnings for user: {user.username}")
        
        now = datetime.now(timezone.utc)
        
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        totals = {
            'today': Decimal('0.0'),
            'this_week': Decimal('0.0'),
            'this_month': Decimal('0.0'),
            'breakdown': {
                'referral_bonus': Decimal('0.0'),
                'signup_bonus': Decimal('0.0'),
                'available_balance': Decimal('0.0'),
                'wallet_balance': Decimal('0.0'),
                'locked_wallet_balance': Decimal('0.0')
            }
        }

        # =========================================================================
        # 1. CALCULATE REFERRAL STATISTICS
        # =========================================================================
        
        # Total direct referrals (users who signed up using this user's referral code)
        total_direct_referrals = db.session.query(
            func.count(Referral.id)
        ).filter(
            Referral.referrer_id == user_id,
            Referral.status == 'active'
        ).scalar() or 0

        # Active referrals (referred users who are active)
        active_referrals = db.session.query(
            func.count(Referral.id)
        ).filter(
            Referral.referrer_id == user_id,
            Referral.status == 'active',
            Referral.referred_id.isnot(None)
        ).scalar() or 0

        # Total network size (from User model)
        total_network_size = user.total_network_size or 0

        # =========================================================================
        # 2. CALCULATE LIFETIME EARNINGS
        # =========================================================================
        
        # Lifetime referral bonuses (all time, not just active)
        lifetime_referral_bonus_raw = db.session.query(
            func.coalesce(func.sum(ReferralBonus.bonus_amount), 0.00)
        ).filter(
            ReferralBonus.user_id == user_id
            # Remove status filter to get ALL historical bonuses
        ).scalar() or 0.00

        # Lifetime signup bonuses (all time)
        lifetime_signup_bonus = db.session.query(
            func.coalesce(func.sum(Bonus.amount), Decimal('0.00'))
        ).filter(
            Bonus.user_id == user_id,
            Bonus.type == 'signup'
            # Remove status filter to get ALL historical bonuses
        ).scalar() or Decimal('0.00')

        # Convert to Decimal for calculation
        lifetime_referral_bonus = Decimal(str(lifetime_referral_bonus_raw))
        
        # Total lifetime earnings (all bonuses ever earned)
        lifetime_earnings = (lifetime_referral_bonus + lifetime_signup_bonus).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # =========================================================================
        # 3. CALCULATE CURRENT PERIOD EARNINGS (existing logic)
        # =========================================================================

        # Current period referral bonuses
        referral_today_raw = db.session.query(
            func.coalesce(func.sum(ReferralBonus.bonus_amount), 0.0)
        ).filter(
            ReferralBonus.user_id == user_id,
            ReferralBonus.status == 'active',
            ReferralBonus.created_at >= today_start
        ).scalar() or 0.0
        
        referral_week_raw = db.session.query(
            func.coalesce(func.sum(ReferralBonus.bonus_amount), 0.0)
        ).filter(
            ReferralBonus.user_id == user_id,
            ReferralBonus.status == 'active',
            ReferralBonus.created_at >= week_start
        ).scalar() or 0.0
        
        referral_month_raw = db.session.query(
            func.coalesce(func.sum(ReferralBonus.bonus_amount), 0.0)
        ).filter(
            ReferralBonus.user_id == user_id,
            ReferralBonus.status == 'active',
            ReferralBonus.created_at >= month_start
        ).scalar() or 0.0

        # Convert all referral amounts to Decimal
        referral_today = Decimal(str(referral_today_raw))
        referral_week = Decimal(str(referral_week_raw))
        referral_month = Decimal(str(referral_month_raw))

        # Current period signup bonuses
        signup_today = db.session.query(
            func.coalesce(func.sum(Bonus.amount), Decimal('0.00'))
        ).filter(
            Bonus.user_id == user_id,
            Bonus.type == 'signup',
            Bonus.status == 'active',
            Bonus.created_at >= today_start
        ).scalar() or Decimal('0.00')

        signup_week = db.session.query(
            func.coalesce(func.sum(Bonus.amount), Decimal('0.0'))
        ).filter(
            Bonus.user_id == user_id,
            Bonus.type == 'signup',
            Bonus.status == 'active',
            Bonus.created_at >= week_start
        ).scalar() or Decimal('0.0')

        signup_month = db.session.query(
            func.coalesce(func.sum(Bonus.amount), Decimal('0.0'))
        ).filter(
            Bonus.user_id == user_id,
            Bonus.type == 'signup',
            Bonus.status == 'active',
            Bonus.created_at >= month_start
        ).scalar() or Decimal('0.0')

        # 4. Get current balances (not time-bound)
        available_balance = user.available_balance if user.available_balance else Decimal('0.0')
        wallet_balance = user.wallet.balance if user.wallet else Decimal('0.0')
        locked_wallet_balance = user.wallet.locked_balance if user.wallet else Decimal('0.0')
        


        # Calculate period totals
        totals['today'] = (referral_today + signup_today).quantize(Decimal('0.01'), ROUND_HALF_UP)
        totals['this_week'] = (referral_week + signup_week).quantize(Decimal('0.01'), ROUND_HALF_UP)
        totals['this_month'] = (referral_month + signup_month).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # Set breakdown (current state)
        referral_total_raw = db.session.query(
            func.coalesce(func.sum(ReferralBonus.bonus_amount), 0.0)
        ).filter(
            ReferralBonus.user_id == user_id,
            ReferralBonus.status == 'active'
        ).scalar() or 0.0
        
        totals['breakdown']['referral_bonus'] = Decimal(str(referral_total_raw)).quantize(Decimal('0.01'), ROUND_HALF_UP)
        totals['breakdown']['signup_bonus'] = db.session.query(
            func.coalesce(func.sum(Bonus.amount), Decimal('0.0'))
        ).filter(
            Bonus.user_id == user_id,
            Bonus.type == 'signup',
            Bonus.status == 'active'
        ).scalar() or Decimal('0.00')
        totals['breakdown']['available_balance'] = available_balance.quantize(Decimal('0.01'), ROUND_HALF_UP)
        totals['breakdown']['wallet_balance'] = wallet_balance.quantize(Decimal('0.01'), ROUND_HALF_UP)
        totals['breakdown']['locked_wallet_balance'] = locked_wallet_balance.quantize(Decimal('0.01'), ROUND_HALF_UP)
        # =========================================================================
        # 5. PREPARE COMPREHENSIVE RESPONSE
        # =========================================================================

        response_data = {
            "user_id": user_id,
            "username": user.username,
            
            # Current period earnings
            "today": str(totals['today']),
            "this_week": str(totals['this_week']),
            "this_month": str(totals['this_month']),
            
            # Current balances breakdown
            "breakdown": {
                "referral_bonus": str(totals['breakdown']['referral_bonus']),
                "signup_bonus": str(totals['breakdown']['signup_bonus']),
                "available_balance": str(totals['breakdown']['available_balance']),
                "wallet_balance": str(totals['breakdown']['wallet_balance']),
                "locked_wallet_balance": str(totals['breakdown']['locked_wallet_balance'])
            },
            
            # NEW: Referral statistics
            "referral_stats": {
                "total_direct_referrals": total_direct_referrals,
                "active_referrals": active_referrals,
                "total_network_size": total_network_size,
                "network_depth": user.network_depth or 0,
                "direct_referrals_count": user.direct_referrals_count or 0
            },
            
            # NEW: Lifetime earnings
            "lifetime_earnings": {
                "total": str(lifetime_earnings),
                "breakdown": {
                    "referral_bonus": str(lifetime_referral_bonus),
                    "signup_bonus": str(lifetime_signup_bonus)
                }
            }
        }

        print(f"✅ Comprehensive stats calculated for user {user_id}")
        print(f"   - Direct referrals: {total_direct_referrals}")
        print(f"   - Network size: {total_network_size}")
        print(f"   - Lifetime earnings: {lifetime_earnings}")
        
        logger.info(f"Comprehensive stats calculated for user {user_id}")

        return jsonify(response_data)

    except Exception as e:
        print(f"💥 Error calculating comprehensive stats for user {user_id}: {str(e)}")
        logger.error(f"Error calculating comprehensive stats for user {user_id}: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "Unable to calculate statistics at this time"
        }), 500
    
@bp.route('/api/user/today-bonus')
def get_today_bonus():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    from bonus.daily import DailyBonusProcessor
    print(DailyBonusProcessor)
    processor = DailyBonusProcessor(user_id)
    bonus_summary = processor.run()  # Returns the dict with keys: total_bonus, packages_successful, packages_failed

    return jsonify({
        "success": True,
        "wallet_balance": bonus_summary["wallet_balance"],
        "locked_wallet_balance": bonus_summary["locked_balance"],
        "total_bonus_today": bonus_summary["total_bonus"],
        "processed_packages": bonus_summary["processed_packages"],
        "packages_completed": bonus_summary["packages_successful"],
        "packages_expired": bonus_summary["packages_failed"]
    })
        # Allowed image extensions
ALLOWED_EXTENSIONS = {
    'png',
    'jpg',
    'jpeg',
    'webp'
}

def allowed_file(filename):
    print(f"Checking allowed file: {filename}")
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    result = '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    print(f"Result: {result}")
    return result
# =========================
# PROFILE PHOTO UPLOAD
# =========================


from flask import session, request, jsonify, url_for, current_app
from flask_login import login_required, current_user
import os
import uuid
import traceback
from werkzeug.utils import secure_filename
from models import User

@bp.route('/upload-profile-photo', methods=['POST'])
def upload_profile_photo():
    print(f"=== UPLOAD ATTEMPT (Hybrid) ===")
    
    # Try to get user from Flask-Login first
    user = None
    
    if current_user.is_authenticated:
        user = current_user
        print("User found via Flask-Login")
    else:
        # Fallback to session
        user_id = session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
            print(f"User found via session: {user_id}")
        else:
            print("No user found in session or Flask-Login")
            return jsonify({
                'success': False, 
                'message': 'Not authenticated'
            }), 401
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 401
    
    print(f"User: {user.id} - {user.email}")
    
    try:
        if 'photo' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400

        file = request.files['photo']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No image selected'}), 400

        # Validate extension
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS):
            return jsonify({'success': False, 'message': 'Invalid image format'}), 400

        # Generate unique filename
        original_filename = secure_filename(file.filename)
        extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{extension}"

        # Get upload folder
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads/profiles')
        upload_folder_abs = os.path.join(current_app.root_path, upload_folder)
        os.makedirs(upload_folder_abs, exist_ok=True)

        # Save file
        save_path = os.path.join(upload_folder_abs, unique_filename)
        file.save(save_path)

        # Delete old photo
        if user.profile_photo:
            old_path = os.path.join(upload_folder_abs, user.profile_photo)
            if os.path.exists(old_path):
                os.remove(old_path)

        # Update database
        user.profile_photo = unique_filename
        from app import db
        db.session.commit()

        # Generate URL
        photo_url = url_for('static', filename=f'uploads/profiles/{unique_filename}', _external=True)

        return jsonify({
            'success': True,
            'message': 'Profile photo updated',
            'photo_url': photo_url
        })

    except Exception as e:
        print(f"ERROR: {str(e)}")
        print(traceback.format_exc())
        from app import db
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': str(e)
        }), 500

# ============================================================
# IMPORTS
# ============================================================




# ============================================================
# HELPER FUNCTIONS
# ============================================================

def ensure_utc(dt):
    """Ensure datetime is timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def utc_iso(dt):
    """Convert datetime to ISO format string in UTC."""
    if dt is None:
        return None
    return ensure_utc(dt).isoformat().replace('+00:00', 'Z')

def safe_get_feature(catalog, key, default=None):
    """Safely get feature from catalog."""
    if not catalog or not hasattr(catalog, 'features'):
        return default
    if not catalog.features:
        return default
    return catalog.features.get(key, default)

# ============================================================
# ROUTE: GET ACTIVE PACKAGES
# ============================================================
@bp.route('/user/active-packages', methods=['GET'])
def get_active_packages():
    """
    Get user's active packages with full details for rendering.
    
    Query Parameters:
        - page (int): Page number (default: 1)
        - per_page (int): Items per page (default: 20, max: 50)
        - sort_by (str): Sort by field (created_at, package_amount, activated_at)
        - sort_order (str): asc or desc (default: desc)
        - is_locked (bool): Filter by locked status
        - type (str): Filter by package type
    
    Returns:
        JSON response with packages and totals
    """
    try:
        # ✅ Get user from session
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not logged in"}), 401
            
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        # ============================================================
        # 1. GET QUERY PARAMETERS
        # ============================================================
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 50)
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        is_locked_filter = request.args.get('is_locked', None)
        package_type = request.args.get('type', None)
        
        # Validate sort column
        valid_sort_columns = ['created_at', 'package_amount', 'activated_at', 'expires_at', 'status']
        if sort_by not in valid_sort_columns:
            sort_by = 'created_at'
        
        # ============================================================
        # 2. BUILD QUERY WITH EAGER LOADING
        # ============================================================
        query = Package.query.options(
            joinedload(Package.catalog)
        ).filter(
            Package.user_id == user.id,
            Package.status == 'active'
        )
        
        # Apply filters
        if is_locked_filter is not None:
            is_locked = is_locked_filter.lower() == 'true'
            query = query.filter(Package.is_locked == is_locked)
        
        if package_type:
            query = query.filter(Package.type == package_type)
        
        # Apply sorting
        sort_column = getattr(Package, sort_by)
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
        
        # ============================================================
        # 3. EXECUTE QUERY WITH PAGINATION
        # ============================================================
        paginated_packages = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        # ============================================================
        # 4. FORMAT PACKAGE DATA WITH LOCK RATES
        # ============================================================
        package_data = []
        totals = {
            'total_investment': 0,
            'total_daily_profit': 0,
            'total_packages': 0,
            'locked_count': 0,
            'active_count': 0,
            'locked_daily_profit': 0,
            'unlocked_daily_profit': 0
        }
        
        for pkg in paginated_packages.items:
            catalog = pkg.catalog
            
            # Calculate progress
            progress_data = calculate_package_progress(pkg)
            
            # ============================================================
            # ✅ CALCULATE RATES WITH LOCK BONUS
            # ============================================================
            
            # Get base rates from catalog
            base_daily_rate = float(catalog.daily_return_rate or 0) if catalog else 0
            base_daily_profit = safe_get_feature(catalog, 'daily_profit', 0)
            
            # Get lock information
            is_locked = pkg.is_locked or False
            lock_bonus_rate = float(pkg.lock_bonus_rate or 0)
            lock_duration_days = pkg.lock_duration_days or 0
            
            # ✅ Calculate effective rates
            if is_locked:
                # Locked machine: Base rate + Lock bonus
                effective_daily_rate = base_daily_rate + lock_bonus_rate
                # Calculate profit based on package amount
                effective_daily_profit = float(pkg.package_amount or 0) * (effective_daily_rate / 100)
                # Total profit = daily profit * duration
                effective_total_profit = effective_daily_profit * (catalog.duration_days if catalog else 26)
                effective_total_return = float(pkg.package_amount or 0) + effective_total_profit
                
                # Display text for locked bonus
                rate_display_text = f"{base_daily_rate}% + {lock_bonus_rate}% bonus = {effective_daily_rate}%"
                bonus_display_text = f"+{lock_bonus_rate}% locked bonus"
            else:
                # Unlocked machine: Base rate only
                effective_daily_rate = base_daily_rate
                effective_daily_profit = base_daily_profit
                effective_total_profit = safe_get_feature(catalog, 'total_profit', 0)
                effective_total_return = safe_get_feature(catalog, 'total_returns', 0)
                rate_display_text = f"{base_daily_rate}%"
                bonus_display_text = None
            
            # ✅ Build package object with both base and effective rates
            package = {
                "id": pkg.id,
                "name": pkg.package,
                "display_name": catalog.display_name if catalog else pkg.package,
                "amount": float(pkg.package_amount or 0),
                "emoji": safe_get_feature(catalog, 'machine_emoji', '⚙️'),
                
                # ✅ Base rates (from catalog)
                "base_daily_rate": base_daily_rate,
                "base_daily_profit": base_daily_profit,
                "base_total_profit": safe_get_feature(catalog, 'total_profit', 0),
                "base_total_return": safe_get_feature(catalog, 'total_returns', 0),
                
                # ✅ Lock information
                "is_locked": is_locked,
                "can_lock": catalog.machine_eligible if catalog else False,
                "lock_bonus_rate": lock_bonus_rate,
                "lock_duration_days": lock_duration_days,
                "lock_earnings": float(pkg.lock_earnings or 0),
                "lock_bonus_tiers": catalog.lock_bonus_tiers if catalog else {},
                
                # ✅ EFFECTIVE RATES (what user actually earns)
                "daily_rate": effective_daily_rate,
                "daily_profit": effective_daily_profit,
                "total_profit": effective_total_profit,
                "total_return": effective_total_return,
                
                # ✅ Display information
                "rate_display_text": rate_display_text,
                "bonus_display_text": bonus_display_text,
                "is_locked_display": "🔒 Locked" if is_locked else "🟢 Active",
                "lock_badge": f"🔒 +{lock_bonus_rate}%" if is_locked else "",
                
                # ✅ Progress information
                "total_rate": float(catalog.total_return_rate or 0) if catalog else 156.0,
                "duration_days": catalog.duration_days if catalog else 26,
                "days_active": progress_data['days_active'],
                "days_remaining": progress_data['days_remaining'],
                "progress_percentage": round(progress_data['progress'], 2),
                
                # ✅ Other fields
                "support_level": safe_get_feature(catalog, 'support_level', 'Basic'),
                "referral_bonus": safe_get_feature(catalog, 'referral_bonus', 0),
                "status": pkg.status or 'active',
                "activated_at": utc_iso(pkg.activated_at),
                "expires_at": utc_iso(pkg.expires_at),
                "type": pkg.type,
                "is_expired": pkg.is_expired if hasattr(pkg, 'is_expired') else False
            }
            
            package_data.append(package)
            
            # ✅ Update totals with effective rates
            totals['total_investment'] += package['amount']
            totals['total_daily_profit'] += package['daily_profit']
            
            if package['is_locked']:
                totals['locked_count'] += 1
                totals['locked_daily_profit'] += package['daily_profit']
            else:
                totals['unlocked_daily_profit'] += package['daily_profit']
                
            if package['status'] == 'active':
                totals['active_count'] += 1
        
        totals['total_packages'] = len(package_data)
        
        # ============================================================
        # 5. RETURN RESPONSE
        # ============================================================
        response = {
            "success": True,
            "packages": package_data,
            "totals": totals,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": paginated_packages.total,
                "pages": paginated_packages.pages,
                "has_prev": paginated_packages.has_prev,
                "has_next": paginated_packages.has_next
            },
            "filters": {
                "sort_by": sort_by,
                "sort_order": sort_order,
                "is_locked": is_locked_filter,
                "type": package_type
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching active packages for user {user_id if 'user_id' in locals() else 'unknown'}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to fetch active packages. Please try again.",
            "error": str(e) if current_app.debug else None
        }), 500



