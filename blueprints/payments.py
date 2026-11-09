# ======================================================================================================
#   PAYMENT API BLUEPRINT FOR MARZ PAYMENT GATEWAY INTEGRATION
#   express - With Locking Support
# =====================================================================================================

from flask import Blueprint, request, jsonify, current_app, session, url_for, redirect
import uuid
from models import Payment, PaymentStatus, User, Withdrawal, PackageCatalog, User, Package, Referral, Bonus, ReferralBonus
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session
import re
import json
from sqlalchemy import and_
import requests
from extensions import db
import os
from datetime import datetime, timedelta, timezone
import base64
import logging
import uuid
from decimal import Decimal
from blueprints.payments_helpers import express_PACKAGE_CATALOG
import sys
from flask import Blueprint, request, jsonify, session, Blueprint, current_app
from blueprints.payments_helpers import (
    validate_payment_input, 
    handle_existing_payment,
    create_payment_record, 
    send_to_pesajet,
    create_user_package,
    get_lock_bonus, send_payment, send_to_marzpay,
    calculate_locked_returns
)
from blueprints.withdraw_helpers import WithdrawalProcessor, WithdrawalException, WithdrawalQueryHelper, WithdrawalConfig, WithdrawalRecordManager
from blueprints.payments_helpers import check_package_funds_availability
from models import Transaction, Notification, WebhookEvent
from decimal import Decimal

import time
from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

import hmac, hashlib




bp = Blueprint("payments", __name__)
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


# =============================================================================================
#      PAYMENT INITIATION ENDPOINT - express ONLY
# =============================================================================================

@bp.route("/payments/initiate", methods=['POST'])
def initiate_payment():
    """Main payment initiation endpoint - express package purchases with locking support"""
    
    try:
        # 1. Authentication & Validation
        user = get_authenticated_user()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        print("=" * 60)
        print("📥 RECEIVED PAYMENT DATA:")
        print(json.dumps(data, indent=2))
        print("=" * 60)
        
        # 2. Validate input (includes lock validation)
        validated, error = validate_payment_input(data)
        if error:
            return error
        if validated["payment_type"] == 'deposit':
            return handle_deposit_payment(user, validated)
        # 3. Route to package payment handler only
        if validated["payment_type"] == "package":
            return handle_package_payment(user, validated)
        else:
            return jsonify({"error": "Invalid payment type. Only 'package' is supported."}), 400
            
    except KeyError as e:
        print(f"KeyError: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Missing required field: {e}"}), 400
    except Exception as e:
        db.session.rollback()
        print(f"Payment initiation error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Payment processing failed"}), 500


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_authenticated_user():
    """Get authenticated user from session"""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def user_has_any_package(user_id: int) -> bool:
    """Check if user has ever purchased any package"""
    from models import Package
    return Package.query.filter_by(user_id=user_id).first() is not None


# ============================================================
# PACKAGE PAYMENT HANDLER - WITH LOCKING SUPPORT
# ============================================================

def handle_package_payment(user, validated):
    """
    Buy a plan with the user's balance (actual balance + mature wallet). No phone, no mobile money here:
    if the balance is too low the frontend must send the user to Deposit first.
    """
    package_obj = validated.get("package_obj")
    if not package_obj:
        return jsonify({"error": "Package not found", "code": "PRODUCT_NOT_FOUND"}), 400

    required = Decimal(str(package_obj.amount))
    has_funds, funds_msg, total_available = check_package_funds_availability(user.id, required)
    if not has_funds:
        return jsonify({
            "error": "Not enough balance. Deposit first, then invest.",
            "code": "INSUFFICIENT_FUNDS",
            "required": float(required),
            "available": float(total_available),
            "shortfall": float(required - total_available),
        }), 402

    return process_internal_package_payment(
        user, package_obj,
        validated.get("lock_days", 0), validated.get("is_locking", False), validated.get("lock_details"),
    )


def handle_deposit_payment(user, validated):
    """Handle mobile money deposit"""
    amount = validated["amount"]
    phone = validated["phone"]
    
    # Check for existing payment
    existing = handle_existing_payment(user, amount, "deposit")
    if existing:
        return jsonify({
            "reference": existing.reference,
            "status":    existing.status,
            "payment_type": "deposit",
            "message":   "Deposit already pending. Check your phone.",
        }), 200    
       
    
    # Create payment record
    payment = create_payment_record(user, amount, phone, "deposit")
    if not payment:
        return jsonify({"error": "Failed to create payment record"}), 500
    
    # Call MarzPay mobile money API
    marz_data, error = send_to_pesajet(payment, phone, amount, package=None,
            lock_details=None)
    if error:
        payment.status = PaymentStatus.FAILED.value
        db.session.commit()
        return jsonify(error), 502
    
    db.session.commit()
    
    return jsonify({
        "reference": payment.reference,
        "status": payment.status,
        "payment_type": "deposit",
        "checkout_url": marz_data.get("pop_up_info"),
        "message": "Deposit initiated successfully"
    }), 200
# ============================================================
# INTERNAL PACKAGE PAYMENT - WITH LOCKING SUPPORT
# ============================================================
def process_internal_package_payment(user, package_obj, lock_days=0, is_locking=False, lock_details=None):
    """
    Process package purchase using internal account balance (actual + wallet)
    with locking support.
    """
    logging.info("=== PROCESSING INTERNAL PACKAGE PAYMENT ===")
    
    from models import Transaction, Notification
    from decimal import Decimal
    import uuid
    import json

    amount = Decimal(str(package_obj.amount))
    # Check for existing payment
    existing_payment = handle_existing_payment(user, package_obj.amount, "package")
    if existing_payment:
        print(f"⚠️ Existing payment found: {existing_payment.reference}")
        return jsonify({
            "reference": existing_payment.reference,
            "status": existing_payment.status,
            "note": "Idempotent: existing record returned"
        }), 200
    
    
    actual_balance = Decimal(str(user.actual_balance or 0))
    
    # ✅ DEBUG: Log what we're processing
    print(f"🔍 Internal Payment - User: {user.id}, Package: {package_obj.name}, Amount: {amount}")
    print(f"🔍 Locking: {is_locking}, Lock Days: {lock_days}")
    print(f"🔍 Lock Details: {lock_details}")
    
    # Start atomic transaction
    try:
        # Deduct from actual balance first
        deduct_from_actual = min(amount, actual_balance)
        if deduct_from_actual > 0:
            user.actual_balance -= deduct_from_actual
            print(f"💰 Deducted {deduct_from_actual} from actual balance")
        
        # Deduct remaining from wallet
        deduct_from_wallet = amount - deduct_from_actual
        if deduct_from_wallet > 0:
            wallet_tx = Transaction(
                user_id=user.id,
                wallet_id=user.wallet.id,
                amount=-deduct_from_wallet,
                type='package_purchase',
                status='completed',
                reference=str(uuid.uuid4())
            )
            db.session.add(wallet_tx)
            user.wallet.balance -= deduct_from_wallet
            print(f"💰 Deducted {deduct_from_wallet} from wallet balance")
        
        db.session.add(user)
        

        
        # Create payment record with lock details
        print("📝 Creating payment record...")
        payment = create_payment_record(
            user=user,
            amount=package_obj.amount,
            phone=None,
            payment_type="package",
            package=package_obj,
            lock_details=lock_details
        )
        if not payment:
            print("❌ Failed to create payment record")
            return jsonify({"error": "Failed to create payment record"}), 500
        print(f"✅ Payment record created: {payment.id}")
        
        # ============================================================
        # ✅ FIX: Convert Decimal values to float for JSON
        # ============================================================
        lock_details_serializable = None
        if lock_details:
            lock_details_serializable = {}
            for key, value in lock_details.items():
                if isinstance(value, Decimal):
                    lock_details_serializable[key] = float(value)
                else:
                    lock_details_serializable[key] = value
        
        # Create user package with lock details
        print("📦 Creating user package...")
        print(f"   User: {user.id}")
        print(f"   Package Catalog: {package_obj.id} - {package_obj.name}")
        print(f"   Lock Details: {lock_details}")
        
        user_package = create_user_package(
            user=user,
            package_catalog=package_obj,
            lock_details=lock_details
        )
        
        print(f"✅ Package created: {user_package.id} - {user_package.package}")
        print(f"   Locked: {user_package.is_locked}")
        print(f"   Lock Duration: {user_package.lock_duration_days} days")
        
        # ✅ FIX: Update payment status with serializable data
        payment.status = PaymentStatus.COMPLETED.value
        payment.raw_response = json.dumps({
            "method": "internal_balance",
            "deduct_from_actual": float(deduct_from_actual),
            "deduct_from_wallet": float(deduct_from_wallet),
            "is_locking": is_locking,
            "lock_days": lock_days,
            "lock_details": lock_details_serializable  # ✅ Use serializable version
        })
        
        # Create notification with lock info
        lock_msg = f" (Locked for {lock_days} days)" if is_locking and lock_days > 0 else ""
        notification = Notification(
            user_id=user.id,
            message=f"Package '{package_obj.name}' purchased successfully{lock_msg} using {'balance' if deduct_from_actual > 0 else 'wallet funds'}. Amount: {amount:,.0f} UGX",
            notification_type='package_purchase',
            is_read=False
        )
        db.session.add(notification)
        print("✅ Notification created")
        
        # Send notifications
        from notification.notification import send_package_activation_notifications
        send_package_activation_notifications(user, package_obj)
        print("✅ Activation notifications sent")
        
        # ✅ DEBUG: Check what's in the session before commit
        print("🔄 Committing transaction...")
        db.session.commit()
        print("✅ Database commit successful")
        
        # ========== PROCESS BONUSES ==========
        is_first_purchase = not user_has_any_package(user.id)
        bonus_success = False
        bonus_message = ""

        if is_first_purchase:
            print("👤 FIRST TIME PURCHASE: Processing referral bonuses...")
            from bonus.payment_processor import process_package_purchase
            bonus_success, bonus_message = process_package_purchase(payment)
            print(f"Bonus processing result: {bonus_success} - {bonus_message}")
        else:
            from bonus.refferral_tree import ReferralTreeHelper
            print(f"👤 User has existing package - crediting direct referrer only")
            bonus_success, bonus_message, transaction_id = ReferralTreeHelper.process_direct_referral_bonus(
                user_id=user.id,
                purchase_amount=payment.amount
            )
            print(f"Direct referral bonus result: {bonus_success} - {bonus_message}")
            if transaction_id:
                print(f"Transaction ID: {transaction_id}")

        # Build response - ✅ ensure all values are JSON serializable
        response_data = {
            "success": True,
            "reference": payment.reference,
            "status": PaymentStatus.COMPLETED.value,
            "payment_type": "package",
            "package": package_obj.name,
            "product": package_obj.name,
            "amount": float(amount),
            "is_locking": is_locking,
            "lock_days": lock_days if is_locking else 0,
            "message": f"Package purchased using {'balance' if deduct_from_actual > 0 else 'wallet funds'}",
            "new_actual_balance": float(user.actual_balance),
            "new_wallet_balance": float(user.wallet.balance) if user.wallet else 0,
            "deducted_from_actual": float(deduct_from_actual),
            "deducted_from_wallet": float(deduct_from_wallet),
            "referral_bonus_processed": bonus_success,
            "bonus_message": bonus_message,
            "package_id": user_package.id  # ✅ Include package ID to verify
        }
        
        # ✅ FIX: Add lock details with float values
        if lock_details and is_locking:
            response_data["lock_details"] = {
                "daily_rate": float(lock_details.get("daily_rate", 0)),
                "daily_return": float(lock_details.get("daily_return", 0)),
                "total_return": float(lock_details.get("total_return", 0)),
                "bonus_percentage": float(lock_details.get("bonus_percentage", 0)),
                "duration_days": lock_details.get("duration_days", 26)
            }

        print("✅ Internal package payment completed successfully")
        print(json.dumps(response_data, indent=2))
        
        return jsonify(response_data), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ Internal package payment failed: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"Internal package payment failed: {e}", exc_info=True)
        return jsonify({"error": f"Payment failed: {str(e)}"}), 500



