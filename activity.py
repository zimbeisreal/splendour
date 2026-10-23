from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.orm import joinedload
import math
import traceback

activity_bp = Blueprint('activity', __name__)

def safe_float_convert(value, default=0.0):
    """Safely convert value to float"""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def safe_isoformat(dt_value):
    """Safely convert datetime to ISO format"""
    try:
        if dt_value:
            return dt_value.isoformat()
        return None
    except Exception:
        return None

def map_transaction_to_activity(transaction):
    """Map Transaction model to activity format with error handling"""
    try:
        type_mapping = {
            'deposit': 'deposit',
            'withdrawal': 'withdraw', 
            'bonus': 'bonus',
            'referral': 'bonus',
            'package': 'deposit'
        }
        
        title_mapping = {
            'deposit': 'Funds Deposit',
            'withdrawal': 'Withdrawal',
            'bonus': 'Bonus Credit', 
            'referral': 'Referral Bonus',
            'package': 'Package Investment'
        }
        
        transaction_type = getattr(transaction, 'type', 'deposit')
        activity_type = type_mapping.get(transaction_type, 'deposit')
        title = title_mapping.get(transaction_type, 'Transaction')
        
        return {
            'type': activity_type,
            'title': title,
            'timestamp': safe_isoformat(getattr(transaction, 'created_at', None)),
            'amount': safe_float_convert(getattr(transaction, 'amount', 0)),
            'currency': 'UGX',
            'source': 'transaction',
            'id': getattr(transaction, 'id', None)
        }
    except Exception as e:
        current_app.logger.error(f"Error mapping transaction: {str(e)}")
        return None

def map_payment_to_activity(payment):
    """Map Payment model to activity format with error handling"""
    try:
        payment_type = getattr(payment, 'payment_type', 'package')
        
        if payment_type == 'package':
            activity_type = 'deposit'
            package_catalog = getattr(payment, 'package_catalog', None)
            package_name = getattr(package_catalog, 'name', 'Investment') if package_catalog else "Investment"
            title = f'Package Purchase - {package_name}'
        else:
            activity_type = 'deposit'
            title = 'Payment Deposit'
        
        return {
            'type': activity_type,
            'title': title,
            'timestamp': safe_isoformat(getattr(payment, 'created_at', None)),
            'amount': safe_float_convert(getattr(payment, 'amount', 0)),
            'currency': getattr(payment, 'currency', 'UGX'),
            'source': 'payment',
            'id': getattr(payment, 'id', None)
        }
    except Exception as e:
        current_app.logger.error(f"Error mapping payment: {str(e)}")
        return None

def map_withdrawal_to_activity(withdrawal):
    """Map Withdrawal model to activity format with error handling"""
    try:
        return {
            'type': 'withdraw',
            'title': 'Withdrawal Request',
            'timestamp': safe_isoformat(getattr(withdrawal, 'created_at', None)),
            'amount': safe_float_convert(getattr(withdrawal, 'amount', 0)),
            'currency': 'UGX',
            'source': 'withdrawal',
            'id': getattr(withdrawal, 'id', None)
        }
    except Exception as e:
        current_app.logger.error(f"Error mapping withdrawal: {str(e)}")
        return None

def map_bonus_to_activity(bonus):
    """Map Bonus model to activity format with error handling"""
    try:
        bonus_type = getattr(bonus, 'type', '')
        title = f'{bonus_type.title()} Bonus' if bonus_type else 'Bonus'
        
        return {
            'type': 'bonus',
            'title': title,
            'timestamp': safe_isoformat(getattr(bonus, 'created_at', None)),
            'amount': safe_float_convert(getattr(bonus, 'amount', 0)),
            'currency': 'UGX',
            'source': 'bonus',
            'id': getattr(bonus, 'id', None)
        }
    except Exception as e:
        current_app.logger.error(f"Error mapping bonus: {str(e)}")
        return None

def map_referral_bonus_to_activity(referral_bonus):
    """Map ReferralBonus model to activity format with error handling"""
    try:
        level = getattr(referral_bonus, 'level', None)
        level_text = f" (Level {level})" if level else ""
        
        # Use bonus_amount as primary, fallback to amount
        bonus_amount = getattr(referral_bonus, 'bonus_amount', None)
        if bonus_amount is None:
            bonus_amount = getattr(referral_bonus, 'amount', 0)
        
        return {
            'type': 'bonus',
            'title': f'Referral Bonus{level_text}',
            'timestamp': safe_isoformat(getattr(referral_bonus, 'created_at', None)),
            'amount': safe_float_convert(bonus_amount),
            'currency': 'UGX',
            'source': 'referral_bonus',
            'id': getattr(referral_bonus, 'id', None)
        }
    except Exception as e:
        current_app.logger.error(f"Error mapping referral bonus: {str(e)}")
        return None

