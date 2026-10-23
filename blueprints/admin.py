# admin.py - Complete Production-Ready Admin Backend
"""
Admin Blueprint for Finicashi Platform
Routes match frontend expectations: /admin/api/*
All endpoints are secure, optimized, and maintain existing logic
"""

from flask import render_template, jsonify, request, Blueprint, session, redirect, url_for, abort, flash
from functools import wraps
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
import csv
from io import StringIO
from flask import Response
import logging
#from sub_admin.decorators import subadmin_required
from extensions import db
from models import (
    User, Withdrawal, Transaction, Package, PackageCatalog, 
    Referral, ReferralBonus, Bonus, AdminAction, SystemSetting,
    Payment, PaymentStatus, Wallet
)
from sqlalchemy import func, and_, or_, desc, case

logger = logging.getLogger(__name__)

# ===========================================================
# BLUEPRINT INITIALIZATION
# ===========================================================

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ===========================================================
# AUTH DECORATOR
# ===========================================================

def admin_required(f):
    """
    Decorator to restrict access to admin-only routes.
    Checks session user_id and role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_id = session["user_id"]
        user = User.query.get(user_id)
        
        if not user or user.role != "admin":
            return jsonify({'error': 'Admin access required'}), 403
        
        # Attach admin user to request for logging
        request.admin_user = user
        return f(*args, **kwargs)
    
    return decorated_function


# ===========================================================
# PAGE ROUTES (HTML Views)
# ===========================================================

@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard_page():
    """Admin dashboard HTML page"""
    return render_template("partials/admin.html")

@admin_bp.route('/subadmin/dashboard')
#@subadmin_required
def subadmin_dashboard_page():
    """Sub Admin dashboard HTML page"""
    return render_template("partials/sub_admin.html")

@admin_bp.route('/users')
@admin_required
def users_page():
    """Users management HTML page"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'all')
    
    query = User.query.options(
        db.joinedload(User.profile),
        db.joinedload(User.wallet)
    )
    
    if search:
        query = query.filter(
            or_(
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.phone.ilike(f'%{search}%')
            )
        )
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/users.html', users=users, search=search, status=status)


