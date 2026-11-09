import os, re, json, uuid, requests
from flask import jsonify, current_app, session
from models import db, Payment, PaymentStatus, PackageCatalog, TransactionType, Package
from datetime import datetime, timedelta, timezone
import logging
from typing import Tuple, Optional, Dict, Any
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = int(os.getenv('REQUEST_TIMEOUT_SECONDS', '60'))

LIVEPAY_BASE_URL = os.getenv('LIVEPAY_BASE_URL', 'https://livepay.me/api')



# Product catalog lives in splendour_catalog.py (single source of truth; the frontend's catalog.js is generated from it).
from blueprints.splendour_catalog import (
    CATALOG as express_PACKAGE_CATALOG,
    DAILY_DAYS, validate_investment, validate_deposit, public_catalog,
)

# Derived — do not hand-maintain
PACKAGE_MAP = {slug: pkg["display_name"] for slug, pkg in express_PACKAGE_CATALOG.items()}

ALLOWED_AMOUNTS = set(catalog["amount"] for catalog in express_PACKAGE_CATALOG.values())
PAYMENT_CHARGE = Decimal("0.00")


# ============================================================
# HELPER: GET LOCK BONUS
# ============================================================

def get_lock_bonus(package_key: str, lock_days: int) -> Tuple[float, Dict]:
    """Compatibility shim. Splendour lock plans have fixed terms and no bonus tiers."""
    catalog = express_PACKAGE_CATALOG.get(package_key)
    if not catalog:
        return 0.0, {}
    return 0.0, {"bonus_percentage": 0.0, "lock_days": lock_days, "is_locking": lock_days > 0, "max_bonus": 0.0}


def calculate_locked_returns(package_key: str, lock_days: int, amount: Decimal) -> Dict:
    """Compatibility shim: terms come from the catalog, never from the caller."""
    from blueprints.splendour_catalog import lock_details_for
    return lock_details_for(package_key) or {}


# ============================================================
# VALIDATE PAYMENT INPUT - UPDATED WITH LOCK SUPPORT
# ============================================================

def _api_error(err):
    body, status = err
    return jsonify(body), status


def _sync_catalog_row(catalog):
    """Get the PackageCatalog row for a catalog entry; create it, or bring a stale row back in line."""
    pkg_obj = PackageCatalog.query.filter_by(name=catalog["name"]).first()
    if not pkg_obj:
        pkg_obj = PackageCatalog(
            name=catalog["name"], amount=catalog["amount"], bonus_percentage=catalog["bonus_percentage"],
            duration_days=catalog["duration_days"], reward_description=catalog["reward_description"],
            features=catalog.get("features", {}), is_active=True)
        db.session.add(pkg_obj)
        db.session.flush()
        return pkg_obj
    wanted = {"amount": catalog["amount"], "bonus_percentage": catalog["bonus_percentage"],
              "duration_days": catalog["duration_days"], "reward_description": catalog["reward_description"],
              "features": catalog.get("features", {}), "is_active": True}
    for k, v in wanted.items():
        if getattr(pkg_obj, k) != v:
            setattr(pkg_obj, k, v)
    db.session.flush()
    return pkg_obj


def validate_payment_input(data):
    """
    Entry validator for POST /payments/initiate. Returns (validated, None) or (None, (response, status)).
      payment_type "deposit": {payment_type, amount >= 20000, phone 07XXXXXXXX}
      payment_type "package" (default): {product: <catalog key>, amount, lock_days?}. No phone, no
        payment method: products are bought with the user's balance. The client names a product;
        amount, rate, term and payout come from splendour_catalog, never from the request.
    """
    if not isinstance(data, dict):
        return None, _api_error(({"error": "Invalid request", "code": "BAD_REQUEST"}, 400))
    payment_type = str(data.get("payment_type", "package")).lower().strip()

    if payment_type == "deposit":
        v, e = validate_deposit(data)
        return (None, _api_error(e)) if e else (v, None)

    if payment_type != "package":
        return None, _api_error(({"error": "Invalid payment type.", "code": "PAYMENT_TYPE"}, 400))

    v, e = validate_investment(data)
    if e:
        return None, _api_error(e)
    try:
        v["package_obj"] = _sync_catalog_row(v["catalog"])
    except Exception as ex:
        logger.error("Catalog sync failed: %s", ex, exc_info=True)
        return None, _api_error(({"error": "Failed to prepare package", "code": "CATALOG_SYNC"}, 500))
    return v, None


