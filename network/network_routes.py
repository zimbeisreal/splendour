# blueprints/network_api.py
"""
Network API Blueprint - Downline Management
"""

from flask import Blueprint, request, jsonify, session, g
from extensions import db
from models import User, Notification, ReferralBonus, Package, ReferralBonusPlan, Referral
from network.network import (
    NetworkQueryOptimizer, NetworkSecurity, DownlineMessaging,
    NetworkAnalytics, NetworkSnapshot
)
from sqlalchemy import func
from functools import wraps
import logging
from datetime import datetime, timezone

network_bp = Blueprint('network_api', __name__, url_prefix='/api/network')
logger = logging.getLogger(__name__)


# ===========================================================
# AUTH DECORATOR
# ===========================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(max_per_minute=30):
    """Simple rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Implement rate limiting using Redis or database
            # For now, returns the function
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ===========================================================
# DOWNLINE ENDPOINTS
# ===========================================================

@network_bp.route('/downline', methods=['GET'])
@login_required
@rate_limit(30)
def get_downline():
    """
    Get user's downline tree
    Query params:
        - depth: int (1-20, default=5)
        - include_inactive: bool (default=true)
        - format: 'tree' or 'list' (default='tree')
    """
    user_id = g.user_id
    depth = min(request.args.get('depth', 5, type=int), 20)
    include_inactive = request.args.get('include_inactive', 'true').lower() == 'true'
    format_type = request.args.get('format', 'tree')
    
    try:
        if format_type == 'list':
            # Flat list format
            downline = NetworkQueryOptimizer.get_downline_with_details(
                user_id, depth, include_inactive
            )
            summary = NetworkQueryOptimizer.get_network_summary(user_id)
            
            return jsonify({
                'success': True,
                'format': 'list',
                'depth': depth,
                'total': len(downline),
                'summary': summary['summary'],
                'level_breakdown': summary['level_breakdown'],
                'downline': downline
            }), 200
        
        else:
            # Tree format (nested)
            tree = build_downline_tree(user_id, depth, include_inactive)
            summary = NetworkQueryOptimizer.get_network_summary(user_id)
            
            return jsonify({
                'success': True,
                'format': 'tree',
                'depth': depth,
                'summary': summary['summary'],
                'level_breakdown': summary['level_breakdown'],
                'downline': tree
            }), 200
            
    except Exception as e:
        logger.error(f"Failed to fetch downline: {e}")
        return jsonify({'error': 'Failed to fetch downline data'}), 500


def build_downline_tree(user_id, max_depth, include_inactive, current_depth=1):
    """Recursively build downline tree"""
    if current_depth > max_depth:
        return []
    
    # Get direct referrals for this user
    direct = NetworkQueryOptimizer.get_downline_with_details(
        user_id, 1, include_inactive
    )
    
    tree = []
    for member in direct:
        node = {
            'user_id': member['user_id'],
            'username': member['username'],
            'level': current_depth,
            'is_active': member['is_active'],
            'is_verified': member['is_verified'],
            'joined_date': member['joined_date'],
            'total_invested': member['total_invested'],
            'active_packages': member['active_packages'],
            'downline_count': 0,  # Will be calculated
            'downline': []
        }
        
        # Get children (next level)
        children = build_downline_tree(
            member['user_id'], max_depth, include_inactive, current_depth + 1
        )
        
        if children:
            node['downline'] = children
            node['downline_count'] = len(children)
        
        tree.append(node)
    
    return tree


@network_bp.route('/downline/direct', methods=['GET'])
@login_required
def get_direct_referrals():
    """Get only direct referrals (Level 1) with contact info"""
    user_id = g.user_id
    
    try:
        direct_referrals = NetworkQueryOptimizer.get_direct_referrals_with_contact(user_id)
        
        return jsonify({
            'success': True,
            'count': len(direct_referrals),
            'referrals': direct_referrals
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to fetch direct referrals: {e}")
        return jsonify({'error': 'Failed to fetch referrals'}), 500


@network_bp.route('/downline/<int:downline_id>', methods=['GET'])
@login_required
def get_downline_member(downline_id):
    """Get specific downline member details"""
    user_id = g.user_id
    
    # Verify access
    if not NetworkSecurity.validate_network_access(user_id, downline_id):
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get member details
        members = NetworkQueryOptimizer.get_downline_with_details(user_id, 5, True)
        member = next((m for m in members if m['user_id'] == downline_id), None)
        
        if not member:
            return jsonify({'error': 'Member not found in your downline'}), 404
        
        # Get additional stats
        member_stats = db.session.query(
            func.count(Package.id).filter(Package.status == 'completed').label('completed_packages'),
            func.coalesce(func.sum(ReferralBonus.bonus_amount).filter(
                ReferralBonus.referrer_id == downline_id
            ), 0).label('earned_from_their_downline')
        ).first()
        
        member['completed_packages'] = member_stats.completed_packages or 0
        member['earned_from_their_downline'] = float(member_stats.earned_from_their_downline or 0)
        
        # Add contact info based on relationship
        contact_info = NetworkSecurity.sanitize_contact_info(
            User.query.get(downline_id), user_id
        )
        member['contact_info'] = contact_info
        
        return jsonify({
            'success': True,
            'member': member
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to fetch member details: {e}")
        return jsonify({'error': 'Failed to fetch member details'}), 500


# ===========================================================
# NETWORK SUMMARY ENDPOINTS
# ===========================================================

@network_bp.route('/summary', methods=['GET'])
@login_required
def get_network_summary():
    """Get comprehensive network summary"""
    user_id = g.user_id
    
    try:
        summary = NetworkQueryOptimizer.get_network_summary(user_id)
        growth = NetworkAnalytics.get_network_growth(user_id, 30)
        top_performers = NetworkAnalytics.get_top_performers(user_id, 5)
        
        return jsonify({
            'success': True,
            'summary': summary['summary'],
            'level_breakdown': summary['level_breakdown'],
            'growth': growth,
            'top_performers': top_performers
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get network summary: {e}")
        return jsonify({'error': 'Failed to get summary'}), 500


@network_bp.route('/analytics/growth', methods=['GET'])
@login_required
def get_network_growth():
    """Get network growth analytics"""
    user_id = g.user_id
    days = min(request.args.get('days', 30, type=int), 90)
    
    try:
        growth = NetworkAnalytics.get_network_growth(user_id, days)
        trends = NetworkAnalytics.get_investment_trends(user_id)
        
        return jsonify({
            'success': True,
            'days': days,
            'growth': growth,
            'investment_trends': trends
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get growth analytics: {e}")
        return jsonify({'error': 'Failed to get growth data'}), 500


@network_bp.route('/analytics/leaderboard', methods=['GET'])
@login_required
def get_leaderboard():
    """Get downline leaderboard"""
    user_id = g.user_id
    limit = min(request.args.get('limit', 10, type=int), 50)
    
    try:
        top_performers = NetworkAnalytics.get_top_performers(user_id, limit)
        
        return jsonify({
            'success': True,
            'leaderboard': top_performers,
            'your_rank': next(
                (i+1 for i, p in enumerate(top_performers) if p['user_id'] == user_id),
                len(top_performers) + 1
            )
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get leaderboard: {e}")
        return jsonify({'error': 'Failed to get leaderboard'}), 500


# ===========================================================
# MESSAGING ENDPOINTS
# ===========================================================

@network_bp.route('/message/send', methods=['POST'])
@login_required
def send_downline_message():
    """Send message to downline member"""
    user_id = g.user_id
    data = request.get_json()
    
    downline_id = data.get('downline_id')
    message = data.get('message', '').strip()
    message_type = data.get('message_type', 'encouragement')
    
    if not downline_id or not message:
        return jsonify({'error': 'downline_id and message are required'}), 400
    
    if len(message) > 500:
        return jsonify({'error': 'Message too long (max 500 characters)'}), 400
    
    success, result = DownlineMessaging.send_message(
        user_id, downline_id, message, message_type
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': result
        }), 200
    else:
        return jsonify({'error': result}), 400


@network_bp.route('/message/bulk', methods=['POST'])
@login_required
def send_bulk_messages():
    """Send message to multiple downline members"""
    user_id = g.user_id
    data = request.get_json()
    
    message = data.get('message', '').strip()
    level_filter = data.get('level')  # Optional: filter by level
    min_investment = data.get('min_investment', 0)
    message_type = data.get('message_type', 'announcement')
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Get filtered downline
    downline = NetworkQueryOptimizer.get_downline_with_details(user_id, 5, True)
    
    # Apply filters
    if level_filter:
        downline = [m for m in downline if m['level'] == level_filter]
    
    if min_investment > 0:
        downline = [m for m in downline if m['total_invested'] >= min_investment]
    
    if not downline:
        return jsonify({'error': 'No downline members match criteria'}), 404
    
    # Rate limit check
    if len(downline) > 50:
        return jsonify({'error': 'Cannot send to more than 50 members at once'}), 400
    
    # Send messages
    results = {'success': 0, 'failed': 0, 'errors': []}
    
    for member in downline:
        success, result = DownlineMessaging.send_message(
            user_id, member['user_id'], message, message_type
        )
        
        if success:
            results['success'] += 1
        else:
            results['failed'] += 1
            results['errors'].append({
                'user_id': member['user_id'],
                'username': member['username'],
                'error': result
            })
    
    return jsonify({
        'success': results['failed'] == 0,
        'results': results
    }), 200


@network_bp.route('/message/templates', methods=['GET'])
@login_required
def get_message_templates():
    """Get predefined message templates"""
    templates = DownlineMessaging.get_message_templates()
    
    return jsonify({
        'success': True,
        'templates': templates
    }), 200


# ===========================================================
# BONUS & COMMISSION ENDPOINTS
# ===========================================================

@network_bp.route('/bonus/earnings', methods=['GET'])
@login_required
def get_bonus_earnings():
    """Get bonus earnings from downline"""
    user_id = g.user_id
    level = request.args.get('level', type=int)
    
    try:
        query = ReferralBonus.query.filter(
            ReferralBonus.referrer_id == user_id,
            ReferralBonus.status == 'paid'
        )
        
        if level:
            query = query.filter(ReferralBonus.level == level)
        
        bonuses = query.order_by(ReferralBonus.calculated_on.desc()).limit(100).all()
        
        # Summarize by level
        summary = db.session.query(
            ReferralBonus.level,
            func.count(ReferralBonus.id).label('count'),
            func.sum(ReferralBonus.bonus_amount).label('total')
        ).filter(
            ReferralBonus.referrer_id == user_id,
            ReferralBonus.status == 'paid'
        ).group_by(ReferralBonus.level).order_by(ReferralBonus.level).all()
        
        return jsonify({
            'success': True,
            'summary': [
                {
                    'level': s.level,
                    'count': s.count,
                    'total': float(s.total or 0)
                }
                for s in summary
            ],
            'recent_bonuses': [
                {
                    'id': b.id,
                    'amount': float(b.bonus_amount),
                    'level': b.level,
                    'from_user_id': b.user_id,
                    'calculated_on': b.calculated_on.isoformat() if b.calculated_on else None
                }
                for b in bonuses
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get bonus earnings: {e}")
        return jsonify({'error': 'Failed to get bonus data'}), 500


@network_bp.route('/bonus/plan', methods=['GET'])
@login_required
def get_bonus_plan():
    """Get current bonus percentages by level"""
    try:
        bonus_plan = ReferralBonusPlan.query.filter(
            ReferralBonusPlan.is_active == True
        ).order_by(ReferralBonusPlan.level).all()
        
        return jsonify({
            'success': True,
            'bonus_plan': [
                {
                    'level': plan.level,
                    'percentage': float(plan.bonus_percentage * 100),  # Convert to percentage
                    'min_qualifying_amount': float(plan.minimum_qualifying_amount or 0)
                }
                for plan in bonus_plan
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get bonus plan: {e}")
        return jsonify({'error': 'Failed to get bonus plan'}), 500


# ===========================================================
# REFERRAL LINK ENDPOINT
# ===========================================================

@network_bp.route('/referral-link', methods=['GET'])
@login_required
def get_referral_link():
    """Get user's referral link"""
    user_id = g.user_id
    user = User.query.get(user_id)
    
    if not user or not user.referral_code:
        return jsonify({'error': 'Referral code not found'}), 404
    
    base_url = request.host_url.rstrip('/')
    referral_link = f"{base_url}/register?ref={user.referral_code}"
    
    # Get share stats
    share_stats = {
        'total_clicks': 0,  # You'd track this with analytics
        'total_signups': Referral.query.filter_by(referrer_id=user_id).count(),
        'total_bonus_earned': float(
            ReferralBonus.query.filter_by(referrer_id=user_id, status='paid')
            .with_entities(db.func.sum(ReferralBonus.bonus_amount))
            .scalar() or 0
        )
    }
    
    return jsonify({
        'success': True,
        'referral_code': user.referral_code,
        'referral_link': referral_link,
        'share_stats': share_stats
    }), 200


# ===========================================================
# EXPORT ENDPOINT
# ===========================================================

@network_bp.route('/export/downline', methods=['GET'])
@login_required
def export_downline():
    """Export downline data as CSV"""
    user_id = g.user_id
    format_type = request.args.get('format', 'csv')
    
    downline = NetworkQueryOptimizer.get_downline_with_details(user_id, 5, True)