def safe_query_execution(query, limit=100):
    """Safely execute database query with error handling"""
    try:
        return query.limit(limit).all()
    except Exception as e:
        current_app.logger.error(f"Database query error: {str(e)}")
        return []

@activity_bp.route('/api/recent_activity', methods=['GET'])
def get_recent_activity():
    """
    Get recent activities for ALL users (general activity feed)
    """
    print("GENERAL RECENT ACTIVITY ENDPOINT HIT")
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 
                                   current_app.config.get('DEFAULT_PAGE_SIZE', 20), 
                                   type=int)
        
        # Validate pagination
        if page < 1:
            return jsonify({'error': 'Page must be greater than 0'}), 400
            
        max_page_size = current_app.config.get('MAX_PAGE_SIZE', 100)
        if page_size < 1 or page_size > max_page_size:
            return jsonify({
                'error': f'Page size must be between 1 and {max_page_size}'
            }), 400
        
        offset = (page - 1) * page_size
        
        # Import models inside try block to catch import errors
        try:
            from models import Transaction, Payment, Withdrawal, Bonus, ReferralBonus, db
        except ImportError as e:
            current_app.logger.error(f"Model import error: {str(e)}")
            return jsonify({'error': 'Internal server error - model import failed'}), 500
        
        all_activities = []
        
        # 1. Get all transactions with eager loading
        try:
            transactions_query = Transaction.query.filter(
                Transaction.type.in_(['deposit', 'withdrawal', 'bonus', 'referral', 'package'])
            ).order_by(Transaction.created_at.desc())
            
            transactions = safe_query_execution(transactions_query, 100)
            
            for transaction in transactions:
                activity = map_transaction_to_activity(transaction)
                if activity:
                    all_activities.append(activity)
                    
        except Exception as e:
            current_app.logger.error(f"Transaction processing error: {str(e)}")
        
        # 2. Get all payments with eager loading
        try:
            payments_query = Payment.query.options(
                joinedload(Payment.package_catalog)
            ).filter(
                Payment.status.in_(['completed'])
            ).order_by(Payment.created_at.desc())
            
            payments = safe_query_execution(payments_query, 100)
            
            for payment in payments:
                activity = map_payment_to_activity(payment)
                if activity:
                    all_activities.append(activity)
                    
        except Exception as e:
            current_app.logger.error(f"Payment processing error: {str(e)}")
        
        # 3. Get all withdrawals
        try:
            withdrawals_query = Withdrawal.query.filter(
                Withdrawal.status.in_(['completed', 'pending'])
            ).order_by(Withdrawal.created_at.desc())
            
            withdrawals = safe_query_execution(withdrawals_query, 100)
            
            for withdrawal in withdrawals:
                activity = map_withdrawal_to_activity(withdrawal)
                if activity:
                    all_activities.append(activity)
                    
        except Exception as e:
            current_app.logger.error(f"Withdrawal processing error: {str(e)}")
        
        # 4. Get all bonuses
        try:
            bonuses_query = Bonus.query.filter(
                Bonus.status.in_(['active', 'paid'])
            ).order_by(Bonus.created_at.desc())
            
            bonuses = safe_query_execution(bonuses_query, 100)
            
            for bonus in bonuses:
                activity = map_bonus_to_activity(bonus)
                if activity:
                    all_activities.append(activity)
                    
        except Exception as e:
            current_app.logger.error(f"Bonus processing error: {str(e)}")
        
        # 5. Get all referral bonuses
        try:
            referral_bonuses_query = ReferralBonus.query.filter(
                ReferralBonus.status.in_(['active', 'paid'])
            ).order_by(ReferralBonus.created_at.desc())
            
            referral_bonuses = safe_query_execution(referral_bonuses_query, 100)
            
            for referral_bonus in referral_bonuses:
                activity = map_referral_bonus_to_activity(referral_bonus)
                if activity:
                    all_activities.append(activity)
                    
        except Exception as e:
            current_app.logger.error(f"Referral bonus processing error: {str(e)}")
        
        # Sort by timestamp with error handling
        try:
            all_activities.sort(key=lambda x: x.get('timestamp', '') or '', reverse=True)
        except Exception as e:
            current_app.logger.error(f"Sorting error: {str(e)}")
            # Continue with unsorted data rather than failing
        
        # Apply pagination
        total_items = len(all_activities)
        start_idx = min(offset, total_items)
        end_idx = min(offset + page_size, total_items)
        paginated_activities = all_activities[start_idx:end_idx]
        
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 0
        
        response = {
            'activities': paginated_activities,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
        
        print(f"Successfully returning {len(paginated_activities)} activities out of {total_items} total")
        return jsonify(response)
        
    except Exception as e:
        current_app.logger.error(f"Critical error in recent_activity: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error processing request'}), 500

@activity_bp.route('/api/recent_activity/user', methods=['GET'])
def get_user_recent_activity():
    """
    Get recent activities for a SPECIFIC user
    """
    #print(f"USER RECENT ACTIVITY ENDPOINT HIT for user_id: {user_id}")
    try:
        from flask import session
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "not logged in"})
        #return get_user_recent_activity(user_id)
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 
                                   current_app.config.get('DEFAULT_PAGE_SIZE', 20), 
                                   type=int)
        
        # Validate pagination
        if page < 1:
            return jsonify({'error': 'Page must be greater than 0'}), 400
            
        max_page_size = current_app.config.get('MAX_PAGE_SIZE', 100)
        if page_size < 1 or page_size > max_page_size:
            return jsonify({
                'error': f'Page size must be between 1 and {max_page_size}'
            }), 400
        
        offset = (page - 1) * page_size
        
        # Import models
        try:
            from models import Transaction, Payment, Withdrawal, Bonus, ReferralBonus, Wallet, db
        except ImportError as e:
            current_app.logger.error(f"Model import error: {str(e)}")
            return jsonify({'error': 'Internal server error - model import failed'}), 500
        
        all_activities = []
        
        # 1. Get user's wallet transactions
        try:
            user_wallet = Wallet.query.filter_by(user_id=user_id).first()
            if user_wallet:
                transactions_query = Transaction.query.filter_by(wallet_id=user_wallet.id).filter(
                    Transaction.type.in_(['deposit', 'withdrawal', 'bonus', 'referral', 'package'])
                ).order_by(Transaction.created_at.desc())
                
                transactions = safe_query_execution(transactions_query, 100)
                
                for transaction in transactions:
                    activity = map_transaction_to_activity(transaction)
                    if activity:
                        all_activities.append(activity)
        except Exception as e:
            current_app.logger.error(f"User transaction processing error: {str(e)}")
        
     
        try:
            payments_query = Payment.query.filter_by(user_id=user_id).filter(
                Payment.status.in_(['completed'])
            ).order_by(Payment.created_at.desc())
            
            payments = safe_query_execution(payments_query, 100)
            
            for payment in payments:
                activity = map_payment_to_activity(payment)
                if activity:
                    all_activities.append(activity)
        except Exception as e:
            current_app.logger.error(f"User payment processing error: {str(e)}")
        
        # 3. Get user's withdrawals
        try:
            withdrawals_query = Withdrawal.query.filter_by(user_id=user_id).filter(
                Withdrawal.status.in_(['completed', 'pending', 'processed'])
            ).order_by(Withdrawal.created_at.desc())
            
            withdrawals = safe_query_execution(withdrawals_query, 100)
            
            for withdrawal in withdrawals:
                activity = map_withdrawal_to_activity(withdrawal)
                if activity:
                    all_activities.append(activity)
        except Exception as e:
            current_app.logger.error(f"User withdrawal processing error: {str(e)}")
        
        # 4. Get user's bonuses
        try:
            bonuses_query = Bonus.query.filter_by(user_id=user_id).filter(
                Bonus.status.in_(['active', 'paid'])
            ).order_by(Bonus.created_at.desc())
            
            bonuses = safe_query_execution(bonuses_query, 100)
            
            for bonus in bonuses:
                activity = map_bonus_to_activity(bonus)
                if activity:
                    all_activities.append(activity)
        except Exception as e:
            current_app.logger.error(f"User bonus processing error: {str(e)}")
        
        # 5. Get user's referral bonuses
        try:
            referral_bonuses_query = ReferralBonus.query.filter_by(user_id=user_id).filter(
                ReferralBonus.status.in_(['active', 'paid'])
            ).order_by(ReferralBonus.created_at.desc())
            
            referral_bonuses = safe_query_execution(referral_bonuses_query, 100)
            
            for referral_bonus in referral_bonuses:
                activity = map_referral_bonus_to_activity(referral_bonus)
                if activity:
                    all_activities.append(activity)
        except Exception as e:
            current_app.logger.error(f"User referral bonus processing error: {str(e)}")
        
        # Sort by timestamp
        try:
            all_activities.sort(key=lambda x: x.get('timestamp', '') or '', reverse=True)
        except Exception as e:
            current_app.logger.error(f"User activity sorting error: {str(e)}")
        
        # Apply pagination
        total_items = len(all_activities)
        start_idx = min(offset, total_items)
        end_idx = min(offset + page_size, total_items)
        paginated_activities = all_activities[start_idx:end_idx]
        
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 0
        
        response = {
            'activities': paginated_activities,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
        
        print(f"Returning {len(paginated_activities)} activities for user {user_id}")
        return jsonify(response)
        
    except Exception as e:
        current_app.logger.error(f"Critical error in user recent_activity: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error processing user request'}), 500