# ============================================================
# EXTERNAL PACKAGE PAYMENT - WITH LOCKING SUPPORT
# ============================================================

def process_external_package_payment(user, amount, phone, package_obj, lock_days=0, is_locking=False, lock_details=None):
    """
    Process package purchase via external MarzPay payment with locking support.
    """
    try:
        print("=" * 60)
        print("💳 PROCESSING EXTERNAL PACKAGE PAYMENT")
        print(f"Package: {package_obj.name}")
        print(f"Amount: {amount}")
        print(f"Locking: {is_locking}, Days: {lock_days}")
        print("=" * 60)
        
        # Create payment record with lock details
        payment = create_payment_record(
            user=user,
            amount=amount,
            phone=phone,
            payment_type="package",
            package=package_obj,
            lock_details=lock_details
        )
        
        if not payment:
            return jsonify({"error": "Failed to create payment record"}), 500
        
        db.session.commit()
        
        # Send to MarzPay with lock info in description
        marz_data, error = send_payment(
            payment=payment,
            phone=phone,
            amount=amount,
            package=package_obj,
            lock_details=lock_details
        )
        
        if error:
            payment.status = PaymentStatus.FAILED.value
            db.session.commit()
            return jsonify(error), 502
        
        # Update payment with MarzPay response
        if marz_data:
            payment.external_ref = marz_data.get("internal_reference")
            payment.status = PaymentStatus.PENDING.value
            print(f"✅ Stored external_ref: {payment.external_ref}")
            db.session.commit()
        
        # Build response
        response_data = {
            "success": True,
            "reference": payment.reference,
            "status": payment.status,
            "payment_type": "package",
            "package": package_obj.id,
            "product": package_obj.name,
            "amount": float(amount),
            "is_locking": is_locking,
            "lock_days": lock_days if is_locking else 0,
            "checkout_url": marz_data.get("pop_up_info") if marz_data else None,
            "message": "Payment initiated. Please complete payment."
        }
        
        # Add lock details to response
        if lock_details and is_locking:
            response_data["lock_details"] = {
                "daily_rate": lock_details.get("daily_rate", 0),
                "daily_return": float(lock_details.get("daily_return", 0)),
                "total_return": float(lock_details.get("total_return", 0)),
                "bonus_percentage": lock_details.get("bonus_percentage", 0)
            }
        
        print("✅ External payment initiated successfully")
        print(json.dumps(response_data, indent=2))
        
        return jsonify(response_data), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"External package payment failed: {e}", exc_info=True)
        return jsonify({"error": f"Payment failed: {str(e)}"}), 500


# ============================================================
# PAYMENT CALLBACK - Webhook from MarzPay
# ============================================================



PESAJET_WEBHOOK_SECRET = os.environ.get("PESAJET_WEBHOOK_SECRET", "").encode()
def _get_webhook_secret_bytes() -> bytes:
    """Read the secret LIVE from env every call — never cache at import time."""
    raw = os.environ.get("PESAJET_WEBHOOK_SECRET", "")
    if not raw:
        print("❌ PESAJET_WEBHOOK_SECRET is not set")
        return b""
    # Strip any accidental Windows CR/LF
    raw = raw.strip()
    return raw.encode("utf-8")
# ============================================================
# SIGNATURE VERIFICATION
# ============================================================
def verify_pesajet_signature(raw_body: bytes, signature_hex: str) -> bool:
    """Try both documented verification methods (raw body, and body-without-signature)."""
    secret = _get_webhook_secret_bytes()
    if not signature_hex or not PESAJET_WEBHOOK_SECRET:
        return False
    
    if not secret:
        print("❌ verify: PESAJET_WEBHOOK_SECRET is empty")
        return False

    # Method 1: HMAC over raw body, compared to X-Webhook-Signature header
    expected = hmac.new(PESAJET_WEBHOOK_SECRET, raw_body, hashlib.sha256).hexdigest()

    if hmac.compare_digest(expected, signature_hex):
        return True

    # Method 2: HMAC over JSON minus "signature", compared to body's "signature"
    try:
        parsed = json.loads(raw_body)
        sig_in_body = parsed.pop("signature", "")
        if not sig_in_body:
            return False
        canonical = json.dumps(parsed, separators=(",", ":")).encode()
        expected_canon = hmac.new(
            PESAJET_WEBHOOK_SECRET, canonical, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_canon, sig_in_body)
    except Exception:
        return False

def _record_webhook(webhook_id, event, payload=None, signature=None, reference=None):
    if not webhook_id:
        return
    from sqlalchemy.exc import IntegrityError
    try:
        with db.session.begin_nested():
            db.session.add(WebhookEvent(
                # provider="pesajet",
                event_type=event or "unknown",
                payload=payload or {},
                signature=signature,
                reference=reference,
                webhook_id=webhook_id,
                status="received",
                processed=False,
            ))
    except IntegrityError:
        raise                      # let the route turn this into 200/duplicate
    except Exception as e:
        print(f"⚠️ webhook audit skipped (non-fatal): {e}")



def _webhook_already_processed(webhook_id) -> bool:
    if not webhook_id:
        return False
    try:
        return bool(WebhookEvent.query.filter_by(webhook_id=webhook_id).first())
    except Exception:
        return False


# ============================================================
# SHARED: parse event/status
# ============================================================
def _classify_event(data: dict):
    """Return 'success' | 'failed' | None from a PesaJet webhook payload."""
    event = (data.get("event") or "").lower()
    status = (data.get("status") or "").upper()

    if event == "payment.completed" or status == "COMPLETED":
        return "success"
    if event in ("payment.failed", "payment.expired") or status in ("FAILED", "EXPIRED"):
        return "failed"
    return None


# ============================================================
# COLLECTION HANDLER
# ============================================================
def handle_collection_webhook(payment, data, outcome):
    """Existing collection logic, moved into its own function."""
    event = (data.get("event") or "").lower()
    status_text = (data.get("status") or "").upper()
    ext_uuid = data.get("transactionId")
    provider_ref = data.get("providerReference")
    network = data.get("provider")

    if outcome == "success":
        payment.status = PaymentStatus.COMPLETED.value
        payment.verified = True
        payment.updated_at = datetime.now(timezone.utc)
        payment.provider = (network or "pesajet").lower()
        payment.external_ref = ext_uuid
        payment.provider_reference = provider_ref
        payment.raw_response = json.dumps(data)

        print(f"✅ Collection completed for payment {payment.id}")

        if payment.payment_type == "package":
            user = User.query.get(payment.user_id)
            package_obj = payment.package_catalog

            if not package_obj or not user:
                payment.status = PaymentStatus.FAILED.value
                db.session.commit()
                print(f"❌ Missing package/user for payment {payment.id}")
                return

            lock_details = None
            is_locking = False
            lock_days = 0

            if hasattr(payment, "features") and payment.features:
                features = payment.features
                if features.get("is_locking"):
                    is_locking = True
                    lock_days = features.get("lock_days", 0)
                    lock_details = {
                        "is_locking": True,
                        "lock_days": lock_days,
                        "bonus_percentage": features.get("bonus_percentage", 0),
                        "daily_rate": features.get("daily_rate", 0),
                        "daily_return": features.get("daily_return", 0),
                        "total_return": features.get("total_return", 0),
                    }

            from blueprints.payments_helpers import create_user_package
            user_package = create_user_package(
                user=user,
                package_catalog=package_obj,
                lock_details=lock_details,
            )
            print(f"✅ Package created ID: {user_package.id}")

            from notification.notification import send_package_activation_notifications
            send_package_activation_notifications(user, package_obj)
            
            lock_msg = ""
            import pytz
            kampala = pytz.timezone("Africa/Kampala")
            if is_locking and lock_days > 0 and user_package.lock_end_date:
                withdraw_date = user_package.lock_end_date + timedelta(days=0)
                withdraw_date_local = withdraw_date.astimezone(kampala)
                withdraw_date_str = withdraw_date_local.strftime("%d %b %Y")

                lock_msg = f"\n🔒 Locked for {lock_days} days\n💰 Withdraw on {withdraw_date_str}"
            db.session.add(Notification(
                user_id=user.id,
                message=f"✅ {package_obj.name} activated{lock_msg}",
                notification_type="package_activation",
                is_read=False,
            ))

            existing_package = Package.query.filter(
                Package.user_id == user.id,
                Package.id != user_package.id,
            ).first()

            if existing_package is None:
                from bonus.payment_processor import process_package_purchase
                ok, msg = process_package_purchase(payment)
                print(f"Bonus (first purchase): {ok} - {msg}")
            else:
                from bonus.refferral_tree import ReferralTreeHelper
                ok, msg, txn = ReferralTreeHelper.process_direct_referral_bonus(
                    user_id=user.id,
                    purchase_amount=payment.amount,
                )
                print(f"Bonus (direct referrer): {ok} - {msg}")


        elif payment.payment_type == "deposit":
            handle_deposit_webhook(payment, data, network, ext_uuid, provider_ref)

        else:
            print(f"⚠️ Unhandled collection payment_type: {payment.payment_type}")

    else:  # failed / expired
        failure_reason = data.get("failureReason")
        print(f"❌ Collection failed (event={event}, status={status_text}, reason={failure_reason})")
        payment.status = PaymentStatus.FAILED.value
        payment.updated_at = datetime.now(timezone.utc)
        payment.raw_response = json.dumps(data)

