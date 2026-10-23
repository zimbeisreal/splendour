# utils/network_helpers.py
"""
Optimized network utilities for downline management
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import func, and_, or_, desc, asc
from sqlalchemy.orm import joinedload, selectinload
from extensions import db
from models import (
    User, Referral, ReferralNetwork, ReferralBonusPlan,
    NetworkSnapshot, Transaction, Package, Notification,
    Payment, ReferralBonus, AuditLog
)
import logging
from functools import lru_cache
import hashlib

logger = logging.getLogger(__name__)


class NetworkSecurity:
    """Security utilities for network operations"""
    
    @staticmethod
    def validate_network_access(user_id: int, target_id: int, max_depth: int = 20) -> bool:
        """Verify user has access to target's network data"""
        if user_id == target_id:
            return True
        
        # Check if target is in user's downline
        relationship = ReferralNetwork.query.filter(
            ReferralNetwork.ancestor_id == user_id,
            ReferralNetwork.descendant_id == target_id,
            ReferralNetwork.depth <= max_depth
        ).first()
        
        return relationship is not None
    
    @staticmethod
    def sanitize_contact_info(user: User, requester_id: int) -> Dict:
        """Return appropriate contact info based on relationship"""
        if requester_id == user.id:
            # Own profile - full info
            return {
                'phone': user.phone,
                'email': user.email,
                'username': user.username
            }
        
        # Check if requester is upline
        is_upline = ReferralNetwork.query.filter(
            ReferralNetwork.ancestor_id == requester_id,
            ReferralNetwork.descendant_id == user.id
        ).first()
        
        if is_upline:
            # Upline can see contact info
            return {
                'phone': user.phone,
                'email': user.email,
                'username': user.username
            }
        
        # Others - limited info
        return {
            'username': user.username,
            'can_contact': False,
            'message': f"Join {user.username}'s network to see contact info"
        }


