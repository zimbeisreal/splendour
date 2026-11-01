# utils/payment_processor.py
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Tuple, Dict, Any, Optional
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from models import Payment, PackageCatalog, Package, User, ReferralBonus, Notification, Transaction 
from bonus.validation import BonusValidationHelper
from bonus.bonus_calculation import BonusCalculationHelper

import uuid

logger = logging.getLogger(__name__)

class PaymentProcessorError(Exception):
    """Custom exception for payment processing errors"""
    pass

def safe_rollback():
    """Safely rollback database transaction"""
    try:
        if db.session.is_active:
            db.session.rollback()
            logger.debug("Transaction rolled back")
    except Exception as e:
        logger.error(f"Rollback failed: {e}")

def create_notification(user_id: int, message: str, notification_type: str = 'bonus') -> bool:
    """Create notification with proper error handling"""
    from models import Notification
    from datetime import datetime

    try:
        notification = Notification(
            user_id=user_id,
            message=message,
            notification_type=notification_type,
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        logger.debug(f"Notification created for user {user_id}")
        db.session.commit()
        return True
    except Exception as e:
        logger.warning(f"Notification creation failed: {e}")
        return False       

def validate_purchase(payment: Payment) -> Tuple[Optional[PackageCatalog], Optional[User]]:
    """Validate payment and return package and user"""
    # Validate payment amount
    if not payment or not payment.amount or payment.amount <= 0:
        logger.error(f"Invalid payment: {payment.id if payment else 'None'}")
        return None, None
    
    # Get or fix package catalog
    if not payment.package_catalog_id:
        package_catalog = PackageCatalog.query.filter_by(amount=payment.amount).first()
        if not package_catalog:
            logger.error(f"No package found for amount {payment.amount}")
            return None, None
        payment.package_catalog_id = package_catalog.id
        db.session.commit()
        logger.info(f"Fixed package_catalog_id: {package_catalog.id}")
    else:
        package_catalog = PackageCatalog.query.get(payment.package_catalog_id)
    
    if not package_catalog:
        logger.error(f"Package catalog not found for payment {payment.id}")
        return None, None
    
    # Validate user
    if not payment.user_id:
        logger.error(f"Payment {payment.id} has no user_id")
        return None, None
    
    user = User.query.get(payment.user_id)
    if not user:
        logger.error(f"User {payment.user_id} not found")
        return None, None
    
    logger.info(f"Validated purchase: User {user.id}, Package {package_catalog.name}")
    return package_catalog, user

# def has_existing_bonuses(payment: Payment) -> bool:
#     """Check if bonuses already processed for this payment"""
#     existing_count = ReferralBonus.query.filter_by(payment_id=payment.id).count()
#     if existing_count > 0:
#         logger.warning(f"Payment {payment.id} already has {existing_count} bonuses")
#         return True
#     return False

def has_existing_bonuses(payment: Payment) -> bool:
    """
    Check if bonuses already processed for this payment.

    Retries once on a stale/broken DB connection so a transient
    pg8000 socket error doesn't get misreported as "no bonuses".
    """
    from sqlalchemy.exc import DBAPIError, OperationalError

    for attempt in range(2):
        try:
            existing_count = (
                ReferralBonus.query
                .filter_by(payment_id=payment.id)
                .count()
            )
            if existing_count > 0:
                logger.warning(
                    f"Payment {payment.id} already has {existing_count} bonuses"
                )
                return True
            return False
        except (DBAPIError, OperationalError) as e:
            # Stale connection — drop it from the pool and retry once
            logger.warning(
                f"has_existing_bonuses: DB error on attempt {attempt + 1} "
                f"for payment {payment.id}: {e}"
            )
            try:
                db.session.rollback()
                db.session.remove()   # evicts broken connection from pool
            except Exception:
                pass
            if attempt == 1:
                raise                 # second failure = real problem, surface it
    return False  # unreachable, but keeps linters happy

# utils/payment_processor.py — REPLACE the existing create_user_package

def create_user_package(user: User, package_catalog: PackageCatalog):
    """
    Thin wrapper — delegates to the ONE canonical implementation in
    blueprints.payments_helpers so package fields (package_amount,
    package, type) are always populated correctly.
    
    Idempotent: if an active package already exists for this user+catalog,
    returns it instead of creating a duplicate.
    """
    existing = Package.query.filter_by(
        user_id=user.id,
        catalog_id=package_catalog.id,
        status='active',
    ).first()
    if existing:
        logger.info(
            f"Using existing package id={existing.id} for user {user.id} "
            f"/ catalog {package_catalog.id}"
        )
        return existing

    # Import locally to avoid circular import at module load
    from blueprints.payments_helpers import create_user_package as _canonical
    return _canonical(user=user, package_catalog=package_catalog, lock_details=None)

def credit_bonus_safely(bonus_id: int, amount: Decimal) -> bool:
    """TEMPORARILY DISABLED - Use BonusPaymentHelper instead"""
    logger.warning(f"credit_bonus_safely is deprecated. Bonus {bonus_id} not credited here.")
    return True

def send_purchase_notifications(user: User, package_catalog: PackageCatalog, credited_count: int):
    """Send all relevant notifications"""
    # Notify purchasing user
    package_name = package_catalog.name
    message = f"Your {package_name} package has been activated!"
    create_notification(user.id, message, 'purchase_confirmation')
    
    if credited_count > 0:
        bonus_message = f"You earned Today! Check Balances!"
        create_notification(user.id, bonus_message, 'bonus_earning')
    
    # Notify referrer if exists
    if user.referred_by:
        referrer_message = f"Your referral  purchased Invested !"
        create_notification(user.referred_by, referrer_message, 'referral_earning')

def process_referral_bonuses(payment: Payment, user: User, package_catalog: PackageCatalog) -> Dict[str, Any]:
    """Process all referral bonuses for this purchase"""
    result = {
        'credited_count': 0,
        'total_amount': Decimal('0'),
        'bonus_ids': []
    }
    
    # Validate processing eligibility
    can_process, process_message, validation_result = BonusValidationHelper.can_process_bonuses(payment.id)
    if not can_process:
        logger.warning(f"Bonus processing skipped: {process_message}")
        BonusValidationHelper.cleanup_processing_flag(payment.id, success=False)
        return result
    
    # Calculate bonuses
    success, bonus_calculations, calc_message, audit_info = BonusCalculationHelper.calculate_all_bonuses_secure(payment)
    if not success or not bonus_calculations:
        logger.error(f"Bonus calculation failed: {calc_message}")
        BonusValidationHelper.cleanup_processing_flag(payment.id, success=False)
        return result
    
    logger.info(f"Calculated {len(bonus_calculations)} potential bonuses")
    
    # Validate bonuses
    valid_bonuses, invalid_bonuses, batch_validation = BonusValidationHelper.validate_bonus_batch(bonus_calculations)
    logger.info(f"Valid: {len(valid_bonuses)}, Invalid: {len(invalid_bonuses)}")
    
    if not valid_bonuses:
        logger.info("No valid bonuses to create")
        BonusValidationHelper.cleanup_processing_flag(payment.id, success=False)
        create_notification(user.id, 
            f"📦 Your {package_catalog.name} package is active. Invite friends to earn bonuses!",
            'info')
        return result
    
    # Store bonuses
    direct_referrer_id = user.referred_by if user else None
    
    for bonus_data in valid_bonuses:
        try:
            # Prepare bonus data
            bonus_data['payment_id'] = bonus_data.pop('purchase_id', None)
            bonus_data['referrer_id'] = bonus_data.get('referrer_id') or direct_referrer_id
            bonus_data['referred_id'] = bonus_data.get('referred_id') or payment.user_id
            bonus_data['type'] = bonus_data.get('type', 'referral_bonus')
            
            # Ensure amount is Decimal
            raw_amount = bonus_data.get('bonus_amount') or bonus_data.get('amount', 0)
            bonus_amount = Decimal(str(raw_amount)) if raw_amount else Decimal('0')
            bonus_data['bonus_amount'] = bonus_amount
            bonus_data.pop('amount', None)
            
            # Create bonus
            bonus = ReferralBonus(**bonus_data)
            db.session.add(bonus)
            db.session.flush()
            
            result['bonus_ids'].append(bonus.id)
            result['total_amount'] += bonus_amount
            
            logger.debug(f"Created bonus {bonus.id} for user {bonus.user_id}")
            
        except Exception as e:
            logger.error(f"Failed to create bonus record: {e}", exc_info=True)
            continue
    
    # Commit all bonuses
    try:
        db.session.commit()
        logger.info(f"Committed {len(result['bonus_ids'])} bonuses")
    except SQLAlchemyError as e:
        logger.error(f"Failed to commit bonuses: {e}")
        safe_rollback()
        return result
    
    # Credit wallets
    for bonus_id in result['bonus_ids']:
        from bonus.bonus_payment import BonusPaymentHelper
        bonus = db.session.get(ReferralBonus, bonus_id)
        if bonus:
            success, msg, txn_id = BonusPaymentHelper._credit_user_wallet_atomic(
                user_id=bonus.referrer_id,
                amount=bonus.bonus_amount,
                bonus_id=bonus.id)
            if success:
                result['credited_count'] += 1
                bonus.status = 'paid'
                bonus.is_paid_out = True
                bonus.paid_out_at = datetime.now(timezone.utc)
                db.session.add(bonus)
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        logger.error(f"Failed to commit status updates: {e}")
        safe_rollback()        
    
    # Clean up processing flag on success
    if result['credited_count'] > 0:
        BonusValidationHelper.cleanup_processing_flag(payment.id, success=True)
    
    return result
# utils/payment_processor.py — REPLACE process_package_purchase

def process_package_purchase(payment: Payment) -> Tuple[bool, str]:
    """
    Process a package purchase:
      - welcome bonus (idempotent)
      - referral bonuses
      - notifications
    Does NOT create the Package — the webhook handler (handle_collection_webhook)
    already created it via blueprints.payments_helpers.create_user_package.
    """
    logger.info(f"Starting package processing for payment {payment.id}")
    
    try:
        # 1. Validate purchase
        package_catalog, user = validate_purchase(payment)
        if not package_catalog or not user:
            return False, "Purchase validation failed"
        
        # 2. Duplicate guard
        if has_existing_bonuses(payment):
            return True, "Already processed"
        
        # 3. Welcome bonus (skip for 1-Day 30K)
        if package_catalog.name == "1-Day 30K":
            logger.info(
                f"Welcome bonus skipped: 1-Day 30K package "
                f"(user {user.id}, payment {payment.id})"
            )
        else:
            credited, msg, amt = credit_welcome_bonus_if_first_purchase(user, payment=payment)
            logger.info(f"Welcome bonus {'applied' if credited else 'skipped'}: {msg}")
        
        # 4. Referral bonuses (uses its own savepoints internally)
        bonus_result = process_referral_bonuses(payment, user, package_catalog)
        
        # 5. Ensure the package exists — but DO NOT create a second one.
        #    The canonical create_user_package (helpers) is idempotent now.
        user_package = Package.query.filter_by(
            user_id=user.id,
            catalog_id=package_catalog.id,
            status='active',
        ).order_by(Package.id.desc()).first()
        
        if not user_package:
            # Very rare: webhook created it but in a prior failed tx.
            # Delegate to the canonical helper to recreate it correctly.
            from blueprints.payments_helpers import create_user_package as _canonical
            user_package = _canonical(
                user=user,
                package_catalog=package_catalog,
                lock_details=None,
            )
            logger.info(f"Recreated package id={user_package.id} via canonical helper")
        else:
            logger.info(f"Package id={user_package.id} already exists — no duplicate created")
        
        # 6. Notifications
        send_purchase_notifications(user, package_catalog, bonus_result['credited_count'])
        
        # 7. Commit everything atomically
        db.session.commit()
        
        msg = (
            f"Successfully processed {bonus_result['credited_count']} bonuses "
            f"totaling {bonus_result['total_amount']}"
        )
        logger.info(msg)
        return True, msg
    
    except Exception as e:
        db.session.rollback()      # ← always rollback first
        logger.exception(
            f"Package purchase processing failed for payment "
            f"{payment.id if payment else 'None'}"
        )
        return False, f"Processing error: {str(e)}"


# Config — tune to taste
WELCOME_BONUS_AMOUNT = Decimal("0000")   # UGX
WELCOME_BONUS_TYPE = "welcome_bonus"
WELCOME_BONUS_REF_PREFIX = "WB"


# utils/payment_processor.py — REPLACE credit_welcome_bonus_if_first_purchase

def credit_welcome_bonus_if_first_purchase(user: User, payment=None) -> tuple[bool, str, Decimal]:
    """
    Credit a one-time welcome bonus to user.actual_balance if the user has
    never received one before. Idempotent — safe to call multiple times.
    Returns (credited, message, amount).
    """
    if not user:
        return False, "No user", Decimal("0")
    
    already = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.type == WELCOME_BONUS_TYPE,
        Transaction.status == "completed",
    ).first()
    
    if already:
        return False, "Welcome bonus already credited", Decimal("0")
    
    amount = WELCOME_BONUS_AMOUNT
    
    try:
        # ✅ 1. Ensure wallet exists FIRST
        from models import Wallet
        wallet = Wallet.query.filter_by(user_id=user.id).first()
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=Decimal("0"))
            db.session.add(wallet)
            db.session.flush()   # gives wallet.id for the Transaction FK
        
        # ✅ 2. Credit actual balance
        user.actual_balance = Decimal(str(user.actual_balance or 0)) + amount
        db.session.add(user)
        
        # ✅ 3. Insert Transaction with wallet_id + real datetime
        txn = Transaction(
            user_id=user.id,
            wallet_id=wallet.id,                                    # ← was missing
            amount=amount,
            type=WELCOME_BONUS_TYPE,
            status="completed",
            reference=f"{WELCOME_BONUS_REF_PREFIX}-{uuid.uuid4().hex[:12].upper()}",
            purchase_type="Welcome bonus for first package purchase",
            created_at=datetime.now(timezone.utc),                  # ← was .isoformat()
        )
        db.session.add(txn)
        
        # ✅ 4. Notification — do NOT commit here, caller owns the tx
        notification = Notification(
            user_id=user.id,
         message=(
    f"SKYLINE · Welcome bonus credited\n"
    f"Amount:   UGX {amount:,.0f}\n"
    f"Reason:   First position opened\n"
    f"Status:   Available"
),
            notification_type="welcome_bonus",
            is_read=False,
        )
        db.session.add(notification)
        
        # ✅ 5. Flush to catch any constraint violations NOW, not later
        db.session.flush()
        
        logger.info(
            f"✅ Welcome bonus UGX {amount} credited to user {user.id} "
            f"(payment {payment.id if payment else 'n/a'})"
        )
        return True, f"Welcome bonus UGX {amount:,.0f} credited", amount
    
    except Exception as e:
        logger.error(
            f"Failed to credit welcome bonus to user {user.id}: {e}",
            exc_info=True,
        )
        db.session.rollback()   # ← critical
        return False, f"Welcome bonus failed: {e}", Decimal("0")