# DEPOSIT HANDLER
# ============================================================
def handle_deposit_webhook(payment, data, network, ext_uuid, provider_ref):
    """
    Credit a completed deposit to the user's actual_balance.

    Idempotency: uses payment.status guard in the caller. Also checks for an
    existing completed transaction with this payment's reference, so a
    double-fired webhook can never credit twice.
    """
    from decimal import Decimal
    from models import Transaction, Notification, Wallet

    user = User.query.get(payment.user_id)
    if not user:
        payment.status = PaymentStatus.FAILED.value
        db.session.commit()
        print(f"❌ Deposit: user {payment.user_id} not found for payment {payment.id}")
        return

    # --- Idempotency guard #2 (belt + suspenders) ---
    already = Transaction.query.filter_by(
        user_id=user.id,
        reference=payment.reference,
        type="deposit",
        status="completed",
    ).first()
    if already:
        print(f"⚠️ Deposit already credited for payment {payment.id} "
              f"(txn {already.id}) — skipping")
        return

    try:
        amount = Decimal(str(payment.amount or 0))
        if amount <= 0:
            print(f"❌ Deposit payment {payment.id} has invalid amount {amount}")
            payment.status = PaymentStatus.FAILED.value
            db.session.commit()
            return

        # --- Ensure wallet exists (for the transaction FK) ---
        wallet = user.wallet
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=Decimal("0"), locked_balance=Decimal("0"))
            db.session.add(wallet)
            db.session.flush()
            user.wallet = wallet

        # --- Credit actual balance ---
        before = Decimal(str(user.actual_balance or 0))
        user.actual_balance = before + amount
        db.session.add(user)

        # --- Audit transaction ---
        txn = Transaction(
            user_id=user.id,
            wallet_id=wallet.id,
            amount=amount,
            type="deposit",
            status="completed",
            reference=payment.reference,
            phone_number=payment.phone_number,
            purchase_type="Mobile money deposit",
      
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(txn)

        # --- Notify user ---
        db.session.add(Notification(
            user_id=user.id,
            message=(
                f"💰 Deposit of UGX {amount:,.0f} received. "
                f"New balance: UGX {user.actual_balance:,.0f}"
            ),
            notification_type="deposit_completed",
            is_read=False,
        ))

        print(f"✅ Deposit credited: user {user.id}, "
              f"amount {amount:,.0f}, new balance {user.actual_balance:,.0f}, "
              f"txn ref {payment.reference}")

    except Exception as e:
        db.session.rollback()
        payment.status = PaymentStatus.FAILED.value
        db.session.commit()
        print(f"❌ Deposit credit failed for payment {payment.id}: {e}")
        import traceback
        traceback.print_exc()
# ============================================================
# DISBURSEMENT HANDLER
# ============================================================
def handle_disbursement_webhook(withdrawal, data, outcome):
    event = (data.get("event") or "").lower()
    status_text = (data.get("status") or "").upper()
    ext_uuid = data.get("transactionId")
    provider_ref = data.get("providerReference")
    failure_reason = data.get("failureReason")

    if outcome == "success":
        withdrawal.status = "completed"
        withdrawal.external_ref = ext_uuid
        withdrawal.updated_at = datetime.now(timezone.utc)
        print(f"✅ Withdrawal completed: {withdrawal.reference} (txn={ext_uuid})")

        # Notify the user
        try:
            db.session.add(Notification(
                user_id=withdrawal.user_id,
                message=f"Your withdrawal of UGX {withdrawal.net_amount:,.0f} has been sent successfully.",
                notification_type="withdrawal_completed",
                is_read=False,
            ))
        except Exception as e:
            print(f"⚠️ Failed to create withdrawal-completed notification: {e}")

    else:  # failed / expired
        print(f"❌ Withdrawal failed (event={event}, status={status_text}, reason={failure_reason})")

        # Refund the deducted balance
        user = db.session.get(User, withdrawal.user_id)
        if user:
            balance_details = {
                "actual_deducted": str(withdrawal.actual_balance_deducted or 0),
                "wallet_deducted": str(withdrawal.wallet_balance_deducted or 0),
            }
            WithdrawalProcessor.fail_withdrawal(
                withdrawal.id,
                withdrawal.user_id,
                Decimal(str(withdrawal.amount)),
                balance_details,
            )
        else:
            # Can't refund — still mark failed
            WithdrawalRecordManager.update_status(withdrawal.id, "failed")

        # Notify the user
        try:
            db.session.add(Notification(
                user_id=withdrawal.user_id,
                message=f"Your withdrawal of UGX {withdrawal.net_amount:,.0f} failed and has been refunded.",
                notification_type="withdrawal_failed",
                is_read=False,
            ))
        except Exception as e:
            print(f"⚠️ Failed to create withdrawal-failed notification: {e}")


import threading
# ============================================================
# BACKGROUND BUSINESS LOGIC (runs AFTER the 200 is sent)
# ============================================================
def _process_webhook_business_logic(data: dict, webhook_id):
    """
    All the slow work: row locks, package creation, deposits,
    referrals, notifications. Runs in a background thread.
    """
    outcome = _classify_event(data)
    if outcome is None:
        print(f"⚠️ Unknown event/status: {data.get('event')} / {data.get('status')}")
        return

    transaction_id = data.get("transactionId")
    reference = data.get("reference") or ""
    reference_base = reference.split("|", 1)[0] if reference else None

    print(f"🔎 [bg] txn={transaction_id} ref={reference} outcome={outcome}")

    # --------------------------------------------------------
    # COLLECTION (Payment) FIRST
    # --------------------------------------------------------
    payment = None
    if transaction_id:
        payment = Payment.query.filter_by(external_ref=transaction_id)\
            .with_for_update().first()
    if not payment and reference_base:
        payment = Payment.query.filter_by(reference=reference_base)\
            .with_for_update().first()

    if payment:
        print(f"📦 Matched COLLECTION: payment id={payment.id} status={payment.status}")

        if payment.status in (
            PaymentStatus.COMPLETED.value,
            PaymentStatus.FAILED.value,
        ):
            print(f"⚠️ Payment already final: {payment.status}")
            db.session.commit()
            return

        try:
            handle_collection_webhook(payment, data, outcome)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        print(f"✅ [bg] collection processed for payment {payment.id}")
        return

    # --------------------------------------------------------
    # DISBURSEMENT (Withdrawal)
    # --------------------------------------------------------
    withdrawal = None
    if transaction_id:
        withdrawal = Withdrawal.query.filter_by(external_ref=transaction_id)\
            .with_for_update().first()
    if not withdrawal and reference_base:
        withdrawal = Withdrawal.query.filter_by(reference=reference_base)\
            .with_for_update().first()

    if withdrawal:
        print(f"💸 Matched DISBURSEMENT: withdrawal id={withdrawal.id} status={withdrawal.status}")

        if withdrawal.status in ("completed", "failed", "cancelled"):
            print(f"⚠️ Withdrawal already final: {withdrawal.status}")
            db.session.commit()
            return

        try:
            handle_disbursement_webhook(withdrawal, data, outcome)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        print(f"✅ [bg] disbursement processed for withdrawal {withdrawal.id}")
        return

    # --------------------------------------------------------
    # NO MATCH
    # --------------------------------------------------------
    print(f"⚠️ [bg] No matching Payment or Withdrawal "
          f"for txn={transaction_id} ref={reference}")

def _handle_marz_callback(raw_body: bytes):
    try:
        # 1. Parse
        try:
            data = json.loads(raw_body)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400

        print(f"Payload: {json.dumps(data, indent=2)}")

        # 2. Extract nested transaction
        # 2. Extract nested transaction
        outer = data.get("data") if isinstance(data.get("data"), dict) else data
        transaction = outer.get("transaction") if isinstance(outer, dict) else None
        if not isinstance(transaction, dict) or not transaction:
            print(f"⚠️ Marz callback: no transaction object")
            print(f"   outer keys = {list(outer.keys()) if isinstance(outer, dict) else 'N/A'}")
            return jsonify({"error": "Missing transaction object"}), 400

        status = (transaction.get("status") or "").lower()
        reference = transaction.get("reference") or data.get("reference")
        ext_uuid = transaction.get("uuid") or data.get("uuid")

        print("🔬 DIAGNOSTIC:")
        print(f"   data keys        = {list(data.keys())}")
        print(f"   data['data']     = {type(data.get('data'))}")
        print(f"   outer keys       = {list(outer.keys()) if isinstance(outer, dict) else 'N/A'}")
        print(f"   transaction type = {type(transaction)}")
        print(f"   transaction      = {transaction}")
        print(f"   reference        = {reference!r}")
        print(f"   ext_uuid         = {ext_uuid!r}")

        if not reference and not ext_uuid:
            return jsonify({"error": "Missing reference and uuid"}), 400

        # 3. Map Marz status → outcome
        outcome = _map_marz_outcome(status)
        if outcome is None:
            print(f"⚠️ Unknown Marz status: {status}")
            return jsonify({"status": "ignored"}), 200

        # 4. Synthesized dedup key (Marz sends no webhook id header)
        webhook_id = f"marz_{ext_uuid}" if ext_uuid else f"marz_{reference}"

        if _webhook_already_processed(webhook_id):
            print(f"⚠️ Duplicate Marz webhook: {webhook_id}")
            return jsonify({"status": "duplicate"}), 200

        print(f"🔎 marz ref={reference} uuid={ext_uuid} status={status} outcome={outcome}")

        # 5. Normalize into the flat shape handle_collection_webhook reads
        normalized = {
            "transactionId":     ext_uuid,
            "reference":         reference,
            #"provider":          transaction.get("provider"),
            "providerReference": transaction.get("provider_reference"),
            "status":            status.upper(),
            "event":             "payment.completed" if outcome == "success"
                                 else "payment.failed",
            "failureReason":     transaction.get("failure_reason"),
            "raw_marz":          data,
        }

        # 6. Look up Payment
        payment = None
        if reference:
            payment = Payment.query.filter_by(reference=reference)\
                .with_for_update().first()
        if not payment and ext_uuid:
            payment = Payment.query.filter_by(external_ref=ext_uuid)\
                .with_for_update().first()

        if not payment:
            print(f"⚠️ No matching Payment for ref={reference} uuid={ext_uuid}")
            _record_webhook(webhook_id, normalized["event"], data, None, ext_uuid)
            db.session.commit()
            return jsonify({"status": "ignored"}), 200

        print(f"📦 Matched Marz COLLECTION: payment id={payment.id} status={payment.status}")

        # 7. Duplicate guard
        if payment.status in (PaymentStatus.COMPLETED.value, PaymentStatus.FAILED.value):
            print(f"⚠️ Payment already final: {payment.status}")
            _record_webhook(webhook_id, normalized["event"], data, None, ext_uuid, provider="marz")
            db.session.commit()
            return jsonify({"status": "already_final"}), 200

        # 8. Dispatch to the shared helper
        handle_collection_webhook(payment, normalized, outcome)
        _record_webhook(webhook_id, normalized["event"], data, None, ext_uuid)
        db.session.commit()
        return jsonify({"status": "ok", "type": "collection", "provider": "marz"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Marz webhook error: {e}", exc_info=True)
        print(f"❌ Marz webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Webhook processing failed"}), 500


def _map_marz_outcome(status: str):
    """Map a Marz transaction status to our success/failed outcome."""
    if status in ("complete", "completed", "paid", "success", "successful"):
        return "success"
    if status in ("failed", "cancelled", "canceled", "expired", "rejected"):
        return "failed"
    return None



# ============================================================
# MAIN CALLBACK ROUTE — FAST ACK + TIMING INSTRUMENTATION
# ============================================================
import threading
import time
from flask import current_app, jsonify, request
from sqlalchemy.exc import IntegrityError


@bp.route("/payments/callback", methods=["POST"])
def payment_callback():
    """Unified callback for PesaJet and Marz — fast ACK, async processing."""
    t_start = time.perf_counter()

    # --------------------------------------------------------
    # 0. READ RAW BODY + DETECT PROVIDER  (request context required)
    # --------------------------------------------------------
    raw_body = request.get_data()
    provider = _detect_callback_provider(request, raw_body)

    print("=" * 60)
    print(f"📞 {provider.upper() if provider else 'UNKNOWN'} WEBHOOK RECEIVED")
    print("=" * 60)

    if not provider:
        # Unknown provider — ack 200 so the sender stops retrying
        print("⚠️ Unknown callback provider — ignoring")
        return jsonify({"status": "ignored"}), 200

    # --------------------------------------------------------
    # 1. PICK THE PROVIDER-SPECIFIC VERIFIER
    # --------------------------------------------------------
    # PesaJet uses HMAC-SHA256; Marz may use a different scheme.
    # Your existing `_handle_pesajet_callback` / `_handle_marz_callback`
    # already encapsulate their own verification — but we must verify
    # IN THE REQUEST THREAD (before returning 200), because we want to
    # reject bad signatures with 401 instead of acking them.
    # --------------------------------------------------------
    t0 = time.perf_counter()

    if provider == "pesajet":
        signature = request.headers.get("X-Webhook-Signature", "")
        webhook_id = request.headers.get("X-Webhook-Id")

        if not verify_pesajet_signature(raw_body, signature):
            elapsed = (time.perf_counter() - t_start) * 1000
            print(f"❌ Invalid PesaJet signature (total {elapsed:.0f}ms)")
            return jsonify({"error": "Signature mismatch"}), 401

    elif provider == "marz":
        return _handle_marz_callback(raw_body)
        # Replace with your Marz verifier (header name / scheme).
        # Example — adapt to whatever Marz actually sends:
        #marz_sig = request.headers.get("X-Marz-Signature", "")
        #webhook_id = request.headers.get("X-Webhook-Id")
        # if not verify_marz_signature(raw_body, marz_sig):
        #     return jsonify({"error": "Signature mismatch"}), 401
    else:
        return jsonify({"status": "ignored"}), 200

    t_verify = (time.perf_counter() - t0) * 1000

    # --------------------------------------------------------
    # 2. PARSE JSON
    # --------------------------------------------------------
    t0 = time.perf_counter()
    try:
        data = json.loads(raw_body)
    except Exception:
        elapsed = (time.perf_counter() - t_start) * 1000
        print(f"❌ Invalid JSON (total {elapsed:.0f}ms)")
        return jsonify({"error": "Invalid JSON"}), 400
    t_parse = (time.perf_counter() - t0) * 1000

    # --------------------------------------------------------
    # 3. DEDUPLICATION
    #    Keyed on (provider, webhook_id) so the same id from two
    #    different providers can't collide.
    # --------------------------------------------------------
    t0 = time.perf_counter()
    if _webhook_already_processed(webhook_id):
        elapsed = (time.perf_counter() - t_start) * 1000
        print(f"⚠️ Duplicate {provider} webhook {webhook_id} "
              f"(dedup {t_parse:.0f}ms, total {elapsed:.0f}ms)")
        return jsonify({"status": "duplicate"}), 200
    t_dedup = (time.perf_counter() - t0) * 1000

    # --------------------------------------------------------
    # 4. AUDIT INSERT + COMMIT
    # --------------------------------------------------------
    t0 = time.perf_counter()
    try:
        _record_webhook(
            webhook_id,
            data.get("event"),
            data,
            request.headers.get("X-Webhook-Signature"),
            data.get("transactionId"),
            provider=provider,
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        elapsed = (time.perf_counter() - t_start) * 1000
        print(f"⚠️ Duplicate {provider} webhook (unique constraint) {webhook_id} "
              f"(total {elapsed:.0f}ms)")
        return jsonify({"status": "duplicate"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ webhook audit commit failed (non-fatal): {e}")
    t_audit = (time.perf_counter() - t0) * 1000

    # --------------------------------------------------------
    # 5. ACK IMMEDIATELY
    # --------------------------------------------------------
    t_total = (time.perf_counter() - t_start) * 1000
    print(
        f"⏱ [fast-path][{provider}] verify={t_verify:.0f}ms "
        f"parse={t_parse:.0f}ms dedup={t_dedup:.0f}ms "
        f"audit={t_audit:.0f}ms TOTAL={t_total:.0f}ms"
    )

    # --------------------------------------------------------
    # 6. BACKGROUND BUSINESS LOGIC  (provider-aware)
    # --------------------------------------------------------
    app_obj = current_app._get_current_object()

    def process_in_background():
        with app_obj.app_context():
            try:
                if provider == "pesajet":
                    _process_webhook_business_logic(data, webhook_id)
                elif provider == "marz":
                    _handle_marz_callback(data, webhook_id)
                # If Marz reuses the same classification logic,
                # you can simply call _process_webhook_business_logic
                # for both and drop the branch above.
            except Exception as e:
                app_obj.logger.error(
                    f"[{provider}] background webhook processing failed: {e}",
                    exc_info=True,
                )
                try:
                    db.session.rollback()
                except Exception:
                    pass
            finally:
                try:
                    db.session.remove()
                except Exception:
                    pass

    threading.Thread(target=process_in_background, daemon=True).start()

    return jsonify({"status": "ok"}), 200

def _detect_callback_provider(req, raw_body: bytes) -> str | None:
    """
    Identify which provider sent this callback.

    PesaJet:  signed with X-Webhook-Signature, payload has top-level
              transactionId.
    Marz:     no signature header, payload has either:
              - top-level `transaction` object, OR
              - nested `data.transaction` object
    """
    if req.headers.get("X-Webhook-Signature") or req.headers.get("X-Webhook-Id"):
        return "pesajet"

    try:
        data = json.loads(raw_body)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    # PesaJet fallback (no header, but flat shape)
    if "transactionId" in data:
        return "pesajet"

    # Marz flat
    if isinstance(data.get("transaction"), dict):
        return "marz"

    # Marz nested under "data"
    inner = data.get("data")
    if isinstance(inner, dict) and isinstance(inner.get("transaction"), dict):
        return "marz"

    return None



# ============================================================
# GET PACKAGE CATALOG ENDPOINT
# ============================================================
@bp.route("/payments/status/<reference>", methods=["GET"])
def payment_status(reference):
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    payment = Payment.query.filter_by(
        reference=reference, user_id=user.id
    ).first()
    if payment:
        

        return jsonify({
            "reference": payment.reference,
            "status":    payment.status,          # pending | completed | failed
            "payment_type": payment.payment_type,
        })

        # 2. Try Withdrawal (payouts)
    withdrawal = Withdrawal.query.filter_by(
        reference=reference, user_id=user.id
    ).first()
    if withdrawal:
        # normalize: map internal statuses to the frontend's expected set
        status = withdrawal.status
        if status in ("completed",):
            normalized = "completed"
        elif status in ("failed", "cancelled", "refunded", "rejected"):
            normalized = "failed"
        else:
            normalized = "pending"      # pending, processing, initiated, queued
        return jsonify({
            "reference": withdrawal.reference,
            "status":    normalized,
            "kind":      "withdrawal",
        })
    return jsonify({"error": "Not found"}), 404

@bp.route("/payments/packages", methods=['GET'])
def get_packages():
    """All products, straight from splendour_catalog (the frontend catalog.js is generated from the same data)."""
    from blueprints.payments_helpers import public_catalog
    from splendour_catalog import MIN_DEPOSIT
    plans = public_catalog()
    return jsonify({"success": True, "packages": plans, "count": len(plans), "min_deposit": MIN_DEPOSIT}), 200


@bp.route("/payments/packages/<package_id>", methods=['GET'])
def get_package_detail(package_id):
    from blueprints.payments_helpers import public_catalog
    for p in public_catalog():
        if p["key"] == package_id.lower().strip():
            return jsonify({"success": True, "package": p}), 200
    return jsonify({"error": "Package not found", "code": "PRODUCT_NOT_FOUND"}), 404


#==========================================================================================================
@bp.route("/payments/callback/", methods=['POST'])
def payment_callback_():
    payment = None
    try:
        data = request.get_json(silent=True) or {}
        print(f"🔍 RAW CALLBACK DATA: {json.dumps(data, indent=2)}")
        
        if not data:
            return jsonify({"error": "No JSON data"}), 400

        transaction = data.get("transaction", {})
        status = transaction.get("status", "completed").lower()
        print(f"🔄 MARZ STATUS: {status}")
        
        reference = (
            data.get("transaction", {}).get("reference") or
            data.get("reference")
        )
        ext_uuid = transaction.get("uuid") or data.get("uuid")
        
        if not reference and not ext_uuid:
            return jsonify({"error": "Missing reference"}), 400
        
        # Get payment with row lock
        payment = None
        if reference:
            payment = Payment.query.filter_by(reference=reference).with_for_update().first()
        
        if not payment and ext_uuid:
            payment = Payment.query.filter_by(external_ref=ext_uuid).with_for_update().first()
        
        if not payment:
            print(f"No matching payment for reference {reference} / ext {ext_uuid}")
            return jsonify({"status": "ignored"}), 200
            
        # Prevent duplicate processing
        if payment.status == PaymentStatus.COMPLETED.value:
            print(f"⚠️ Payment already processed: {payment.reference}")
            return jsonify({"status": "already_processed"}), 200
        
        if payment.status == PaymentStatus.FAILED.value:
            print(f"⚠️ Payment previously failed: {payment.reference}")
            return jsonify({"status": "already_failed"}), 200
        
        # Handle success status
        if status in ("complete", "completed", "paid"):
            payment.status = PaymentStatus.COMPLETED.value
            payment.verified = True
            payment.updated_at = datetime.now(timezone.utc)
            payment.provider = data.get("transaction", {}).get("provider")
            payment.external_ref = transaction.get("uuid")
            payment.raw_response = json.dumps(data)
            payment.provider_reference = transaction.get("provider_reference")
            
            print(f"🔍 Checking payment type: {payment.payment_type}")
            print(f"✅ Payment status updated to: {payment.status}")
            
                        # ============================================================
            # MEDIA STAR HANDLER
            # ============================================================
            if payment.payment_type == "media_star":
                print("📺 Processing Media Star subscription from callback")
                user = User.query.get(payment.user_id)
                
                if not user:
                    payment.status = PaymentStatus.FAILED.value
                    db.session.commit()
                    return jsonify({"error": "User not found"}), 400
                
                try:
                    # Extract Media Star metadata from raw_response
                    metadata = json.loads(payment.raw_response or '{}')
                    print(f"📺 Media Star metadata: {metadata}")
                    
                    # Get subscription details (stored during initiation)
                    subscription_data = json.loads(payment.raw_response) if payment.raw_response else {}
                    if 'subscription' in subscription_data:
                        package_name = subscription_data.get('subscription')
                        serial_number = subscription_data.get('serial_number')
                        package_code = subscription_data.get('package_code')
                        amount = subscription_data.get('amount', 0)
                        service_charge = subscription_data.get('service_charge', 1500)
                    else:
                        # Fallback: try to get from metadata field
                        metadata_field = json.loads(payment.metadata) if payment.metadata else {}
                        package_name = metadata_field.get('subscription', 'Media Star')
                        serial_number = metadata_field.get('serial_number', 'N/A')
                        package_code = metadata_field.get('package_code', 'N/A')
                        amount = float(payment.amount) - 1500
                        service_charge = 1500
                    
                    print(f"📺 Activating: {package_name} for serial: {serial_number}")
                    
                    # ✅ TODO: Call Media Star API to activate subscription
                
                    # Create success notification
                    from models import Notification
                    notification = Notification(
                        user_id=user.id,
                        message=f"📺 Media Star TV subscription '{package_name}' activated successfully! Amount: {amount:,.0f} UGX + {service_charge:,.0f} UGX service charge.",
                        notification_type='bill_payment',
                        is_read=False
                    )
                    db.session.add(notification)
                    
                    # Also add to user's actual balance if there's any remaining? No, payment was external
                    # Just mark as completed
                    
                    db.session.commit()
                    print(f"✅ Media Star subscription activated for user {user.id}")
                    
                    return jsonify({
                        "status": "ok",
                        "payment_type": "media_star",
                        "subscription": package_name,
                        "message": "Media Star subscription activated successfully"
                    }), 200
                    
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Media Star processing failed: {e}", exc_info=True)
                    payment.status = PaymentStatus.PENDING.value
                    db.session.add(payment)
                    db.session.commit()
                    return jsonify({"error": f"Media Star processing failed: {str(e)}"}), 500


            # ✅ FIX 2: Process based on payment type
            if payment.payment_type == "package":
                user = User.query.get(payment.user_id)
                package_obj = payment.package_catalog
                
                # ✅ FIX 3: Correct logic - check BOTH conditions
                if not package_obj or not user:
                    payment.status = PaymentStatus.FAILED.value
                    db.session.commit()
                    return jsonify({"error": "Missing Package or User"}), 400
                
                try:
                    from blueprints.payments_helpers import create_user_package
                    user_package = create_user_package(user, package_obj)
                    
                    from notification.notification import send_package_activation_notifications
                    send_package_activation_notifications(user, package_obj)

                    
                    existing_package = Package.query.filter(
                        Package.user_id == user.id,
                        Package.id != user_package.id 
                    ).first()
                    
                    is_first_purchase = (existing_package is None)

                     # ========== STEP 4: PROCESS BONUSES ONLY IF FIRST PURCHASE ==========
                    if is_first_purchase:
                        print("USER FIRST TIME PACKAGE PURCHASE: Processing Referral Bonuses....")
                        from bonus.payment_processor import process_package_purchase
                        success, message = process_package_purchase(payment)
                        print(f"Bonus processing result: {success} - {message}")
                    else:
                        from bonus.refferral_tree import ReferralTreeHelper
                        print(f"User {user.id} already has a package - crediting direct referrer only")
                        success, message, transaction_id = ReferralTreeHelper.process_direct_referral_bonus(
                                            user_id=user.id,
                                            purchase_amount=payment.amount
                                        )
                        
                        print(f"Direct referral bonus result: {success} - {message}")
                        if transaction_id:
                            print(f"Transaction ID: {transaction_id}")
                     
                    # =========================================================================
     
                    # ✅ FIX 4: Commit ONLY after ALL operations succeed
                    db.session.commit()
                    
                    if success:
                        print(f"✅ Package processed: {message}")
                        return jsonify({
                            "status": "ok",
                            "bonus_status": "success",
                            "message": message
                        }), 200
                    else:
                        # ✅ FIX 5: Even if bonus processing had issues, package is created
                        # This is still a success for the payment
                        print(f"⚠️ Package created but bonus issue: {message}")
                        return jsonify({
                            "status": "ok",
                            "bonus_status": "warning",
                            "message": "Package created but bonus processing had issues"
                        }), 200
                        
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Package processing failed: {e}", exc_info=True)
                    # Keep payment as PENDING for retry
                    payment.status = PaymentStatus.PENDING.value
                    db.session.add(payment)
                    db.session.commit()
                    return jsonify({"error": f"Package processing failed: {str(e)}"}), 500
                    
            elif payment.payment_type == "deposit":
                user = User.query.get(payment.user_id)
                if not user:
                    payment.status = PaymentStatus.FAILED.value
                    db.session.rollback()
                    return jsonify({"error": "User not found"}), 400
                
                try:
                    user.actual_balance += Decimal(str(payment.amount))
                    print(f"Deposit completed: Added {payment.amount} to user {user.id}")
                    db.session.commit()
                    return jsonify({"status": "ok", "message": "Deposit processed"}), 200
                    
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f"Deposit processing failed: {e}", exc_info=True)
                    payment.status = PaymentStatus.PENDING.value
                    db.session.add(payment)
                    db.session.commit()
                    return jsonify({"error": "Deposit processing failed"}), 500
        
        else:
            # Handle failed payment
            print(f"❌ Payment failed with status: {status}")
            payment.status = PaymentStatus.FAILED.value
            payment.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify({"status": "ok", "message": "Payment marked as failed"}), 200
        
    except Exception as e:
        # ✅ FIX 6: Always rollback on exception
        if payment:
            db.session.rollback()
        current_app.logger.error(f"Callback error: {e}", exc_info=True)
        return jsonify({"error": "Payment processing failed"}), 500
#=======================================================================================================


# ============================================================
# CONSTANTS
# ============================================================

# ============================================================
# PESAJET CONFIG
# ============================================================
PESAJET_BASE_URL = "https://payments.pesajet.com"
PESAJET_REQUEST_TIMEOUT = 60


def detect_provider(phone: str) -> str:
    """Map a Ugandan phone number to a PesaJet provider."""
    if os.environ.get("PESAJET_SANDBOX") == "1":
        return "sandbox"
    p = phone.lstrip("+")
    if p.startswith(("25677", "25678", "25639", "25676", "25679")):
        print("MTN detected. Routing to MTN=========")
        return "mtn"
    if p.startswith(("25670", "25675", "25674", "25673", "25620")):
        print("AIRTEL DETECTED: Routing to airtel=========")
        return "airtel"
    raise ValueError(f"Cannot determine provider for {phone}")


# ============================================================
# WITHDRAWAL ROUTE - PESAJET INTEGRATION
# ============================================================


@bp.route("/wallet/transfer-locked", methods=["POST"])
def transfer_locked():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    user = db.session.get(User, user_id)
    if not user or not user.wallet:
        return jsonify({"success": False, "error": "Wallet not found"}), 404

    try:
        now = datetime.now(timezone.utc)

        # ------------------------------------------------------------
        # 1. Flip any matured locks to unlocked BEFORE querying
        #    A lock is mature when is_locked=True AND lock_end_date <= now
        # ------------------------------------------------------------
        matured = (
            db.session.query(Package)
            .filter(
                Package.user_id == user.id,
                Package.is_locked == True,
                Package.lock_end_date.isnot(None),
                Package.lock_end_date <= now,
            )
            .all()
        )
        for pkg in matured:
            pkg.is_locked = False
            logger.info("🔓 Package %s lock matured — now transferable", pkg.id)

        if matured:
            db.session.flush()

        # ------------------------------------------------------------
        # 2. Find mature, untransferred locked packages
        #    is_locked=False means either "was locked and matured"
        #    or "never locked". lock_earnings > 0 filters out the latter.
        # ------------------------------------------------------------
        mature_packages = (
            db.session.query(Package)
            .filter(
                Package.user_id == user.id,
                Package.is_locked == False,
                Package.lock_earnings > 0,
            )
            .with_for_update()
            .all()
        )

        if not mature_packages:
            return jsonify({
                "success": False,
                "error": (
                    "No mature locked balance available. "
                    "Locked earnings can only be transferred after the lock period ends."
                )
            }), 400

        # ------------------------------------------------------------
        # 3. Sum what's transferable
        # ------------------------------------------------------------
        total_transferable = sum(
            (Decimal(str(p.lock_earnings or 0)) for p in mature_packages),
            Decimal("0"),
        )

        if total_transferable <= 0:
            return jsonify({"success": False, "error": "No transferable locked balance"}), 400

        # ------------------------------------------------------------
        # 4. Sanity guard — wallet vs packages
        # ------------------------------------------------------------
        wallet_locked = Decimal(str(user.wallet.locked_balance or 0))
        if wallet_locked < total_transferable:
            logger.error(
                "Locked balance drift: wallet=%s, pkg_sum=%s, user=%s",
                wallet_locked, total_transferable, user.id,
            )
            return jsonify({
                "success": False,
                "error": "Balance mismatch detected. Please contact support."
            }), 500

        # ------------------------------------------------------------
        # 5. Perform the transfer
        # ------------------------------------------------------------
        new_balance = Decimal(str(user.actual_balance or 0)) + total_transferable
        user.actual_balance = float(new_balance)
        user.wallet.locked_balance = float(wallet_locked - total_transferable)

        for pkg in mature_packages:
            pkg.lock_earnings = 0
            # is_locked already False from step 1

        # ------------------------------------------------------------
        # 6. Audit trail
        # ------------------------------------------------------------
        tx = Transaction(
            user_id=user.id, 
            wallet_id=user.wallet.id,       # ← was user.id (bug)
            type="lock_transfer",
            amount=float(total_transferable),
            status="completed",
            purchase_type=(
                f"Transferred UGX {total_transferable:,.0f} from "
                f"{len(mature_packages)} matured locked package(s)"
            ),
        )
        db.session.add(tx)
        db.session.commit()

        logger.info(
            "Locked transfer OK: user=%s amount=%s packages=%s",
            user.id, total_transferable, len(mature_packages),
        )

        return jsonify({
            "success": True,
            "message": f"UGX {total_transferable:,.0f} transferred to deposit balance",
            "transferred": float(total_transferable),
            "packages_processed": len(mature_packages),
            "new_balance": float(new_balance),
            "new_locked_balance": float(user.wallet.locked_balance),
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception("Locked transfer failed: user=%s error=%s", user_id, e)
        return jsonify({
            "success": False,
            "error": "Transfer failed. Please try again."
        }), 500

@bp.route("/wallet/transfer-locked/<int:package_id>", methods=["POST"])
def transfer_locked_package(package_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    user = db.session.get(User, user_id)
    if not user or not user.wallet:
        return jsonify({"success": False, "error": "Wallet not found"}), 404

    try:
        # Flip matured locks for this user first (safety)
        now = datetime.now(timezone.utc)
        (
            db.session.query(Package)
            .filter(
                Package.user_id == user.id,
                Package.is_locked == True,
                Package.lock_end_date.isnot(None),
                Package.lock_end_date <= now,
            )
            .update({"is_locked": False}, synchronize_session=False)
        )

        # Lock only this package
        pkg = (
            db.session.query(Package)
            .filter(
                Package.id == package_id,
                Package.user_id == user.id,
                Package.is_locked == False,
                Package.lock_earnings > 0,
            )
            .with_for_update()
            .first()
        )

        if not pkg:
            return jsonify({
                "success": False,
                "error": "This package is not ready to transfer yet."
            }), 400

        amount = Decimal(str(pkg.lock_earnings or 0))
        if amount <= 0:
            return jsonify({"success": False, "error": "Nothing to transfer"}), 400

        wallet_locked = Decimal(str(user.wallet.locked_balance or 0))
        if wallet_locked < amount:
            logger.error(
                "Locked drift: wallet=%s pkg=%s user=%s pkg_id=%s",
                wallet_locked, amount, user.id, pkg.id,
            )
            return jsonify({
                "success": False,
                "error": "Balance mismatch. Contact support."
            }), 500

        # Move funds
        new_balance = Decimal(str(user.actual_balance or 0)) + amount
        user.actual_balance = float(new_balance)
        user.wallet.locked_balance = float(wallet_locked - amount)

        pkg.lock_earnings = 0
        pkg.status = "completed"  # or whatever your terminal status is

        tx = Transaction(
            user_id=user.id, 
            wallet_id=user.wallet.id,
            type="lock_transfer",
            amount=float(amount),
            status="completed",
            reference=f"LOCKT-{uuid.uuid4().hex[:12].upper()}",
            purchase_type=f"LOCK-1PKG",
        )
        db.session.add(tx)
        db.session.commit()

        logger.info(
            "Per-package locked transfer OK: user=%s pkg=%s amount=%s",
            user.id, pkg.id, amount,
        )

        return jsonify({
            "success": True,
            "message": f"UGX {amount:,.0f} transferred to deposit balance",
            "transferred": float(amount),
            "package_id": pkg.id,
            "new_balance": float(new_balance),
            "new_locked_balance": float(user.wallet.locked_balance),
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception("Per-package transfer failed: user=%s err=%s", user_id, e)
        return jsonify({
            "success": False,
            "error": "Transfer failed. Please try again."
        }), 500
    
@bp.route("/payments/withdraw", methods=["POST"])
def withdraw():
    """
    Main withdrawal endpoint with PesaJet DISBURSEMENT integration.
    """

    # ============================================================
    # 1. GET AND VALIDATE INPUT  (unchanged)
    # ============================================================
  
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400

    amount = data.get("amount")
    payment_type = data.get("payment_type", "withdrawal")
    recipient_phone = data.get("recipient_phone") if payment_type == "send_money" else None

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if payment_type == "send_money":
        phone_number = user.phone
        if not phone_number:
            return jsonify({"error": "User does not have a registered phone number"}), 400
    else:
        phone_number = data.get("phone") or data.get("phone_number")

    # Idempotency key — reused as PesaJet's idempotencyKey
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        import hashlib
        key_material = f"{session.get('user_id')}:{amount}:{phone_number}:{datetime.now().date()}"
        idempotency_key = hashlib.sha256(key_material.encode()).hexdigest()

    logger.info(f"Idempotency key: {idempotency_key}")
    logger.info(f"WITHDRAW PROCESSING STARTED: {data}, {amount}, {phone_number}")

    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    if payment_type == "send_money" and not recipient_phone:
        return jsonify({"error": "Recipient phone number required for send money"}), 400
    if payment_type != "send_money" and not phone_number:
        return jsonify({"error": "Phone number is required"}), 400
    if payment_type != "send_money" and not amount:
        return jsonify({"error": "Amount is required"}), 400

    try:
        # ============================================================
        # 2. PROCESS WITHDRAWAL INTERNALLY  (unchanged)
        # ============================================================
        amount_decimal = Decimal(str(amount))

        success, message, withdrawal_data = WithdrawalProcessor.process_withdrawal_request(
            user_id, amount_decimal, phone_number, idempotency_key
        )

        if not success:
            return jsonify({"error": message}), 400

        if withdrawal_data.get("already_processed"):
            return jsonify({
                "success": True,
                "message": message,
                "withdrawal_id": withdrawal_data["reference"],
                "already_processed": True,
            }), 200
                # ============================================================
        # 2b. ADMIN REVIEW BRANCH  (minimal fix)
        # ============================================================
        if amount_decimal > WithdrawalConfig.ADMIN_REVIEW_THRESHOLD:
            print("Amount for admin approval. sending to admin........")
            from blueprints.withdraw_helpers import WithdrawalRecordManager
            WithdrawalRecordManager.update_status(
                withdrawal_data["withdrawal_id"],
                "pending_admin",        # new status — admin will resolve
            )
            print("Withdrawl sent to admin........pending admin")
            db.session.commit()

            logger.info(
                f"Withdrawal {withdrawal_data['reference']} flagged for admin review "
                f"(amount={amount_decimal} > {WithdrawalConfig.ADMIN_REVIEW_THRESHOLD})"
            )

            return jsonify({
                "success": True,
                "message": "Withdrawal submitted. It will be reviewed and processed shortly.",
                "withdrawal_id": withdrawal_data["reference"],
                "reference": withdrawal_data["reference"],
                "net_amount": str(withdrawal_data.get("net_amount", amount)),
                "fee": str(withdrawal_data.get("fee", "0")),
                "status": "pending_admin",
            }), 200
        # ============================================================
        # 3. PREPARE PESAJET PAYLOAD  (CHANGED)
        # ============================================================
        merchant_reference = withdrawal_data["reference"]
        net_amount = withdrawal_data["net_amount"]

        if payment_type == "send_money":
            target_phone = recipient_phone
            tag = "send_money"
            print(f"💰 SENDING MONEY to recipient: {target_phone}")
        else:
            target_phone = phone_number
            tag = "customer_withdraw"
            print(f"💰 PROCESSING WITHDRAWAL for user: {target_phone}")

        # PesaJet expects canonical +256 format
        formatted_phone = target_phone.strip()
        if formatted_phone.startswith("0"):
            formatted_phone = "+256" + formatted_phone[1:]
        elif formatted_phone.startswith("+"):
            pass  # already E.164
        elif formatted_phone.startswith("256") and len(formatted_phone) == 12:
            formatted_phone = "+" + formatted_phone
        else:
            digits = re.sub(r"\D", "", formatted_phone)
            if len(digits) >= 9:
                formatted_phone = "+256" + digits[-9:]
            else:
                formatted_phone = "+256" + digits

        # Encode tag into reference (PesaJet reference max 255)
        reference = f"{merchant_reference}"

        # Detect provider from target phone
        provider = detect_provider(formatted_phone)

        payload = {
            "type": "DISBURSEMENT",
            "amount": int(float(net_amount)),          # min 1
            "phoneNumber": formatted_phone,            # +256 canonical
            "provider": provider,                      # mtn | airtel | sandbox
            "reference": reference,                    # up to 255 chars
            "idempotencyKey": merchant_reference,      # STABLE per withdrawal
        }

        print("🔹 PesaJet disbursement payload:", json.dumps(payload, indent=2))

        # ============================================================
        # 4. CALL PESAJET API  (CHANGED)
        # ============================================================
        headers = {
            "X-API-Key": os.environ.get("PESAJET_API_KEY"),
            "Content-Type": "application/json",
        }

        print(f"Calling PesaJet API for withdrawal {merchant_reference}", flush=True)

        response = requests.post(
            f"{PESAJET_BASE_URL}/api/v1/payments",
            json=payload,
            headers=headers,
            timeout=PESAJET_REQUEST_TIMEOUT,
        )

        print(f"PesaJet response status: {response.status_code}, body: {response.text}", flush=True)
        response.raise_for_status()
        pesajet_data = response.json()

        # ============================================================
        # 5. PROCESS PESAJET RESPONSE  (CHANGED)
        # ============================================================
        transaction_id = pesajet_data.get("transactionId")

        if transaction_id:
            from blueprints.withdraw_helpers import WithdrawalRecordManager
            WithdrawalRecordManager.update_status(
                withdrawal_data["withdrawal_id"],
                "processing",
                external_ref=transaction_id,
            )
            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Withdrawal request submitted successfully",
                "withdrawal_id": merchant_reference,
                "reference": merchant_reference,
                "external_reference": transaction_id,
                "net_amount": str(withdrawal_data.get("net_amount", amount)),
                "fee": str(withdrawal_data.get("fee", "0")),
                "status": (pesajet_data.get("status") or "PENDING").lower(),
            }), 200
        else:
            # 2xx but no transaction id — treat as failure
            error_msg = pesajet_data.get("message", "Disbursement not accepted")
            logger.error(f"PesaJet withdrawal not accepted: {error_msg}")

            WithdrawalProcessor.fail_withdrawal(
                withdrawal_data["withdrawal_id"],
                user_id,
                amount_decimal,
                withdrawal_data.get("balances", {}),
            )

            return jsonify({
                "success": False,
                "error": error_msg,
                "details": "Your funds have been refunded. Please try again.",
            }), 400

    # ============================================================
    # 6. ERROR HANDLING  (CHANGED)
    # ============================================================
    except requests.exceptions.HTTPError as e:
        status_code = None
        error_message = "Disbursement provider error"

        if e.response is not None:
            status_code = e.response.status_code
            try:
                body = e.response.json()
                # Handle both shapes: {error:{...}} (docs) and {message, error, statusCode} (real)
                if isinstance(body.get("error"), dict):
                    error_message = body["error"].get("message") or str(body)
                else:
                    error_message = body.get("message") or body.get("error") or e.response.text
            except Exception:
                error_message = e.response.text

        print(f"🔥 PesaJet disbursement HTTP error: {status_code} {error_message}", flush=True)

        # ============================================================
        # ⚠️ SAFETY: only refund on CLIENT errors (4xx), NOT on timeout/5xx.
        # A 5xx or timeout could mean the payout actually went out.
        # Instead mark PENDING_VERIFICATION and reconcile later.
        # ============================================================
        if status_code and 400 <= status_code < 500 and status_code != 409:
            # Genuine client error — safe to refund
            if "withdrawal_data" in locals():
                WithdrawalProcessor.fail_withdrawal(
                    withdrawal_data["withdrawal_id"],
                    user_id,
                    amount_decimal,
                    withdrawal_data.get("balances", {}),
                )
            return jsonify({
                "error": error_message,
                "details": "Your funds have been refunded. Please try again.",
            }), status_code

        # 409: idempotency conflict — the original transaction exists; fetch it
        if status_code == 409:
            return jsonify({
                "error": "Duplicate withdrawal detected",
                "details": "This withdrawal was already submitted. Check status before retrying.",
            }), 409

        # 5xx / timeout / unknown — do NOT refund; verify first
        if "withdrawal_data" in locals():
            from blueprints.withdraw_helpers import WithdrawalRecordManager
            WithdrawalRecordManager.update_status(
                withdrawal_data["withdrawal_id"],
                "pending_verification",  # add this status if not present
            )
            db.session.commit()

        return jsonify({
            "error": "Disbursement status uncertain",
            "details": "We could not confirm the payout. It will be verified automatically.",
        }), 502

    except requests.exceptions.RequestException as e:
        # Network error / timeout — same caution as above
        print(f"PesaJet network error: {str(e)}", flush=True)

        if "withdrawal_data" in locals():
            from blueprints.withdraw_helpers import WithdrawalRecordManager
            WithdrawalRecordManager.update_status(
                withdrawal_data["withdrawal_id"],
                "pending_verification",
            )
            db.session.commit()

        return jsonify({
            "error": "Disbursement status uncertain",
            "details": "We could not confirm the payout. It will be verified automatically.",
        }), 502

    except WithdrawalException as e:
        print(f"Withdrawal processing error: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        print(f"Unexpected error in withdrawal: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()

        if "withdrawal_data" in locals():
            WithdrawalProcessor.fail_withdrawal(
                withdrawal_data["withdrawal_id"],
                user_id,
                amount_decimal,
                withdrawal_data.get("balances", {}),
            )

        return jsonify({
            "error": "Withdrawal processing failed",
            "details": "Your funds have been refunded. Please try again.",
        }), 500

# ============================================================
# WITHDRAWAL CALLBACK - LIVEPAY
# ============================================================
@bp.route("/payments/withdrawal-callback", methods=['POST'])
def withdrawal_callback():
    """
    Handle LivePay withdrawal callback/webhook
    """
    
    print("=" * 60)
    print("📞 WITHDRAWAL CALLBACK RECEIVED")
    print("=" * 60)
    
    try:
        # Get callback data
        data = request.get_json(silent=True) or {}
        print(f"Callback data: {json.dumps(data, indent=2)}")
        
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        # ============================================================
        # 1. EXTRACT LIVEPAY DATA
        # ============================================================
        # Handle both possible structures
        reference = data.get("reference") or data.get("customer_reference")
        ext_uuid = data.get("internal_reference")
        
        # Determine success status
        success = data.get("success", False)
        status_text = data.get("status", "").lower()
        
        if status_text in ["success", "successful", "completed", "complete", "paid", "confirmed"]:
            success = True
            print(f"✅ Status indicates SUCCESS: {status_text}")
        elif status_text in ["failed", "cancelled", "expired", "rejected"]:
            success = False
            print(f"❌ Status indicates FAILURE: {status_text}")

        else:
            # Fallback to 'success' field if present
            success = data.get("success", False)
            print(f"⚠️ Unknown status '{status_text}', using success field: {success}")
        
        network = data.get("network") or data.get("provider")
        amount = data.get("amount")
        phone = data.get("msisdn") or data.get("phone_number")
        
        print(f"✅ Success: {success}")
        print(f"📌 Reference: {reference}")
        print(f"📌 Internal Reference: {ext_uuid}")
        print(f"📌 Network: {network}")
        print(f"📌 Phone: {phone}")
        print(f"📌 Amount: {amount}")
        print(f"📌 Status: {status_text}")
        
        if not reference and not ext_uuid:
            return jsonify({"error": "Missing reference"}), 400
        
        # ============================================================
        # 2. FIND WITHDRAWAL RECORD
        # ============================================================
        withdrawal = None
        
        if reference:
            withdrawal = Withdrawal.query.filter_by(reference=reference).first()
        
        if not withdrawal and ext_uuid:
            withdrawal = Withdrawal.query.filter_by(external_ref=ext_uuid).first()
        
        # Fallback: search by reference in external_ref or raw_response
        if not withdrawal and reference:
            withdrawal = Withdrawal.query.filter_by(external_ref=reference).first()
        
        if not withdrawal and reference:
            withdrawals = Withdrawal.query.filter(
                Withdrawal.raw_response.isnot(None),
                Withdrawal.raw_response.contains(reference)
            ).all()
            if withdrawals:
                withdrawal = withdrawals[0]
                print(f"✅ Found withdrawal via raw_response search: {withdrawal.id}")
        
        if not withdrawal:
            print(f"❌ No matching withdrawal for reference {reference} / {ext_uuid}")
            return jsonify({"status": "ignored"}), 200
        
        print(f"✅ Found withdrawal ID: {withdrawal.id}, Current status: {withdrawal.status}")
        
        # ============================================================
        # 3. PREVENT DUPLICATE PROCESSING
        # ============================================================
        if withdrawal.status in ['completed', 'failed', 'cancelled']:
            print(f"⚠️ Withdrawal already processed: {withdrawal.reference}")
            return jsonify({"status": "already_processed"}), 200
        
        # ============================================================
        # 4. PROCESS SUCCESSFUL WITHDRAWAL
        # ============================================================
        if success:
            withdrawal.status = "completed"
            withdrawal.completed_at = datetime.now(timezone.utc)
            withdrawal.external_ref = ext_uuid or withdrawal.external_ref
            withdrawal.raw_response = json.dumps(data)
            
            db.session.commit()
            
            print(f"✅ Withdrawal {withdrawal.id} completed successfully")
            
            # Create notification for user
            try:
                notification = Notification(
                    user_id=withdrawal.user_id,
                    message=f"Withdrawal of {withdrawal.net_amount:,.0f} UGX completed successfully. Reference: {withdrawal.reference}",
                    notification_type='withdrawal_completed',
                    is_read=False
                )
                db.session.add(notification)
                db.session.commit()
            except Exception as notif_error:
                logger.error(f"Failed to create notification: {notif_error}")
            
            return jsonify({
                "status": "ok",
                "message": "Withdrawal completed",
                "withdrawal_id": withdrawal.id,
                "reference": withdrawal.reference
            }), 200
        
        # ============================================================
        # 5. PROCESS FAILED WITHDRAWAL
        # ============================================================
        else:
            print(f"❌ Withdrawal failed - Status: {status_text}")
            
            # Get user for refund
            user = db.session.get(User, withdrawal.user_id)
            
            # Refund the user
            if user:
                from blueprints.withdraw_helpers import BalanceManager
                refund_success = BalanceManager.refund_withdrawal(user, {
                    "actual_deducted": str(withdrawal.actual_balance_deducted),
                    "wallet_deducted": str(withdrawal.wallet_balance_deducted)
                })
                print(f"Refund successful: {refund_success}")
            
            # Update withdrawal status
            withdrawal.status = "failed"
            withdrawal.updated_at = datetime.now(timezone.utc)
            withdrawal.raw_response = json.dumps(data)
            
            if data.get("message"):
                withdrawal.failure_reason = data.get("message")
            
            db.session.commit()
            
            print(f"❌ Withdrawal {withdrawal.id} marked as failed and refunded")
            
            # Create notification for user
            try:
                notification = Notification(
                    user_id=withdrawal.user_id,
                    message=f"Withdrawal failed: {data.get('message', 'Unknown error')}. Your funds have been refunded.",
                    notification_type='withdrawal_failed',
                    is_read=False
                )
                db.session.add(notification)
                db.session.commit()
            except Exception as notif_error:
                logger.error(f"Failed to create notification: {notif_error}")
            
            return jsonify({
                "status": "ok",
                "message": "Withdrawal marked as failed",
                "withdrawal_id": withdrawal.id,
                "reference": withdrawal.reference
            }), 200
    
    except Exception as e:
        logger.error(f"Withdrawal callback error: {e}", exc_info=True)
        print(f"❌ Callback error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

#=================================================================================================
#=================================================================================================

import logging
from flask import request, jsonify
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
#===================================================================================================
@bp.route("/withdraw/callback/", methods=["POST"])
def withdraw_callback_():
    print("MARZ WITHDRAW CALLBACK RECEIVED")
    
    try:
        data = request.get_json()
        print(f"RAW CALLBACK DATA: {json.dumps(data, indent=2)}")
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        # EXACT SAME LOGIC AS PAYMENT CALLBACK
        transaction = data.get("transaction", {})
        
        # Get references - SAME AS PAYMENT
        reference = (
            transaction.get("reference") or
            data.get("reference")  
        )
        provider_reference = data.get("provider_reference") or transaction.get("provider_reference")

        ext_uuid = transaction.get("uuid") or data.get("uuid")
        
        status = transaction.get("status", "").lower()
        print(f"🔄 MARZ WITHDRAW STATUS: {status}")
        print(f"🔍 Checking references: reference={reference}, ext_uuid={ext_uuid}")

        # SIMPLE SEARCH - SAME AS PAYMENT
        withdrawal = None
        
        # Try by reference (your UUID) first
        if reference:
            withdrawal = Withdrawal.query.filter_by(reference=reference).first()
            if withdrawal:
                print(f"✅ Found withdrawal by reference: {reference}")
        
        # Try by external UUID
        if not withdrawal and ext_uuid:
            withdrawal = Withdrawal.query.filter_by(external_ref=ext_uuid).first()
            if withdrawal:
                print(f"✅ Found withdrawal by external UUID: {ext_uuid}")

        if not withdrawal and provider_reference:
            withdrawal = Withdrawal.query.filter_by(reference=provider_reference).first()
            if withdrawal:
                print(f"✅ Found withdrawal by provider_reference: {provider_reference}")
        
        if not withdrawal:
            print(f"❌ No withdrawal found for reference={reference}")
            return jsonify({"status": "ignored"}), 200
    
        print(f"🎯 Processing withdrawal ID: {withdrawal.id}, current status: {withdrawal.status}")
        
        # Store MarzPay's reference if we don't have it
        if not withdrawal.external_ref and ext_uuid:
            withdrawal.external_ref = ext_uuid
            db.session.commit()
            print(f"💾 Stored external_ref: {ext_uuid}")
        
        # Process status (your existing logic)
        if withdrawal.status in ["completed", "failed"]:
            print(f"⏭️ Withdrawal {withdrawal.id} already {withdrawal.status}. Skipping.")
            return jsonify({"status": "ok"}), 200
        
        if status == 'completed':
            print(f"✅ Completing withdrawal ID: {withdrawal.id}")
            WithdrawalProcessor.complete_withdrawal(withdrawal.id, reference or ext_uuid)
        
        elif status in ['failed', 'rejected']:
            print(f"❌ Failing withdrawal ID: {withdrawal.id}")

            actual_deducted = withdrawal.actual_balance_deducted
            wallet_deducted = withdrawal.wallet_balance_deducted
            balance_details = {
                'actual_deducted': str(actual_deducted) if actual_deducted is not None else '0',
                'wallet_deducted': str(wallet_deducted) if wallet_deducted is not None else '0'
            }
            amount_decimal = Decimal(str(withdrawal.amount))

            print(f"   📊 Balance details for refund: {balance_details}")
            print(f"   💰 Amount (Decimal): {amount_decimal}")
            print(f"   👤 User ID: {withdrawal.user_id}")
            print(f"   📝 Withdrawal ID: {withdrawal.id}")
            WithdrawalProcessor.fail_withdrawal(withdrawal.id, withdrawal.user_id, amount_decimal, balance_details)
            print(f"✅ Withdrawal {withdrawal.id} marked as failed and refund initiated")
        
        return jsonify({"status": "callback processed"}), 200

    except Exception as e:
        print(f"💥 Error processing MarzPay callback: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Callback processing failed"}), 500
    
    # except Exception as e:
    #     print(f"💥 Error processing MarzPay callback: {e}")
    #     return jsonify({"error": "Callback processing failed"}), 500

#===============================================================================================================

@bp.route("/payments/withdraw/history", methods=["GET"])
def withdrawal_history():
    """
    Get user's withdrawal history
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401
    
    try:
        limit = request.args.get('limit', 10, type=int)
        withdrawals = WithdrawalQueryHelper.get_user_withdrawals(user_id, limit)
        
        withdrawal_list = []
        for withdrawal in withdrawals:
            withdrawal_list.append({
                'id': withdrawal.id,
                'amount': str(withdrawal.amount),
                'net_amount': str(withdrawal.net_amount) if withdrawal.net_amount else None,
                'fee': str(withdrawal.fee) if withdrawal.fee else None,
                'phone': withdrawal.phone,
                'status': withdrawal.status,
                'external_ref': withdrawal.external_ref,
                'external_txid': withdrawal.external_txid,
                'created_at': withdrawal.created_at.isoformat() if withdrawal.created_at else None,
                'updated_at': withdrawal.updated_at.isoformat() if withdrawal.updated_at else None
            })
        
        return jsonify({
            "success": True,
            "withdrawals": withdrawal_list,
            "total": len(withdrawal_list)
        }), 200
        
    except Exception as e:
        print(f"Error fetching withdrawal history: {str(e)}", flush=True)
        return jsonify({"error": "Failed to fetch withdrawal history"}), 500


@bp.route("/payments/withdraw/limits", methods=["GET"])
def withdrawal_limits():
    """
    Get withdrawal limits and configuration
    """
    return jsonify({
        "success": True,
        "limits": {
            "min_withdrawal": str(WithdrawalConfig.MIN_WITHDRAWAL),
            "max_withdrawal": str(WithdrawalConfig.MAX_WITHDRAWAL),
            "processing_fee_percent": str(WithdrawalConfig.PROCESSING_FEE_PERCENT),
            "hold_period_hours": WithdrawalConfig.HOLD_PERIOD_HOURS
        }
    }), 200


@bp.route("/payments/withdraw/<withdrawal_id>", methods=["GET"])
def get_withdrawal_status(withdrawal_id):
    """
    Get specific withdrawal status
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401
    
    try:
        withdrawal = Withdrawal.query.filter_by(
            id=withdrawal_id, 
            user_id=user_id
        ).first()
        
        if not withdrawal:
            return jsonify({"error": "Withdrawal not found"}), 404
        
        return jsonify({
            "success": True,
            "withdrawal": {
                'id': withdrawal.id,
                'amount': str(withdrawal.amount),
                'net_amount': str(withdrawal.net_amount) if withdrawal.net_amount else None,
                'fee': str(withdrawal.fee) if withdrawal.fee else None,
                'phone': withdrawal.phone,
                'status': withdrawal.status,
                'external_ref': withdrawal.external_ref,
                'external_txid': withdrawal.external_txid,
                'created_at': withdrawal.created_at.isoformat() if withdrawal.created_at else None,
                'updated_at': withdrawal.updated_at.isoformat() if withdrawal.updated_at else None
            }
        }), 200
        
    except Exception as e:
        print(f"Error fetching withdrawal status: {str(e)}", flush=True)
        return jsonify({"error": "Failed to fetch withdrawal status"}), 500