# ============================================================
# CREATE PAYMENT RECORD - UPDATED WITH LOCK SUPPORT
# ============================================================

def create_payment_record(user, amount, phone, payment_type, package=None, lock_details=None):
    """Create a new Payment record with lock support."""
    
    print("=" * 60)
    print("💰 CREATING PAYMENT RECORD")
    print(f"User: {user.id}, Amount: {amount}, Lock: {lock_details}")
    print("=" * 60)
    
    reference = str(uuid.uuid4())
    
    # Determine transaction type
    if payment_type.upper() in ['CARD', 'MOBILE']:
        transaction_type = TransactionType.DEPOSIT
    elif payment_type == 'media_star':
        transaction_type = TransactionType.DEPOSIT
    else:
        try:
            transaction_type = TransactionType[payment_type.upper()]
        except KeyError:
            transaction_type = TransactionType.PACKAGE
    
    try:
        if isinstance(package, PackageCatalog):
            package_id = package.id
            pkg_obj = package
        else:
            package_id = None
            pkg_obj = None
        
        # Prepare features with lock details
        features = {}
        if lock_details:
            features["is_locking"] = True
            features["lock_days"] = lock_details.get("lock_days", 0)
            features["bonus_percentage"] = lock_details.get("bonus_percentage", 0)
            features["daily_rate"] = lock_details.get("daily_rate", 0)
            features["daily_return"] = float(lock_details.get("daily_return", 0))
            features["total_return"] = float(lock_details.get("total_return", 0))
        
        payment = Payment(
            user_id=user.id,
            reference=reference,
            amount=amount,
            currency="UGX",
            phone_number=phone,
            provider=None,
            status=PaymentStatus.PENDING.value,
            method="MarzPay",
            external_ref=None,
            idempotency_key=str(uuid.uuid4()),
            raw_response=None,
            payment_type=payment_type,
            transaction_type=transaction_type,
            package_catalog_id=package_id if isinstance(package, PackageCatalog) else package,
            package_catalog=pkg_obj if isinstance(package, PackageCatalog) else None,
            # Store lock details in raw_response or a new field
            features=features  # You'll need to add this column to Payment model
        )
        
        db.session.add(payment)
        db.session.flush()
        
        print(f"✅ Payment record created with ID: {payment.id}")
        print(f"📋 Features: {features}")
        print("=" * 60)
        
        return payment
        
    except Exception as e:
        logger.error(f"Error in create_payment_record: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# CREATE USER PACKAGE - UPDATED WITH LOCK SUPPORT
# ============================================================
def create_user_package(user, package_catalog: PackageCatalog, lock_details=None):
    """
    Create the user's Package after the amount has been paid.
      Daily plan: daily_bonus_rate = 0.03% (0.0003), runs DAILY_DAYS days.
      Lock plan:  no daily profit (daily_bonus_rate 0). The full payout (amount + profit) is parked in
                  wallet.locked_balance and Package.lock_earnings, and /wallet/transfer-locked moves it
                  to actual_balance once lock_end_date has passed.
    Does NOT commit: the caller (internal purchase route / webhook) commits, so a later failure rolls back everything.
    """
    if not package_catalog:
        raise ValueError("Invalid package catalog")

    is_lock = bool(lock_details and lock_details.get("is_locking"))
    lock_days = int(lock_details.get("lock_days", 0)) if is_lock else 0
    duration_days = lock_days if is_lock else int(package_catalog.duration_days or DAILY_DAYS)
    if is_lock:
        daily_rate = Decimal("0")
    else:
        daily_rate = Decimal(str(package_catalog.bonus_percentage)) / Decimal("100")   # 0.03 -> 0.0003

    now = datetime.now(timezone.utc)
    payout = Decimal(str(lock_details.get("total_return", 0))) if is_lock else Decimal("0")

    new_package = Package(
        user_id=user.id,
        catalog_id=package_catalog.id,
        package=package_catalog.name,
        type="purchased",
        status="active",
        package_amount=package_catalog.amount,
        daily_bonus_rate=daily_rate,
        total_bonus_paid=Decimal("0.00"),
        activated_at=now,
        expires_at=now + timedelta(days=duration_days),
        is_locked=is_lock,
        lock_start_date=now if is_lock else None,
        lock_end_date=(now + timedelta(days=lock_days)) if is_lock else None,
        lock_duration_days=lock_days,
        lock_bonus_rate=0,
        lock_daily_rate=0,
        machine_details={
            "product": package_catalog.name, "is_locking": True, "duration_days": duration_days,
            "lock_duration_days": lock_days, "total_return": float(payout),
            "profit": float(lock_details.get("profit", 0)),
        } if is_lock else {},
    )
    db.session.add(new_package)
    db.session.flush()

    if is_lock and payout > 0:
        if not user.wallet:
            from models import Wallet
            user.wallet = Wallet(user_id=user.id, balance=0, locked_balance=0)
            db.session.add(user.wallet)
            db.session.flush()
        user.wallet.locked_balance = float(Decimal(str(user.wallet.locked_balance or 0)) + payout)
        new_package.lock_earnings = float(payout)
        logger.info("Locked %s for user %s, matures %s", payout, user.id, new_package.lock_end_date)

    return new_package


def sync_package_catalog():
    """One-off / deploy-time: upsert every catalog product and deactivate old catalog rows.
    Existing user Packages keep their catalog_id, so history is untouched.  Run from `flask shell`."""
    names = set()
    for c in express_PACKAGE_CATALOG.values():
        _sync_catalog_row(c)
        names.add(c["name"])
    stale = PackageCatalog.query.filter(~PackageCatalog.name.in_(names)).all()
    for row in stale:
        row.is_active = False
    db.session.commit()
    return {"active": len(names), "deactivated": [r.name for r in stale]}


# ============================================================
# SEND TO MARZPAY - UPDATED
# ============================================================


PESAJET_BASE_URL = "https://payments.pesajet.com"
REQUEST_TIMEOUT_SECONDS = 30


def detect_provider(phone: str) -> str:
    if os.environ.get("PESAJET_SANDBOX") == "1":
        return "sandbox"
    p = phone.lstrip("+")
    if p.startswith(("25677", "25678", "25639", "25676", "25679")):
        print("MTN NUMBER DETECTED=========")
        return "mtn"
    if p.startswith(("25670", "25675", "25674", "25673")):
        print("AIRTEL NUMBER DETECTED========")
        return "airtel"
    raise ValueError(f"Cannot determine provider for {phone}")


def send_to_pesajet(payment, phone, amount, package=None, lock_details=None):
    """Initiate a COLLECTION request to PesaJet (REST)."""

    headers = {
        "X-API-Key": os.environ.get("PESAJET_API_KEY"),
        "Content-Type": "application/json",
    }

    # Encode package/lock context into reference (max 255 chars)
    reference = str(payment.reference)

    # E.164 format
    formatted_phone = phone
    if phone.startswith("0"):
        formatted_phone = "+256" + phone[1:]
    elif phone.startswith("256"):
        formatted_phone = "+" + phone
    elif not phone.startswith("+"):
        formatted_phone = "+256" + phone

    payload = {
        "type": "COLLECTION",
        "amount": int(amount),                      # min 1
        "phoneNumber": formatted_phone,             # canonical +256
        "provider": detect_provider(formatted_phone),
        "reference": reference,                     # up to 255 chars
        "idempotencyKey": str(payment.reference),   # STABLE per payment
    }

    print("🔹 PesaJet payload:", json.dumps(payload, indent=2))

    try:
        resp = requests.post(
            f"{PESAJET_BASE_URL}/api/v1/payments",
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        print("🔹 PesaJet status:", resp.status_code)
        print("🔹 PesaJet body:", resp.text)

        transaction_id = data.get("transactionId")
        if transaction_id:
            payment.status = (data.get("status") or "PENDING").lower()
            payment.external_ref = transaction_id
            payment.raw_response = json.dumps(data)
            return data, None
        else:
            payment.status = PaymentStatus.FAILED.value
            payment.raw_response = json.dumps(data)
            return None, {"error": "Payment request failed"}

    except requests.exceptions.HTTPError as e:
        status_code = None
        response_text = ""
        error_code = None
        error_message = "Payment provider error"
        request_id = None

        if e.response is not None:
            status_code = e.response.status_code
            response_text = e.response.text
            try:
                body = e.response.json()
                err = body.get("error") or {}
                error_code = err.get("code")
                error_message = err.get("message") or response_text
                request_id = err.get("requestId")
            except Exception:
                error_message = response_text

        print("🔥 PesaJet HTTP ERROR:", status_code, error_code, error_message)
        if request_id:
            print("   requestId:", request_id)

        payment.status = PaymentStatus.FAILED.value
        payment.raw_response = json.dumps(
            {"status_code": status_code, "error": response_text}
        )
        return None, {
            "error": error_message,
            "code": error_code,
            "status_code": status_code,
            "request_id": request_id,
        }

    except Exception as e:
        print(f"Unexpected error in send_to_pesajet: {e}")
        payment.status = PaymentStatus.FAILED.value
        payment.raw_response = json.dumps({"error": str(e)})
        return None, {"error": f"Payment error: {str(e)}"}

    
# ============================================================
# MARZ INNOVATIONS
# ============================================================

MARZ_BASE_URL = "https://wallet.wearemarz.com/api/v1"


def send_to_marzpay(payment, phone, amount, package=None):
    """Initiate payment request to MarzPay API."""
    headers = {
        "Authorization": f"Basic {os.environ.get('MARZ_AUTH_HEADER')}",
        "Content-Type": "application/json"
    }

    callback_url = get_callback_url()
    print("CALLBACK URL:", callback_url)

    if payment.payment_type == "package" and package:
        description = f"payment_for_{package.name}"
    elif payment.payment_type == "deposit":
        description = "account_deposit"
    elif payment.payment_type == "media_star":
        description = "media_star_subscription"
    else:
        description = "payment"

    print(f"Description: {description}")

    formatted_phone = phone
    if phone.startswith('0'):
        formatted_phone = "+256" + phone[1:]
    elif phone.startswith('256'):
        formatted_phone = "+" + phone

    marz_amount = amount_with_charge(amount)
    payload = {
        "phone_number": formatted_phone,
        "amount": int(marz_amount),
        "country": "UG",
        "reference": str(payment.reference),
        "callback_url": callback_url,
        "description": description
    }

    print("🔹 MarzPay payload:", json.dumps(payload, indent=2))

    try:
        resp = requests.post(
            f"{MARZ_BASE_URL}/collect-money",
            json=payload, headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS
        )
        resp.raise_for_status()
        marz_data = resp.json()
        print("🔹 MarzPay response status:", resp.status_code)
        print("🔹 MarzPay response body:", resp.text)

        status_map = {
            "confirmed": PaymentStatus.PENDING.value,
            "processing": PaymentStatus.PENDING.value,
            "approved": PaymentStatus.PENDING.value,
            "success": PaymentStatus.PENDING.value,
            "successful": PaymentStatus.PENDING.value,
            "completed": PaymentStatus.COMPLETED.value,
            "complete": PaymentStatus.COMPLETED.value,
            "pending": PaymentStatus.PENDING.value,
            "failed": PaymentStatus.FAILED.value,
            "cancelled": PaymentStatus.FAILED.value,
            "expired": PaymentStatus.FAILED.value,
            "rejected": PaymentStatus.FAILED.value
        }

        marz_status = marz_data.get("status", "pending").lower()
        mapped_status = status_map.get(marz_status, PaymentStatus.PENDING.value)

        payment.status = mapped_status
        payment.raw_response = json.dumps(marz_data)
        txn = (marz_data.get("data") or {}).get("transaction") or {}
        payment.external_ref = txn.get("uuid") or marz_data.get("transaction_id")

        return marz_data, None

    except requests.exceptions.HTTPError as e:
        response_text = ""
        status_code = None

        if e.response is not None:
            status_code = e.response.status_code
            response_text = e.response.text

        print("🔥 MarzPay HTTP ERROR")
        print("STATUS:", status_code)
        print("BODY:", response_text)

        payment.status = PaymentStatus.FAILED.value
        payment.raw_response = json.dumps({"status_code": status_code, "error": response_text})

        return None, {
            "error": "Payment provider rejected request",
            "status_code": status_code,
            "details": response_text
        }

    except requests.RequestException as e:
        print(f"MarzPay API Request Exception: {e}")
        payment.status = PaymentStatus.FAILED.value
        payment.raw_response = json.dumps({"error": str(e)})
        return None, jsonify({"error": f"Payment provider error: {str(e)}"})

    except Exception as e:
        print(f"Unexpected error in send_to_marzpay: {e}")
        payment.status = PaymentStatus.FAILED.value
        payment.raw_response = json.dumps({"error": str(e)})
        return None, jsonify({"error": "Unexpected payment error"})


# ============================================================
# PROVIDER SWITCHER
# ============================================================

PESAJET_MAX_AMOUNT = 200000


def send_payment(payment, phone, amount, package=None, lock_details=None):
    """Route to correct provider by amount."""
    try:
        amount_int = int(amount)
    except (TypeError, ValueError):
        return None, {"error": f"Invalid amount: {amount}"}

    if amount_int < PESAJET_MAX_AMOUNT:
        print(f"🔀 Routing UGX {amount_int:,} → PesaJet (< {PESAJET_MAX_AMOUNT:,})")
        return send_to_pesajet(payment=payment, phone=phone, amount=amount,
                               package=package, lock_details=lock_details)
    else:
        print(f"🔀 Routing UGX {amount_int:,} → Marz Innovations (>= {PESAJET_MAX_AMOUNT:,})")
        return send_to_marzpay(payment=payment, phone=phone, amount=amount, package=package)



# ============================================================
# AMOUNT WITH CHARGE
# ============================================================

def amount_with_charge(amount):
    amount = Decimal(str(amount))
    fee_amount = amount * PAYMENT_CHARGE
    final_amount = amount + fee_amount
    return final_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ============================================================
# GET CALLBACK URL
# ============================================================

def get_callback_url():
    """Return appropriate callback URL based on environment"""
    from flask import current_app
    
    if current_app.config.get('DEBUG'):
        ngrok_url = os.environ.get('NGROK_URL')
        print("NGROK URL IN .ENV:", ngrok_url)
        if ngrok_url:
            return f"{ngrok_url}/payments/callback"
        return None
    else:
        return "https://sandss.online/payments/callback"


# ============================================================
# CHECK PACKAGE FUNDS AVAILABILITY
# ============================================================

def check_package_funds_availability(user_id: int, package_amount: Decimal) -> Tuple[bool, str, Decimal]:
    """Check if user has sufficient funds (actual balance + mature wallet)"""
    from models import User
    from blueprints.withdraw_helpers import WithdrawalValidator
    
    user = db.session.get(User, user_id)
    if not user:
        return False, "User not found", Decimal('0')
    
    actual_balance = Decimal(str(user.actual_balance or 0))
    mature_wallet = WithdrawalValidator._get_mature_wallet_balance(user)
    total_available = actual_balance + mature_wallet
    
    if total_available >= package_amount:
        return True, "Sufficient funds", total_available
    else:
        return False, f"Insufficient funds. Need {package_amount:,.0f} UGX, have {total_available:,.0f} UGX", total_available


# ============================================================
# HANDLE EXISTING PAYMENT
# ============================================================

def handle_existing_payment(user, amount, payment_type):
    """Return existing pending payment object if available"""
    try:
        existing = Payment.query.filter_by(
            user_id=user.id,
            amount=amount,
            transaction_type=TransactionType[payment_type.upper()],
            status=PaymentStatus.PENDING.value
        ).first()
        return existing
    except Exception as e:
        logger.error(f"Error in handle_existing_payment: {str(e)}")
        return None