class NetworkQueryOptimizer:
    """Optimized queries for network operations"""
    
    @staticmethod
    def get_downline_ids(user_id: int, depth: int = 5) -> List[int]:
        """Efficiently get all downline user IDs up to specified depth"""
        # Single query using ReferralNetwork table
        downline = ReferralNetwork.query.filter(
            ReferralNetwork.ancestor_id == user_id,
            ReferralNetwork.depth <= depth
        ).with_entities(ReferralNetwork.descendant_id).all()
        
        return [d[0] for d in downline]
    
    @staticmethod
    def get_downline_with_details(user_id: int, depth: int = 5, 
                                   include_inactive: bool = True) -> List[Dict]:
        """Get downline with user details in optimized single query"""
        
        # Base query
        query = db.session.query(
            ReferralNetwork.depth,
            ReferralNetwork.descendant_id,
            User.username,
            User.phone,
            User.email,
            User.is_active,
            User.is_verified,
            User.created_at,
            User.actual_balance,
            User.available_balance,
            func.coalesce(func.sum(Package.package_amount), 0).label('total_invested'),
            func.count(Package.id).label('active_packages'),
            func.coalesce(func.sum(Transaction.amount).filter(
                Transaction.type == 'deposit',
                Transaction.status == 'completed'
            ), 0).label('total_deposits')
        ).join(
            User, User.id == ReferralNetwork.descendant_id
        ).outerjoin(
            Package, and_(
                Package.user_id == User.id,
                Package.status == 'active'
            )
        ).outerjoin(
            Transaction, and_(
                Transaction.user_id == User.id,
                Transaction.status == 'completed'
            )
        ).filter(
            ReferralNetwork.ancestor_id == user_id,
            ReferralNetwork.depth <= depth
        ).group_by(
            ReferralNetwork.depth,
            ReferralNetwork.descendant_id,
            User.id
        )
        
        if not include_inactive:
            query = query.filter(User.is_active == True)
        
        results = query.order_by(
            asc(ReferralNetwork.depth),
            desc(func.coalesce(func.sum(Package.package_amount), 0))
        ).all()
        
        # Format results
        downline = []
        for row in results:
            downline.append({
                'user_id': row.descendant_id,
                'username': row.username,
                'phone': row.phone,
                'email': row.email,
                'level': row.depth,
                'is_active': row.is_active,
                'is_verified': row.is_verified,
                'joined_date': row.created_at.isoformat() if row.created_at else None,
                'total_invested': float(row.total_invested or 0),
                'active_packages': row.active_packages or 0,
                'total_deposits': float(row.total_deposits or 0),
                'actual_balance': float(row.actual_balance or 0),
                'available_balance': float(row.available_balance or 0)
            })
        
        return downline
    
    @staticmethod
    def get_network_summary(user_id: int) -> Dict:
        """Get comprehensive network summary in 2 optimized queries"""
        
        # Query 1: Network stats from ReferralNetwork
        network_stats = db.session.query(
            func.count(ReferralNetwork.descendant_id).label('total_downline'),
            func.sum(case((User.is_active == True, 1), else_=0)).label('active_count'),
            func.sum(case((User.is_active == False, 1), else_=0)).label('inactive_count'),
            func.avg(ReferralNetwork.depth).label('avg_depth'),
            func.max(ReferralNetwork.depth).label('max_depth')
        ).join(
            User, User.id == ReferralNetwork.descendant_id
        ).filter(
            ReferralNetwork.ancestor_id == user_id
        ).first()
        
        # Query 2: Level breakdown
        level_breakdown = db.session.query(
            ReferralNetwork.depth,
            func.count(ReferralNetwork.descendant_id).label('count')
        ).filter(
            ReferralNetwork.ancestor_id == user_id
        ).group_by(ReferralNetwork.depth).order_by(ReferralNetwork.depth).all()
        
        # Query 3: Financial stats
        financial_stats = db.session.query(
            func.coalesce(func.sum(Package.package_amount), 0).label('total_team_investment'),
            func.coalesce(func.sum(ReferralBonus.bonus_amount), 0).label('total_earned_bonus')
        ).outerjoin(
            ReferralNetwork, ReferralNetwork.descendant_id == Package.user_id
        ).outerjoin(
            ReferralBonus, and_(
                ReferralBonus.referrer_id == user_id,
                ReferralBonus.status == 'paid'
            )
        ).filter(
            ReferralNetwork.ancestor_id == user_id,
            Package.status == 'active'
        ).first()
        
        return {
            'summary': {
                'total_downline': network_stats.total_downline or 0,
                'active_downline': network_stats.active_count or 0,
                'inactive_downline': network_stats.inactive_count or 0,
                'average_depth': round(network_stats.avg_depth or 0, 2),
                'max_depth': network_stats.max_depth or 0,
                'total_team_investment': float(financial_stats.total_team_investment or 0),
                'total_earned_bonus': float(financial_stats.total_earned_bonus or 0)
            },
            'level_breakdown': {
                f'level_{level}': count for level, count in level_breakdown
            }
        }
    
    @staticmethod
    def get_direct_referrals_with_contact(user_id: int) -> List[Dict]:
        """Get direct referrals (Level 1) with contact info"""
        
        referrals = db.session.query(
            User.id,
            User.username,
            User.phone,
            User.email,
            User.is_active,
            User.is_verified,
            User.created_at,
            func.coalesce(func.sum(Package.package_amount), 0).label('total_invested'),
            func.max(Package.created_at).label('last_purchase_date')
        ).join(
            Referral, Referral.referred_id == User.id
        ).outerjoin(
            Package, and_(
                Package.user_id == User.id,
                Package.status == 'active'
            )
        ).filter(
            Referral.referrer_id == user_id,
            Referral.status == 'active'
        ).group_by(User.id).order_by(
            desc(func.coalesce(func.sum(Package.package_amount), 0))
        ).all()
        
        result = []
        for row in referrals:
            result.append({
                'id': row.id,
                'username': row.username,
                'phone': row.phone,
                'email': row.email,
                'is_active': row.is_active,
                'is_verified': row.is_verified,
                'joined_date': row.created_at.isoformat() if row.created_at else None,
                'total_invested': float(row.total_invested or 0),
                'last_purchase': row.last_purchase_date.isoformat() if row.last_purchase_date else None,
                'contact_allowed': True
            })
        
        return result


