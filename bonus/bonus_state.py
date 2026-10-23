from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from flask import current_app
from models import ReferralBonus, User, Payment
from extensions import db
from sqlalchemy import text

class BonusStateHelper:
    """Tracks bonus states, history, and reporting"""
    
    @staticmethod
    def get_user_bonus_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get comprehensive bonus history for a user
        """
        try:
            bonuses = ReferralBonus.query.filter_by(user_id=user_id).order_by(
                ReferralBonus.created_at.desc()
            ).limit(limit).all()
            
            history = []
            for bonus in bonuses:
                history.append({
                    'id': bonus.id,
                    'amount': float(bonus.amount),
                    'level': bonus.level,
                    'status': bonus.status,
                    'created_at': bonus.created_at.isoformat() if bonus.created_at else None,
                    'paid_at': bonus.paid_at.isoformat() if bonus.paid_at else None,
                 #   'purchase_id': bonus.payment_id,
                    'bonus_percentage': float(bonus.bonus_percentage) if bonus.bonus_percentage else 0,
                    'qualifying_amount': float(bonus.qualifying_amount) if bonus.qualifying_amount else 0,
                    'referred_user_id': getattr(bonus, 'referred_id', None)
                })
            
            return history
            
        except Exception as e:
            current_app.logger.error(f"Error getting bonus history for user {user_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_pending_bonuses(user_id: int = None) -> List[Dict[str, Any]]:
        """
        Get pending bonuses, optionally filtered by user
        """
        try:
            query = ReferralBonus.query.filter_by(status='pending')
            
            if user_id:
                query = query.filter_by(user_id=user_id)
            
            pending = query.order_by(ReferralBonus.created_at.asc()).all()
            
            result = []
            for bonus in pending:
                result.append({
                    'id': bonus.id,
                    'user_id': bonus.user_id,
                    'amount': float(bonus.amount),
                    'level': bonus.level,
                    'created_at': bonus.created_at.isoformat() if bonus.created_at else None,
                    'purchase_id': bonus.payment_id,
                    'referred_user': getattr(bonus, 'referred_user', {}).get('username', 'Unknown')
                })
            
            return result
            
        except Exception as e:
            current_app.logger.error(f"Error getting pending bonuses: {str(e)}")
            return []
    
    @staticmethod
    def get_total_paid_bonuses(user_id: int = None, days: int = None) -> Dict[str, Any]:
        """
        Get total paid bonuses with optional filters
        """
        try:
            query = ReferralBonus.query.filter_by(status='paid')
            
            if user_id:
                query = query.filter_by(user_id=user_id)
            
            if days:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
                query = query.filter(ReferralBonus.paid_at >= cutoff_date)
            
            paid_bonuses = query.all()
            
            total_amount = sum(Decimal(str(b.amount)) for b in paid_bonuses)
            bonus_count = len(paid_bonuses)
            
            # Level distribution
            level_distribution = {}
            for bonus in paid_bonuses:
                level = bonus.level
                level_distribution[level] = level_distribution.get(level, 0) + 1
            
            return {
                'total_amount': float(total_amount),
                'bonus_count': bonus_count,
                'average_bonus': float(total_amount / bonus_count) if bonus_count > 0 else 0,
                'level_distribution': level_distribution,
                'time_period_days': days
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting total paid bonuses: {str(e)}")
            return {'total_amount': 0, 'bonus_count': 0, 'average_bonus': 0, 'level_distribution': {}}
    
    @staticmethod
    def get_unpaid_bonus_by_purchase(purchase_id: int) -> List[Dict[str, Any]]:
        """
        Get unpaid bonuses for a specific purchase
        """
        try:
            unpaid_bonuses = ReferralBonus.query.filter_by(
                payment_id=purchase_id,
                status='pending'
            ).all()
            
            result = []
            for bonus in unpaid_bonuses:
                user = User.query.get(bonus.user_id)
                result.append({
                    'bonus_id': bonus.id,
                    'user_id': bonus.user_id,
                    'username': user.username if user else 'Unknown',
                    'level': bonus.level,
                    'amount': float(bonus.amount),
                    'bonus_percentage': float(bonus.bonus_percentage) if bonus.bonus_percentage else 0,
                    'created_at': bonus.created_at.isoformat() if bonus.created_at else None
                })
            
            return result
            
        except Exception as e:
            current_app.logger.error(f"Error getting unpaid bonuses for purchase {purchase_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_bonus_statistics(time_period_days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive bonus statistics
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_period_days)
            
            # Total bonuses
            total_bonuses = ReferralBonus.query.filter(
                ReferralBonus.created_at >= cutoff_date
            ).count()
            
            # Paid bonuses
            paid_bonuses = ReferralBonus.query.filter(
                ReferralBonus.status == 'paid',
                ReferralBonus.paid_at >= cutoff_date
            ).all()
            
            paid_amount = sum(Decimal(str(b.amount)) for b in paid_bonuses)
            
            # Pending bonuses
            pending_bonuses = ReferralBonus.query.filter(
                ReferralBonus.status == 'pending',
                ReferralBonus.created_at >= cutoff_date
            ).count()
            
            # Top earners
            top_earners_query = text("""
                SELECT user_id, SUM(amount) as total_earned, COUNT(*) as bonus_count
                FROM referral_bonuses
                WHERE status = 'paid' AND paid_at >= :cutoff_date
                GROUP BY user_id
                ORDER BY total_earned DESC
                LIMIT 10
            """)
            
            top_earners_result = db.session.execute(top_earners_query, {'cutoff_date': cutoff_date})
            top_earners = []
            
            for row in top_earners_result:
                user = User.query.get(row.user_id)
                top_earners.append({
                    'user_id': row.user_id,
                    'username': user.username if user else 'Unknown',
                    'total_earned': float(row.total_earned),
                    'bonus_count': row.bonus_count
                })
            
            return {
                'time_period_days': time_period_days,
                'total_bonuses': total_bonuses,
                'paid_bonuses': len(paid_bonuses),
                'paid_amount': float(paid_amount),
                'pending_bonuses': pending_bonuses,
                'top_earners': top_earners,
                'average_bonus': float(paid_amount / len(paid_bonuses)) if paid_bonuses else 0
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting bonus statistics: {str(e)}")
            return {}
    
    @staticmethod
    def get_user_bonus_summary(user_id: int) -> Dict[str, Any]:
        """
        Get bonus summary for a specific user
        """
        try:
            all_bonuses = ReferralBonus.query.filter_by(user_id=user_id).all()
            
            paid_bonuses = [b for b in all_bonuses if b.status == 'paid']
            pending_bonuses = [b for b in all_bonuses if b.status == 'pending']
            
            total_earned = sum(Decimal(str(b.amount)) for b in paid_bonuses)
            pending_amount = sum(Decimal(str(b.amount)) for b in pending_bonuses)
            
            # Level performance
            level_performance = {}
            for bonus in paid_bonuses:
                level = bonus.level
                if level not in level_performance:
                    level_performance[level] = {
                        'count': 0,
                        'total_amount': Decimal('0'),
                        'average_amount': Decimal('0')
                    }
                
                level_performance[level]['count'] += 1
                level_performance[level]['total_amount'] += Decimal(str(bonus.amount))
            
            # Calculate averages
            for level, data in level_performance.items():
                data['average_amount'] = data['total_amount'] / data['count']
                # Convert to float for JSON serialization
                data['total_amount'] = float(data['total_amount'])
                data['average_amount'] = float(data['average_amount'])
            
            return {
                'user_id': user_id,
                'total_bonuses': len(all_bonuses),
                'paid_bonuses': len(paid_bonuses),
                'pending_bonuses': len(pending_bonuses),
                'total_earned': float(total_earned),
                'pending_amount': float(pending_amount),
                'level_performance': level_performance,
                'first_bonus_date': min([b.created_at for b in all_bonuses]).isoformat() if all_bonuses else None,
                'last_bonus_date': max([b.created_at for b in all_bonuses]).isoformat() if all_bonuses else None
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting user bonus summary for {user_id}: {str(e)}")
            return {'user_id': user_id, 'error': str(e)}