@admin_bp.route('/withdrawals')
@admin_required
def withdrawals_page():
    """Withdrawals management HTML page"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'pending')
    
    query = Withdrawal.query.options(db.joinedload(Withdrawal.user))
    
    if status_filter != 'all':
        query = query.filter(Withdrawal.status == status_filter)
    
    withdrawals = query.order_by(
        case((Withdrawal.status == 'pending', 1), else_=2),
        Withdrawal.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/withdrawals.html', withdrawals=withdrawals, status_filter=status_filter)


@admin_bp.route('/packages')
@admin_required
def packages_page():
    """Packages management HTML page"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'active')
    
    query = Package.query.options(
        db.joinedload(Package.user),
        db.joinedload(Package.catalog)
    )
    
    if status != 'all':
        query = query.filter(Package.status == status)
    
    packages = query.order_by(Package.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    
    summary = db.session.query(
        func.count(Package.id).label('total'),
        func.coalesce(func.sum(Package.package_amount), 0).label('total_value'),
        func.count(Package.id).filter(Package.status == 'active').label('active_count')
    ).first()
    
    return render_template('admin/packages.html', 
                         packages=packages, 
                         status=status,
                         summary={
                             'total': summary.total or 0,
                             'total_value': float(summary.total_value or 0),
                             'active_count': summary.active_count or 0
                         })


@admin_bp.route('/bonuses')
@admin_required
def bonuses_page():
    """Bonuses management HTML page"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'pending')
    
    query = Bonus.query.options(db.joinedload(Bonus.user))
    
    if status != 'all':
        query = query.filter(Bonus.status == status)
    
    bonuses = query.order_by(Bonus.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    
    summary = db.session.query(
        func.coalesce(func.sum(Bonus.amount).filter(Bonus.status == 'pending'), 0).label('pending_total'),
        func.count(Bonus.id).filter(Bonus.status == 'pending').label('pending_count'),
        func.coalesce(func.sum(Bonus.amount).filter(Bonus.status == 'paid'), 0).label('paid_total')
    ).first()
    
    return render_template('admin/bonuses.html', 
                         bonuses=bonuses, 
                         status=status,
                         summary={
                             'pending_total': float(summary.pending_total or 0),
                             'pending_count': summary.pending_count or 0,
                             'paid_total': float(summary.paid_total or 0)
                         })


@admin_bp.route('/users/<int:user_id>')
@admin_required
def user_detail_page(user_id):
    """User detail HTML page"""
    user = User.query.options(
        db.joinedload(User.profile),
        db.joinedload(User.wallet),
        db.joinedload(User.packages).joinedload(Package.catalog)
    ).get_or_404(user_id)
    
    packages = Package.query.filter_by(user_id=user_id)\
        .options(db.joinedload(Package.catalog))\
        .order_by(Package.created_at.desc()).all()
    
    withdrawals = Withdrawal.query.filter_by(user_id=user_id)\
        .order_by(Withdrawal.created_at.desc()).limit(50).all()
    
    referrals_count = Referral.query.filter_by(referrer_id=user_id).count()
    transactions = Transaction.query.filter_by(user_id=user_id)\
        .order_by(Transaction.created_at.desc()).limit(20).all()
    
    bonus_summary = db.session.query(
        func.count(Bonus.id).label('total_bonuses'),
        func.coalesce(func.sum(Bonus.amount), 0).label('total_amount')
    ).filter(Bonus.user_id == user_id, Bonus.status == 'paid').first()
    
    return render_template('admin/user_detail.html', 
                         user=user, packages=packages, withdrawals=withdrawals,
                         referrals_count=referrals_count, transactions=transactions,
                         bonus_summary=bonus_summary)


# ===========================================================
# API ENDPOINTS - DASHBOARD STATS
# ===========================================================

@admin_bp.route('/api/stats', methods=['GET'])
@admin_required
def api_stats():
    """Get dashboard statistics - matches frontend /admin/api/stats"""
    try:
        today = datetime.now(timezone.utc).date()
        
        stats = {
            'total_users': User.query.filter_by(is_active=True).count(),
            'pending_users': User.query.filter_by(is_verified=False).count(),
            'active_packages': Package.query.filter_by(status='active').count(),
            'pending_withdrawals': Withdrawal.query.filter_by(status='pending').count(),
            'total_volume': float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
                Transaction.type == 'deposit', Transaction.status == 'completed').scalar() or 0),
            'total_bonus_paid': float(db.session.query(func.coalesce(func.sum(Bonus.amount), 0)).filter(
                Bonus.status == 'paid').scalar() or 0),
            'today_users': User.query.filter(func.date(User.created_at) == today).count(),
            'today_withdrawals': Withdrawal.query.filter(func.date(Withdrawal.created_at) == today).count()
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/users/recent', methods=['GET'])
@admin_required
def api_recent_users():
    """Get recent users - matches frontend /admin/api/users/recent"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        users = User.query.options(
            db.joinedload(User.profile),
            db.joinedload(User.wallet)
        ).order_by(User.created_at.desc()).limit(limit).all()
        
        result = [{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'phone': u.phone,
            'role': u.role,
            'is_active': u.is_active,
            'is_verified': u.is_verified,
            'actual_balance': float(u.actual_balance or 0),
            'available_balance': float(u.available_balance or 0),
            'created_at': u.created_at.isoformat() if u.created_at else None
        } for u in users]
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error fetching recent users: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/withdrawals/recent', methods=['GET'])
@admin_required
def api_recent_withdrawals():
    """Get recent withdrawals - matches frontend /admin/api/withdrawals/recent"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        withdrawals = Withdrawal.query.options(
            db.joinedload(Withdrawal.user)
        ).order_by(Withdrawal.created_at.desc()).limit(limit).all()
        
        result = [{
            'id': w.id,
            'amount': float(w.amount),
            'net_amount': float(w.net_amount) if w.net_amount else None,
            'fee': float(w.fee) if w.fee else 0,
            'status': w.status,
            'phone': w.phone,
            'user_id': w.user_id,
            'user': {'username': w.user.username} if w.user else None,
            'created_at': w.created_at.isoformat() if w.created_at else None
        } for w in withdrawals]
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error fetching recent withdrawals: {e}")
        return jsonify({'error': str(e)}), 500


# ===========================================================
# API ENDPOINTS - USER MANAGEMENT
# ===========================================================

@admin_bp.route('/api/users', methods=['GET'])
@admin_required
def api_users_list():
    """Get paginated users list - matches frontend /admin/api/users"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '').strip()
        status = request.args.get('status', 'all')
        per_page = 20
        
        query = User.query.options(
            db.joinedload(User.profile),
            db.joinedload(User.wallet)
        )
        
        if search:
            query = query.filter(
                or_(
                    User.username.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%'),
                    User.phone.ilike(f'%{search}%')
                )
            )
        
        if status == 'active':
            query = query.filter_by(is_active=True)
        elif status == 'inactive':
            query = query.filter_by(is_active=False)
        
        paginated = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        users = [{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'phone': u.phone,
            'role': u.role,
            'is_active': u.is_active,
            'is_verified': u.is_verified,
            'actual_balance': float(u.actual_balance or 0),
            'available_balance': float(u.available_balance or 0),
            'created_at': u.created_at.isoformat() if u.created_at else None
        } for u in paginated.items]
        
        return jsonify({
            'items': users,
            'total': paginated.total,
            'page': paginated.page,
            'pages': paginated.pages,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/users/<int:user_id>/verify', methods=['POST'])
@admin_required
def api_verify_user(user_id):
    """Verify a user - matches frontend /admin/api/users/{id}/verify"""
    user = User.query.get_or_404(user_id)
    
    try:
        user.is_verified = True
        
        if user.profile:
            user.profile.kyc_status = 'approved'
        
        log_admin_action(request.admin_user.id, 'verify_user', 'user', user_id,
                        old_value='unverified', new_value='verified')
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'User {user.username} verified successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error verifying user: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/api/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def api_toggle_user_status(user_id):
    """Toggle user active status - matches frontend /admin/api/users/{id}/toggle-status"""
    user = User.query.get_or_404(user_id)
    
    if user.id == request.admin_user.id:
        return jsonify({'success': False, 'message': 'Cannot modify your own status'}), 400
    
    try:
        old_status = user.is_active
        user.is_active = not user.is_active
        
        log_admin_action(request.admin_user.id, 'toggle_status', 'user', user_id,
                        old_value=str(old_status), new_value=str(user.is_active))
        
        db.session.commit()
        status_text = 'activated' if user.is_active else 'deactivated'
        return jsonify({'success': True, 'message': f'User {status_text} successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling user status: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/api/users/<int:user_id>/delete', methods=['DELETE'])
@admin_required
def api_delete_user(user_id):
    """Soft delete user - matches frontend /admin/api/users/{id}/delete"""
    user = User.query.get_or_404(user_id)
    
    if user.id == request.admin_user.id:
        return jsonify({'success': False, 'message': 'Cannot delete your own account'}), 400
    
    try:
        user.is_active = False
        user.role = 'deleted'
        
        log_admin_action(request.admin_user.id, 'delete_user', 'user', user_id,
                        old_value='active', new_value='deleted')
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'User {user.username} deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/api/users/<int:user_id>/role', methods=['POST'])
@admin_required
def api_change_user_role(user_id):
    """Change user role - matches frontend /admin/api/users/{id}/role"""
    user = User.query.get_or_404(user_id)
    new_role = request.json.get('role')
    
    if new_role not in ['user', 'admin', 'super_admin']:
        return jsonify({'success': False, 'message': 'Invalid role'}), 400
    
    try:
        old_role = user.role
        user.role = new_role
        
        log_admin_action(request.admin_user.id, 'change_role', 'user', user_id,
                        old_value=old_role, new_value=new_role)
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Role changed to {new_role}'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error changing user role: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ===========================================================
# API ENDPOINTS - WITHDRAWAL MANAGEMENT
# ===========================================================

@admin_bp.route('/api/withdrawals', methods=['GET'])
@admin_required
def api_withdrawals_list():
    """Get paginated withdrawals - matches frontend /admin/api/withdrawals"""
    try:
        page = request.args.get('page', 1, type=int)
        status_filter = request.args.get('status', 'pending')
        per_page = 20
        
        query = Withdrawal.query.options(db.joinedload(Withdrawal.user))
        
        if status_filter != 'all':
            query = query.filter(Withdrawal.status == status_filter)
        
        paginated = query.order_by(
            case((Withdrawal.status == 'pending', 1), else_=2),
            Withdrawal.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        withdrawals = [{
            'id': w.id,
            'amount': float(w.amount),
            'net_amount': float(w.net_amount) if w.net_amount else None,
            'fee': float(w.fee) if w.fee else 0,
            'status': w.status,
            'phone': w.phone,
            'user_id': w.user_id,
            'user': {'username': w.user.username} if w.user else None,
            'created_at': w.created_at.isoformat() if w.created_at else None
        } for w in paginated.items]
        
        # Summary stats
        summary = {
            'pending_total': float(db.session.query(func.coalesce(func.sum(Withdrawal.amount), 0))
                                   .filter(Withdrawal.status == 'pending').scalar() or 0),
            'pending_count': Withdrawal.query.filter_by(status='pending').count(),
            'completed_total': float(db.session.query(func.coalesce(func.sum(Withdrawal.amount), 0))
                                     .filter(Withdrawal.status == 'approved').scalar() or 0)
        }
        
        return jsonify({
            'items': withdrawals,
            'total': paginated.total,
            'page': paginated.page,
            'pages': paginated.pages,
            'per_page': per_page,
            'pending_total': summary['pending_total'],
            'pending_count': summary['pending_count'],
            'paid_total': summary['completed_total']
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching withdrawals: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/withdrawals/<int:withdrawal_id>/approve', methods=['POST'])
@admin_required
def api_approve_withdrawal(withdrawal_id):
    """Approve withdrawal - matches frontend /admin/api/withdrawals/{id}/approve"""
    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)
    
    if withdrawal.status != 'pending':
        return jsonify({'success': False, 'message': 'Withdrawal already processed'}), 400
    
    try:
        withdrawal.status = 'approved'
        withdrawal.processed_by = request.admin_user.id
        withdrawal.processed_at = datetime.now(timezone.utc)
        
        user = withdrawal.user
        if user and user.wallet:
            transaction = Transaction(
                wallet_id=user.wallet.id,
                user_id=user.id,
                type='withdrawal',
                amount=-withdrawal.amount,
                status='completed',
                reference=withdrawal.reference or f'WDL_{withdrawal_id}_{int(datetime.now().timestamp())}'
            )
            db.session.add(transaction)
            
            user.actual_balance = db.session.query(
                User.actual_balance - withdrawal.amount
            ).filter(User.id == user.id).scalar()
            
            user.available_balance = db.session.query(
                User.available_balance - withdrawal.amount
            ).filter(User.id == user.id).scalar()
        
        log_admin_action(request.admin_user.id, 'approve_withdrawal', 'withdrawal', withdrawal_id,
                        old_value='pending', new_value='approved')
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Withdrawal approved successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error approving withdrawal: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/api/withdrawals/<int:withdrawal_id>/reject', methods=['POST'])
@admin_required
def api_reject_withdrawal(withdrawal_id):
    """Reject withdrawal - matches frontend /admin/api/withdrawals/{id}/reject"""
    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)
    reason = request.json.get('reason', 'No reason provided')
    
    if withdrawal.status != 'pending':
        return jsonify({'success': False, 'message': 'Withdrawal already processed'}), 400
    
    try:
        withdrawal.status = 'rejected'
        withdrawal.processed_by = request.admin_user.id
        withdrawal.processed_at = datetime.now(timezone.utc)
        
        if hasattr(withdrawal, 'rejection_reason'):
            withdrawal.rejection_reason = reason
        
        log_admin_action(request.admin_user.id, 'reject_withdrawal', 'withdrawal', withdrawal_id,
                        old_value='pending', new_value='rejected')
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Withdrawal rejected'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error rejecting withdrawal: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ===========================================================
# API ENDPOINTS - PACKAGE MANAGEMENT
# ===========================================================

@admin_bp.route('/api/packages', methods=['GET'])
@admin_required
def api_packages_list():
    """Get paginated packages - matches frontend /admin/api/packages"""
    try:
        page = request.args.get('page', 1, type=int)
        status_filter = request.args.get('status', 'active')
        per_page = 20
        
        query = Package.query.options(
            db.joinedload(Package.user),
            db.joinedload(Package.catalog)
        )
        
        if status_filter != 'all':
            query = query.filter(Package.status == status_filter)
        
        paginated = query.order_by(Package.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        packages = [{
            'id': p.id,
            'package': p.package,
            'package_amount': float(p.package_amount),
            'status': p.status,
            'user_id': p.user_id,
            'user': {'username': p.user.username} if p.user else None,
            'catalog': {'name': p.catalog.name} if p.catalog else None,
            'activated_at': p.activated_at.isoformat() if p.activated_at else None,
            'expires_at': p.expires_at.isoformat() if p.expires_at else None,
            'created_at': p.created_at.isoformat() if p.created_at else None
        } for p in paginated.items]
        
        summary = db.session.query(
            func.count(Package.id).label('total'),
            func.coalesce(func.sum(Package.package_amount), 0).label('total_value'),
            func.count(Package.id).filter(Package.status == 'active').label('active_count')
        ).first()
        
        return jsonify({
            'items': packages,
            'total': paginated.total,
            'page': paginated.page,
            'pages': paginated.pages,
            'per_page': per_page,
            'total_count': summary.total or 0,
            'active_count': summary.active_count or 0,
            'total_value': float(summary.total_value or 0)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching packages: {e}")
        return jsonify({'error': str(e)}), 500


# ===========================================================
# API ENDPOINTS - BONUS MANAGEMENT
# ===========================================================

@admin_bp.route('/api/bonuses', methods=['GET'])
@admin_required
def api_bonuses_list():
    """Get paginated bonuses - matches frontend /admin/api/bonuses"""
    try:
        page = request.args.get('page', 1, type=int)
        status_filter = request.args.get('status', 'pending')
        per_page = 20
        
        query = Bonus.query.options(db.joinedload(Bonus.user))
        
        if status_filter != 'all':
            query = query.filter(Bonus.status == status_filter)
        
        paginated = query.order_by(Bonus.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        bonuses = [{
            'id': b.id,
            'amount': float(b.amount) if b.amount else 0,
            'type': b.type,
            'status': b.status,
            'user_id': b.user_id,
            'user': {'username': b.user.username} if b.user else None,
            'created_at': b.created_at.isoformat() if b.created_at else None,
            'paid_at': b.paid_at.isoformat() if hasattr(b, 'paid_at') and b.paid_at else None
        } for b in paginated.items]
        
        summary = db.session.query(
            func.coalesce(func.sum(Bonus.amount).filter(Bonus.status == 'pending'), 0).label('pending_total'),
            func.count(Bonus.id).filter(Bonus.status == 'pending').label('pending_count'),
            func.coalesce(func.sum(Bonus.amount).filter(Bonus.status == 'paid'), 0).label('paid_total')
        ).first()
        
        return jsonify({
            'items': bonuses,
            'total': paginated.total,
            'page': paginated.page,
            'pages': paginated.pages,
            'per_page': per_page,
            'pending_total': float(summary.pending_total or 0),
            'pending_count': summary.pending_count or 0,
            'paid_total': float(summary.paid_total or 0)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching bonuses: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/bonuses/<int:bonus_id>/release', methods=['POST'])
@admin_required
def api_release_bonus(bonus_id):
    """Release bonus - matches frontend /admin/api/bonuses/{id}/release"""
    bonus = Bonus.query.get_or_404(bonus_id)
    
    if bonus.status == 'paid':
        return jsonify({'success': False, 'message': 'Bonus already paid'}), 400
    
    try:
        bonus.status = 'paid'
        bonus.paid_at = datetime.now(timezone.utc)
        
        if bonus.user and bonus.user.wallet:
            transaction = Transaction(
                wallet_id=bonus.user.wallet.id,
                user_id=bonus.user_id,
                type='bonus',
                amount=bonus.amount,
                status='completed',
                reference=f'BONUS_{bonus_id}_{int(datetime.now().timestamp())}'
            )
            db.session.add(transaction)
            
            bonus.user.actual_balance = db.session.query(
                User.actual_balance + bonus.amount
            ).filter(User.id == bonus.user_id).scalar()
            
            bonus.user.available_balance = db.session.query(
                User.available_balance + bonus.amount
            ).filter(User.id == bonus.user_id).scalar()
        
        log_admin_action(request.admin_user.id, 'release_bonus', 'bonus', bonus_id,
                        old_value='pending', new_value='paid')
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Bonus of {bonus.amount} released successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error releasing bonus: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ===========================================================
# API ENDPOINTS - EXPORTS
# ===========================================================

@admin_bp.route('/api/export/users', methods=['GET'])
@admin_required
def api_export_users():
    """Export users to CSV - matches frontend /admin/api/export/users"""
    def generate():
        yield ','.join(['ID', 'Username', 'Email', 'Phone', 'Role', 'Is Active', 
                       'Is Verified', 'Join Date', 'Actual Balance', 'Available Balance']) + '\n'
        
        chunk_size = 1000
        offset = 0
        
        while True:
            users = User.query.offset(offset).limit(chunk_size).all()
            if not users:
                break
            
            for user in users:
                row = [
                    str(user.id), user.username, user.email or '', user.phone, user.role,
                    'Active' if user.is_active else 'Inactive',
                    'Verified' if user.is_verified else 'Unverified',
                    user.member_since.isoformat() if user.member_since else '',
                    str(float(user.actual_balance or 0)), str(float(user.available_balance or 0))
                ]
                yield ','.join(f'"{item}"' for item in row) + '\n'
            
            offset += chunk_size
    
    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=users_export.csv"}
    )


@admin_bp.route('/api/export/withdrawals', methods=['GET'])
@admin_required
def api_export_withdrawals():
    """Export withdrawals to CSV - matches frontend /admin/api/export/withdrawals"""
    def generate():
        yield ','.join(['ID', 'User ID', 'Username', 'Amount', 'Status', 'Phone', 
                       'Request Date', 'Processed Date']) + '\n'
        
        chunk_size = 1000
        offset = 0
        
        while True:
            withdrawals = Withdrawal.query.options(
                db.joinedload(Withdrawal.user)
            ).offset(offset).limit(chunk_size).all()
            
            if not withdrawals:
                break
            
            for w in withdrawals:
                row = [
                    str(w.id), str(w.user_id), w.user.username if w.user else 'Unknown',
                    str(float(w.amount)), w.status, w.phone or '',
                    w.created_at.isoformat() if w.created_at else '',
                    w.processed_at.isoformat() if w.processed_at else ''
                ]
                yield ','.join(f'"{item}"' for item in row) + '\n'
            
            offset += chunk_size
    
    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=withdrawals_export.csv"}
    )


# ===========================================================
# API ENDPOINTS - SEARCH
# ===========================================================

@admin_bp.route('/api/search', methods=['GET'])
@admin_required
def api_search():
    """Global search across users, payments, bonuses - matches frontend /admin/api/search"""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'users': [], 'payments': [], 'bonuses': [], 'total_results': 0}), 200
        
        users = search_users(query)
        payments = search_payments(query)
        bonuses = search_bonuses(query)
        
        return jsonify({
            'users': users,
            'payments': payments,
            'bonuses': bonuses,
            'total_results': len(users) + len(payments) + len(bonuses)
        }), 200
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500


def search_users(query):
    """Search users helper"""
    try:
        if query.isdigit():
            users = User.query.filter(
                or_(
                    User.id == int(query),
                    User.username.ilike(f'%{query}%'),
                    User.email.ilike(f'%{query}%'),
                    User.phone.ilike(f'%{query}%')
                )
            ).limit(50).all()
        else:
            users = User.query.filter(
                or_(
                    User.username.ilike(f'%{query}%'),
                    User.email.ilike(f'%{query}%'),
                    User.phone.ilike(f'%{query}%')
                )
            ).limit(50).all()
        
        return [{
            'type': 'user',
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'phone': u.phone,
            'is_active': u.is_active
        } for u in users]
    except Exception as e:
        logger.error(f"Error searching users: {e}")
        return []


def search_payments(query):
    """Search payments helper"""
    try:
        if query.isdigit():
            payments = Payment.query.filter(
                or_(
                    Payment.id == int(query),
                    Payment.reference.ilike(f'%{query}%'),
                    Payment.phone_number.ilike(f'%{query}%')
                )
            ).limit(50).all()
        else:
            payments = Payment.query.filter(
                or_(
                    Payment.reference.ilike(f'%{query}%'),
                    Payment.phone_number.ilike(f'%{query}%')
                )
            ).limit(50).all()
        
        return [{
            'type': 'payment',
            'id': p.id,
            'reference': p.reference,
            'amount': float(p.amount),
            'status': p.status,
            'user_id': p.user_id
        } for p in payments]
    except Exception as e:
        logger.error(f"Error searching payments: {e}")
        return []


def search_bonuses(query):
    """Search bonuses helper"""
    try:
        bonuses = Bonus.query.join(User).filter(
            or_(
                Bonus.type.ilike(f'%{query}%'),
                User.username.ilike(f'%{query}%')
            )
        ).limit(50).all()
        
        return [{
            'type': 'bonus',
            'id': b.id,
            'amount': float(b.amount) if b.amount else 0,
            'status': b.status,
            'user_id': b.user_id
        } for b in bonuses]
    except Exception as e:
        logger.error(f"Error searching bonuses: {e}")
        return []


# ===========================================================
# TEST ENDPOINT
# ===========================================================

@admin_bp.route('/api/ping', methods=['GET'])
@admin_required
def api_ping():
    """Test endpoint to verify API connectivity"""
    return jsonify({
        'status': 'ok',
        'message': 'Admin API is working',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'user_id': request.admin_user.id,
        'user_role': request.admin_user.role
    }), 200


# ===========================================================
# HELPER FUNCTIONS
# ===========================================================

def log_admin_action(admin_id, action, target_type, target_id, old_value=None, new_value=None):
    """Log admin actions for audit trail"""
    try:
        log = AdminAction(
            admin_id=admin_id,
            action_type=action,
            target_type=target_type,
            target_id=target_id,
            old_value=str(old_value) if old_value else None,
            new_value=str(new_value) if new_value else None,
            ip_address=request.remote_addr if request else None
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")
        db.session.rollback()


# ===========================================================
# ROOT REDIRECT
# ===========================================================

@admin_bp.route('')
@admin_required
def admin_root():
    """Redirect root admin to dashboard"""
    return redirect(url_for('admin.admin_dashboard_page'))

# ===========================================================
# MISSING ENDPOINTS THAT RETURNED 404
# Add these to your admin.py
# ===========================================================

@admin_bp.route('/api/stats/growth', methods=['GET'])
@admin_required
def api_stats_growth():
    """Get user growth data for charts - 30 days"""
    try:
        days = request.args.get('days', 30, type=int)
        
        labels = []
        data = []
        
        for i in range(days - 1, -1, -1):
            date = datetime.now(timezone.utc).date() - timedelta(days=i)
            labels.append(date.strftime('%b %d'))
            
            count = User.query.filter(
                func.date(User.created_at) == date
            ).count()
            data.append(count)
        
        return jsonify({
            'labels': labels,
            'data': data
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching growth stats: {e}")
        return jsonify({'labels': [], 'data': []}), 200


@admin_bp.route('/api/logs', methods=['GET'])
@admin_required
def api_logs():
    """Get paginated audit logs"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '').strip()
        per_page = 20
        
        query = AdminAction.query.options(
            db.joinedload(AdminAction.admin)
        )
        
        if search:
            query = query.filter(
                or_(
                    AdminAction.action_type.ilike(f'%{search}%'),
                    AdminAction.target_type.ilike(f'%{search}%'),
                    AdminAction.target_id.cast(db.String).ilike(f'%{search}%')
                )
            )
        
        paginated = query.order_by(AdminAction.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        logs = []
        for log in paginated.items:
            logs.append({
                'id': log.id,
                'admin_id': log.admin_id,
                'admin_username': log.admin.username if log.admin else 'System',
                'action_type': log.action_type,
                'target_type': log.target_type,
                'target_id': log.target_id,
                'old_value': log.old_value[:100] if log.old_value else None,
                'new_value': log.new_value[:100] if log.new_value else None,
                'ip_address': log.ip_address,
                'created_at': log.created_at.isoformat() if log.created_at else None
            })
        
        return jsonify({
            'items': logs,
            'total': paginated.total,
            'page': paginated.page,
            'pages': paginated.pages,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/packages/stats', methods=['GET'])
@admin_required
def api_packages_stats():
    """Get package distribution for pie chart"""
    try:
        active = Package.query.filter_by(status='active').count()
        completed = Package.query.filter_by(status='completed').count()
        expired = Package.query.filter_by(status='expired').count()
        
        return jsonify({
            'labels': ['Active', 'Completed', 'Expired'],
            'data': [active, completed, expired]
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching package stats: {e}")
        return jsonify({'labels': [], 'data': []}), 200
    
#===================================================================================
#===================================================================================