class DownlineMessaging:
    """Secure messaging to downline members"""
    
    @staticmethod
    def send_message(user_id: int, downline_id: int, message: str, 
                     message_type: str = 'encouragement') -> Tuple[bool, str]:
        """Send message to downline member"""
        
        # Verify relationship
        relationship = ReferralNetwork.query.filter(
            ReferralNetwork.ancestor_id == user_id,
            ReferralNetwork.descendant_id == downline_id
        ).first()
        
        if not relationship:
            return False, "User is not in your downline"
        
        # Rate limiting - max 10 messages per hour per downline
        recent_count = Notification.query.filter(
            Notification.user_id == downline_id,
            Notification.created_at >= datetime.now(timezone.utc) - timedelta(hours=1),
            Notification.metadata['from_user_id'].astext.cast(db.Integer) == user_id
        ).count()
        
        if recent_count >= 10:
            return False, "Rate limit exceeded. Max 10 messages per hour"
        
        try:
            notification = Notification(
                user_id=downline_id,
                message=message,
                notification_type='downline_message',
                is_read=False,
                created_at=datetime.now(timezone.utc)
            )
            # Add metadata if your Notification model supports JSON
            if hasattr(notification, 'metadata'):
                notification.metadata = {
                    'from_user_id': user_id,
                    'message_type': message_type,
                    'sender_username': User.query.get(user_id).username
                }
            
            db.session.add(notification)
            
            # Log activity
            audit = AuditLog(
                actor_id=user_id,
                action='send_downline_message',
                ip_address=None  # Will be set from request
            )
            db.session.add(audit)
            
            db.session.commit()
            return True, "Message sent successfully"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to send message: {e}")
            return False, f"Failed to send: {str(e)}"
    
    @staticmethod
    def get_message_templates() -> List[Dict]:
        """Get predefined message templates"""
        return [
            {
                'type': 'welcome',
                'title': 'Welcome to the team! 🎉',
                'message': "Welcome to our network! I'm here to help you succeed. Let me know if you have any questions about getting started.",
                'icon': '👋'
            },
            {
                'type': 'investment_reminder',
                'title': 'Ready to start earning? 💰',
                'message': "Hi! I noticed you haven't made your first investment yet. The Bronze package starts at just UGX 10,000 and gives you 5% daily returns. Let me show you how!",
                'icon': '💎'
            },
            {
                'type': 'training',
                'title': 'Free training available 📚',
                'message': "I'm hosting a training session on how to maximize your earnings. Would you like to join? Let me know and I'll send you the details!",
                'icon': '🎓'
            },
            {
                'type': 'congratulation',
                'title': 'Congratulations! 🏆',
                'message': "Congratulations on your recent investment! You're on your way to financial freedom. Keep up the great work!",
                'icon': '🎊'
            },
            {
                'type': 'referral_encouragement',
                'title': 'Share the opportunity 🤝',
                'message': "You've started your journey! Now it's time to share this opportunity with friends and family. Every person you refer earns you commissions. Let me help you get started!",
                'icon': '👥'
            }
        ]


