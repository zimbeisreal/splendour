# In your Flask application
from bonus.refferral_tree import ReferralTreeHelper
from bonus.bonus_config import BonusConfigHelper
from bonus.bonus_calculation import BonusCalculationHelper
from bonus.validation import BonusValidationHelper
from bonus.bonus_payment import BonusPaymentHelper
from bonus.audit_fraud import AuditFraudHelper
from bonus.bonus_state import BonusStateHelper
from models import Payment, ReferralBonus
from extensions import db

# Example 1: User signs up with referral
def handle_user_signup(user_id, referrer_id):
    success = ReferralTreeHelper.add_user_to_network(user_id, referrer_id)
    if success:
        return {"status": "success", "message": "User added to referral network"}
    else:
        return {"status": "error", "message": "Failed to add user to network"}

# Example 2: Process bonuses after successful purchase
def handle_successful_payment(payment_id):
    # Validate purchase
    is_valid, reason = BonusValidationHelper.validate_purchase(payment_id)
    if not is_valid:
        return {"status": "error", "message": reason}
    
    # Calculate bonuses
    purchase = Payment.query.get(payment_id)
    bonus_calculations = BonusCalculationHelper.calculate_all_bonuses(purchase)
    
    # Validate and create bonus records
    valid_bonuses, invalid_bonuses = BonusValidationHelper.validate_bonus_batch(bonus_calculations)
    
    # Store valid bonuses
    for bonus_data in valid_bonuses:
        bonus = ReferralBonus(**bonus_data)
        db.session.add(bonus)
    
    db.session.commit()
    
    # Queue for payment processing
    for bonus in valid_bonuses:
        BonusPaymentHelper.queue_bonus_payout(bonus['id'])
    
    return {
        "status": "success", 
        "bonuses_created": len(valid_bonuses),
        "invalid_bonuses": len(invalid_bonuses)
    }

# Example 3: Admin dashboard - get bonus statistics
def get_admin_bonus_report():
    stats = BonusStateHelper.get_bonus_statistics(30)  # Last 30 days
    fraud_audit = AuditFraudHelper.run_comprehensive_audit()
    
    return {
        "bonus_statistics": stats,
        "fraud_detection": fraud_audit,
        "pending_bonuses": BonusStateHelper.get_pending_bonuses()
    }

# Example 4: User bonus dashboard
def get_user_bonus_dashboard(user_id):
    history = BonusStateHelper.get_user_bonus_history(user_id, 20)
    summary = BonusStateHelper.get_user_bonus_summary(user_id)
    pending = BonusStateHelper.get_pending_bonuses(user_id)
    
    return {
        "bonus_history": history,
        "bonus_summary": summary,
        "pending_bonuses": pending
    }