class NetworkAnalytics:
    """Network analytics and insights"""
    
    @staticmethod
    def get_network_growth(user_id: int, days: int = 30) -> Dict:
        """Get network growth over time"""
        
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Daily growth from NetworkSnapshot
        snapshots = NetworkSnapshot.query.filter(
            NetworkSnapshot.user_id == user_id,
            NetworkSnapshot.snapshot_date >= start_date.date()
        ).order_by(NetworkSnapshot.snapshot_date).all()
        
        growth_data = []
        for snapshot in snapshots:
            growth_data.append({
                'date': snapshot.snapshot_date.isoformat(),
                'total_downline': snapshot.total_downline,
                'active_downline': snapshot.active_downline,
                'new_members': snapshot.direct_referrals,  # New that day
                'total_investment': float(snapshot.network_investment)
            })
           # ========== FIX: Add this safety check ==========
        if not growth_data:
            return {
                'history': [],
                'growth_rate': 0.0,
                'projected_30_days': 0,
                'avg_daily_growth': 0.0
            }
    # ===============================================
        # Calculate growth rate
        if len(growth_data) >= 2:
            first = growth_data[0]['total_downline']
            last = growth_data[-1]['total_downline']
            growth_rate = ((last - first) / first * 100) if first > 0 else 0
        else:
            growth_rate = 0
        
        # Project next 30 days (simple linear projection)
        avg_daily_growth = (growth_data[-1]['total_downline'] - growth_data[0]['total_downline']) / days if days > 0 else 0
        projected = growth_data[-1]['total_downline'] + (avg_daily_growth * 30)
        
        return {
            'history': growth_data,
            'growth_rate': round(growth_rate, 2),
            'projected_30_days': max(0, round(projected)),
            'avg_daily_growth': round(avg_daily_growth, 2)
        }
    
    @staticmethod
    def get_top_performers(user_id: int, limit: int = 10) -> List[Dict]:
        """Get top performing downline members"""
        
        top_performers = db.session.query(
            User.id,
            User.username,
            User.is_active,
            func.coalesce(func.sum(Package.package_amount), 0).label('total_investment'),
            func.count(Package.id).label('package_count'),
            func.coalesce(func.sum(ReferralBonus.bonus_amount), 0).label('earned_commission'),
            func.count(Referral.id).label('referrals_made')
        ).join(
            ReferralNetwork, ReferralNetwork.descendant_id == User.id
        ).outerjoin(
            Package, and_(
                Package.user_id == User.id,
                Package.status == 'active'
            )
        ).outerjoin(
            ReferralBonus, and_(
                ReferralBonus.referrer_id == User.id,
                ReferralBonus.status == 'paid'
            )
        ).outerjoin(
            Referral, Referral.referrer_id == User.id
        ).filter(
            ReferralNetwork.ancestor_id == user_id
        ).group_by(User.id).order_by(
            desc(func.coalesce(func.sum(Package.package_amount), 0))
        ).limit(limit).all()
        
        return [
            {
                'user_id': p.id,
                'username': p.username,
                'is_active': p.is_active,
                'total_investment': float(p.total_investment or 0),
                'package_count': p.package_count or 0,
                'earned_commission': float(p.earned_commission or 0),
                'referrals_made': p.referrals_made or 0
            }
            for p in top_performers
        ]
    
    @staticmethod
    def get_investment_trends(user_id: int) -> Dict:
        """Analyze investment patterns in downline"""
        
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        # Investments by level
        investments_by_level = db.session.query(
            ReferralNetwork.depth,
            func.count(Package.id).label('investment_count'),
            func.sum(Package.package_amount).label('total_amount')
        ).join(
            Package, Package.user_id == ReferralNetwork.descendant_id
        ).filter(
            ReferralNetwork.ancestor_id == user_id,
            Package.created_at >= thirty_days_ago,
            Package.status == 'active'
        ).group_by(ReferralNetwork.depth).order_by(ReferralNetwork.depth).all()
        
        return {
            'investments_by_level': [
                {
                    'level': row.depth,
                    'count': row.investment_count,
                    'total': float(row.total_amount or 0)
                }
                for row in investments_by_level
            ],
            'total_investments_30d': sum(row.investment_count for row in investments_by_level),
            'total_value_30d': float(sum(row.total_amount or 0 for row in investments_by_level))
        }


# Helper for SQL CASE statement
def case(whens, else_=None):
    """Simple case statement builder"""
    from sqlalchemy import case as sa_case
    return sa_case(whens, else_=else_)