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

# ============================================================
# express PACKAGE CATALOG - COMPLETE
# ============================================================

# ============================================================
# express · EXPRESS · PACKAGE CATALOG
# Aligned with the frontend PRODUCTS array in static/js/profile.js
# ============================================================

express_PACKAGE_CATALOG = {
    # ── DAILY (frontend: 20%/day × 25 days, total = profit only) ──
    "daily_15k": {
        "name": "GOLD-Daily Withdraw",
        "display_name": "GOLD-Daily Withdraw",
        "amount": 15000,
        "bonus_percentage": 20.0,
        "duration_days": 25,
        "reward_description": "Earn UGX 3,000 per day for 25 days. Total profit: UGX 75,000.",
        "features": {
            "daily_profit": 3000,
            "total_profit": 75000,
            "total_returns": 75000,          # matches frontend `total` (profit only)
            "capital": 15000,                 # explicit, so payout code never guesses
            "daily_rate": 20.0,
            "total_rate": 500.0,              # 20% × 25
            "referral_bonus": 0,
            "support_level": "Daily",
            "machine_emoji": "",
        },
        "is_active": True,
        "is_locking_package": False,
        "locking_bonus_rate": 0.0,
        "machine_eligible": True,
        "machine_type": "daily",
        "lock_minimum_days": 0,
        "lock_maximum_days": 0,
        "lock_bonus_tiers": {},
    },
        "daily_30k": {
        "name": "DIAMOND-Daily Withdraw",
        "display_name": "DIAMOND-Daily Withdraw",
        "amount": 30000,
        "bonus_percentage": 20.0,
        "duration_days": 25,
        "reward_description": "Earn UGX 3,000 per day for 25 days. Total profit: UGX 75,000.",
        "features": {
            "daily_profit": 6000,
            "total_profit": 150000,
            "total_returns": 150000,          # matches frontend `total` (profit only)
            "capital": 30000,                 # explicit, so payout code never guesses
            "daily_rate": 20.0,
            "total_rate": 500.0,              # 20% × 25
            "referral_bonus": 0,
            "support_level": "Daily",
            "machine_emoji": "",
        },
        "is_active": True,
        "is_locking_package": False,
        "locking_bonus_rate": 0.0,
        "machine_eligible": True,
        "machine_type": "daily",
        "lock_minimum_days": 0,
        "lock_maximum_days": 0,
        "lock_bonus_tiers": {},
    },
    "daily_50k": {
        "name": "PLATINUM-Daily Withdraw",
        "display_name": "PLATINUM-Daily Withdraw",
        "amount": 50000,
        "bonus_percentage": 20.0,
        "duration_days": 25,
        "reward_description": "Earn UGX 10,000 per day for 25 days. Total profit: UGX 250,000.",
        "features": {
            "daily_profit": 10000, "total_profit": 250000, "total_returns": 250000,
            "capital": 50000, "daily_rate": 20.0, "total_rate": 500.0,
            "referral_bonus": 0, "support_level": "Daily", "machine_emoji": "",
        },
        "is_active": True, "is_locking_package": False, "locking_bonus_rate": 0.0,
        "machine_eligible": True, "machine_type": "daily",
        "lock_minimum_days": 0, "lock_maximum_days": 0, "lock_bonus_tiers": {},
    },
    "daily_100k": {
        "name": "BRONZE-Daily Withdraw",
        "display_name": "BRONZE-Daily Withdraw",
        "amount": 100000, "bonus_percentage": 20.0, "duration_days": 25,
        "reward_description": "Earn UGX 20,000 per day for 25 days. Total profit: UGX 500,000.",
        "features": {
            "daily_profit": 20000, "total_profit": 500000, "total_returns": 500000,
            "capital": 100000, "daily_rate": 20.0, "total_rate": 500.0,
            "referral_bonus": 0, "support_level": "Daily", "machine_emoji": "",
        },
        "is_active": True, "is_locking_package": False, "locking_bonus_rate": 0.0,
        "machine_eligible": True, "machine_type": "daily",
        "lock_minimum_days": 0, "lock_maximum_days": 0, "lock_bonus_tiers": {},
    },
    "daily_200k": {
        "name": "SILVER-Daily Withdraw",
        "display_name": "SILVER-Daily Withdraw",
        "amount": 200000, "bonus_percentage": 20.0, "duration_days": 25,
        "reward_description": "Earn UGX 40,000 per day for 25 days. Total profit: UGX 1,000,000.",
        "features": {
            "daily_profit": 40000, "total_profit": 1000000, "total_returns": 1000000,
            "capital": 200000, "daily_rate": 20.0, "total_rate": 500.0,
            "referral_bonus": 0, "support_level": "Daily", "machine_emoji": "",
        },
        "is_active": True, "is_locking_package": False, "locking_bonus_rate": 0.0,
        "machine_eligible": True, "machine_type": "daily",
        "lock_minimum_days": 0, "lock_maximum_days": 0, "lock_bonus_tiers": {},
    },

    # ── LOCK 3 DAYS (frontend: total = capital + profit) ──
    "lock_3d_54k": {
        "name": "BRONZE-LOCK",
        "display_name": "BRONZE-LOCK",
        "amount": 54000,
        "bonus_percentage": 83.0,          # 41,500 / 50,000
        "duration_days": 3,
        "reward_description": "Lock UGX 50,000 for 3 days. Total return: UGX 91,500.",
        "features": {
            "daily_profit": 0, "total_profit": 41500, "total_returns": 91500,
            "capital": 50000, "daily_rate": 0.0, "total_rate": 83.0,
            "referral_bonus": 0, "support_level": "3-Day", "machine_emoji": "",
        },
        "is_active": True, "is_locking_package": True, "locking_bonus_rate": 0.0,
        "machine_eligible": True, "machine_type": "locked",
        "lock_minimum_days": 3, "lock_maximum_days": 3, "lock_bonus_tiers": {},
    },
    "lock_3d_100k": {
        "name": "SILVER-LOCK",
        "display_name": "SILVER-LOCK",
        "amount": 100000,
        "bonus_percentage": 66.0,          # 66,000 / 100,000
        "duration_days": 3,
        "reward_description": "Lock UGX 100,000 for 3 days. Total return: UGX 166,000.",
        "features": {
            "daily_profit": 0, "total_profit": 66000, "total_returns": 166000,
            "capital": 100000, "daily_rate": 0.0, "total_rate": 66.0,
            "referral_bonus": 0, "support_level": "3-Day", "machine_emoji": "",
        },
        "is_active": True, "is_locking_package": True, "locking_bonus_rate": 0.0,
        "machine_eligible": True, "machine_type": "locked",
        "lock_minimum_days": 3, "lock_maximum_days": 3, "lock_bonus_tiers": {},
    },

    # ── LOCK 7 DAYS ──
    "lock_7d_76k": {
        "name": "GOLD-LOCK",
        "display_name": "GOLD-LOCK",
        "amount": 76000,
        "bonus_percentage": 122.86,        # 86,000 / 70,000
        "duration_days": 7,
        "reward_description": "Lock UGX 70,000 for 7 days. Total return: UGX 156,000.",
        "features": {
            "daily_profit": 0, "total_profit": 86000, "total_returns": 156000,
            "capital": 70000, "daily_rate": 0.0, "total_rate": 122.86,
            "referral_bonus": 0, "support_level": "7-Day", "machine_emoji": "",
        },
        "is_active": True, "is_locking_package": True, "locking_bonus_rate": 0.0,
        "machine_eligible": True, "machine_type": "locked",
        "lock_minimum_days": 7, "lock_maximum_days": 7, "lock_bonus_tiers": {},
    },
    "lock_7d_115k": {
        "name": "PLATINUM-LOCK",
        "display_name": "PLATINUM-LOCK",
        "amount": 115000,
        "bonus_percentage": 50.43,         # unchanged, matches frontend
        "duration_days": 7,
        "reward_description": "Lock UGX 115,000 for 7 days. Total return: UGX 173,000.",
        "features": {
            "daily_profit": 0, "total_profit": 58000, "total_returns": 173000,
            "capital": 115000, "daily_rate": 0.0, "total_rate": 50.43,
            "referral_bonus": 0, "support_level": "7-Day", "machine_emoji": "",
        },
        "is_active": True, "is_locking_package": True, "locking_bonus_rate": 0.0,
        "machine_eligible": True, "machine_type": "locked",
        "lock_minimum_days": 7, "lock_maximum_days": 7, "lock_bonus_tiers": {},
    },

    # ── LOCK 14 DAYS ──
    "lock_14d_153k": {
        "name": "VIP-LOCK",
        "display_name": "VIP-LOCK",
        "amount": 153000,
        "bonus_percentage": 56.0,          # unchanged, matches frontend
        "duration_days": 14,
        "reward_description": "Lock UGX 150,000 for 14 days. Total return: UGX 234,000.",
        "features": {
            "daily_profit": 0, "total_profit": 84000, "total_returns": 234000,
            "capital": 150000, "daily_rate": 0.0, "total_rate": 56.0,
            "referral_bonus": 0, "support_level": "14-Day", "machine_emoji": "",
        },
        "is_active": True, "is_locking_package": True, "locking_bonus_rate": 0.0,
        "machine_eligible": True, "machine_type": "locked",
        "lock_minimum_days": 14, "lock_maximum_days": 14, "lock_bonus_tiers": {},
    },
}

# Derived — do not hand-maintain
PACKAGE_MAP = {slug: pkg["display_name"] for slug, pkg in express_PACKAGE_CATALOG.items()}

ALLOWED_AMOUNTS = set(catalog["amount"] for catalog in express_PACKAGE_CATALOG.values())
PAYMENT_CHARGE = Decimal("0.00")


# ============================================================
# HELPER: GET LOCK BONUS
# ============================================================

def get_lock_bonus(package_key: str, lock_days: int) -> Tuple[float, Dict]:
    """
    Get lock bonus percentage and details for a package
    Returns: (bonus_percentage, details_dict)
    """
    catalog = express_PACKAGE_CATALOG.get(package_key)
    if not catalog:
        return 0.0, {}
    
    tiers = catalog.get("lock_bonus_tiers", {})
    bonus = tiers.get(lock_days, 0.0)
    
    return bonus, {
        "bonus_percentage": bonus,
        "lock_days": lock_days,
        "is_locking": lock_days > 0,
        "max_bonus": catalog.get("locking_bonus_rate", 0.0)
    }


# ============================================================
# HELPER: CALCULATE LOCKED RETURNS
# ============================================================

def calculate_locked_returns(package_key: str, lock_days: int, amount: Decimal) -> Dict:
    """
    Calculate returns for a locked package
    Returns: {
        "daily_rate": float,
        "daily_return": Decimal,
        "total_return": Decimal,
        "bonus_percentage": float,
        "lock_days": int
    }
    """
    catalog = express_PACKAGE_CATALOG.get(package_key)
    if not catalog:
        return {}
    
    base_rate = catalog.get("bonus_percentage", 6.0)
    bonus, _ = get_lock_bonus(package_key, lock_days)
    
    total_rate = base_rate + bonus
    daily_return = (Decimal(str(total_rate)) / Decimal("100")) * amount
    total_return = daily_return * Decimal(str(catalog.get("duration_days", 26)))
    
    return {
        "daily_rate": total_rate,
        "daily_return": daily_return,
        "total_return": total_return,
        "bonus_percentage": bonus,
        "lock_days": lock_days,
        "is_locking": lock_days > 0,
        "base_rate": base_rate,
        "duration_days": catalog.get("duration_days", 26)
    }


# ============================================================
# VALIDATE PAYMENT INPUT - UPDATED WITH LOCK SUPPORT
# ============================================================

def validate_payment_input(data):
    """Validate payment input with lock support for express."""
    
    print("=" * 60)
    print("🔍 VALIDATING PAYMENT INPUT")
    print(f"📥 Received data: {data}")
    print("=" * 60)
    
    # Extract fields
    product = data.get('product', '').lower().strip()
    amount = data.get('amount')
    phone = data.get('phone')
    lock_days = data.get('lock_days', 0)
    is_locking = data.get('is_locking', False)
    payment_method = data.get('payment_method', 'marz').lower()
    payment_type = data.get('payment_type', 'package').lower()

    if payment_type == "deposit":
        # Validate amount
        try:
            amount_int = int(amount) if amount else 0
        except (TypeError, ValueError):
            return None, (jsonify({"error": "Invalid amount"}), 400)
        
        if amount_int < 500:
            return None, (jsonify({"error": "Minimum deposit is UGX 500"}), 400)
        
        if amount_int > 10_000_000:
            return None, (jsonify({"error": "Maximum deposit is UGX 10,000,000"}), 400)
        
        # Validate phone
        phone_str = str(phone).strip().replace(' ', '') if phone else ''
        if len(phone_str) < 10 or not phone_str.isdigit():
            return None, (jsonify({"error": "Valid 10-digit phone number required"}), 400)
        
        return {
            "amount": amount_int,
            "phone": phone_str,
            "payment_type": "deposit",
        }, None
    
    # ============================================================
    # VALIDATE PHONE NUMBER
    # ============================================================
    if payment_method in ['mobile', 'marz']:
        if not phone:
            return None, (jsonify({"error": "Phone number required for mobile money"}), 400)
        
        # Clean phone number
        phone_str = str(phone).strip()
        if not phone_str or len(phone_str) < 10:
            return None, (jsonify({"error": "Valid 10-digit phone number required"}), 400)

   
    # ============================================================
    # VALIDATE AMOUNT
    # ============================================================
    try:
        amount_int = int(amount) if amount else 0
    except (TypeError, ValueError):
        return None, (jsonify({"error": f"Invalid amount format: {amount}"}), 400)
    
    if amount_int <= 0:
        return None, (jsonify({"error": "Amount must be greater than 0"}), 400)
    
    # ============================================================
    # VALIDATE PRODUCT
    # ============================================================
    if not product:
        return None, (jsonify({"error": "Product name required"}), 400)
    
    # Check if product exists in catalog
    catalog = express_PACKAGE_CATALOG.get(product)
    if not catalog:
        return None, (jsonify({"error": f"Product '{product}' not found"}), 404)
    
    # Validate amount matches catalog
    expected_amount = catalog.get("amount")
    if amount_int != expected_amount:
        return None, (jsonify({
            "error": f"Amount mismatch. Expected: {expected_amount}, Got: {amount_int}"
        }), 400)
    
    # ============================================================
    # VALIDATE LOCK DAYS
    # ============================================================
    lock_days_int = int(lock_days) if lock_days else 0
    
    if is_locking and lock_days_int > 0:
        # Check if package supports locking
        if not catalog.get("is_locking_package", False):
            return None, (jsonify({
                "error": f"Product '{product}' does not support locking"
            }), 400)
        
        # Validate lock days range
        min_days = catalog.get("lock_minimum_days", 7)
        max_days = catalog.get("lock_maximum_days", 56)
        
        if lock_days_int < min_days or lock_days_int > max_days:
            return None, (jsonify({
                "error": f"Lock days must be between {min_days} and {max_days}"
            }), 400)
        
        # Validate lock days are in tiers
        # Validate lock days are in tiers — only if tiers are defined
        tiers = catalog.get("lock_bonus_tiers", {})
        if tiers and lock_days_int not in tiers:
            return None, (jsonify({
                "error": f"Lock days must be one of: {list(tiers.keys())}"
            }), 400)
    
    # ============================================================
    # GET OR CREATE PACKAGE CATALOG IN DB
    # ============================================================
    pkg_obj = PackageCatalog.query.filter_by(
        name=catalog["name"]
    ).first()
    # ============================================================
# ONE-TIME PURCHASE — 1-Day 30K (lock_1d_30k)
# ============================================================

    if not pkg_obj:
        # Create package catalog entry if it doesn't exist
        try:
            pkg_obj = PackageCatalog(
                name=catalog["name"],
                amount=catalog["amount"],
                bonus_percentage=catalog["bonus_percentage"],
                duration_days=catalog["duration_days"],
                reward_description=catalog["reward_description"],
                features=catalog.get("features", {}),
                is_active=True
            )
            db.session.add(pkg_obj)
            db.session.flush()
            print(f"✅ Created new PackageCatalog: {catalog['name']}")
        except Exception as e:
            return None, (jsonify({"error": f"Failed to create package: {str(e)}"}), 500)
    # ============================================================
    # ONE-TIME PURCHASE — 1-Day 30K (lock_1d_30k)
    # ============================================================
    ONE_TIME_PRODUCTS = {"lock_1d_30k"}
    
    if product in ONE_TIME_PRODUCTS:
        user_id = session.get('user_id')
        if not user_id:
            return None, (jsonify({"error": "User not found"}), 400)
        
        already_owned = Package.query.filter_by(
            user_id=user_id,
            catalog_id=pkg_obj.id,
        ).first()
        
        if already_owned:
            return None, (jsonify({
                "error": (
                    "You have already purchased the 1-Day 30K package. "
                    "It can only be bought once per account."
                )
            }), 409)
    # ============================================================
    # CALCULATE RETURNS IF LOCKING
    # ============================================================
    # lock_details = None
    # if is_locking and lock_days_int > 0:
    #     lock_details = calculate_locked_returns(product, lock_days_int, Decimal(str(amount_int)))
    #     print(f"🔒 Lock details: {lock_details}")
    lock_details = None
    if is_locking and lock_days_int > 0:
        lock_details = calculate_locked_returns(product, lock_days_int, Decimal(str(amount_int)))
        
        # ✅ Override total_return with the frontend's inflated value if provided
        frontend_lock_total = data.get("lock_total")
        if frontend_lock_total:
            try:
                lock_details["total_return"] = float(Decimal(str(frontend_lock_total)))
                print(f"✅ Using frontend lock_total: {lock_details['total_return']}")
            except (ValueError, TypeError) as e:
                print(f"⚠️ Invalid lock_total from frontend: {frontend_lock_total} — {e}")
        
        print(f"🔒 Lock details: {lock_details}")

    
    # ============================================================
    # BUILD VALIDATED DATA
    # ============================================================
    validated_data = {
        "amount": amount_int,
        "phone": phone_str if phone else None,
        "product": product,
        "product_name": catalog["name"],
        "payment_type": payment_type,
        "payment_method": payment_method,
        "package_obj": pkg_obj,
        "catalog": catalog,
        "lock_days": lock_days_int,
        "is_locking": is_locking and lock_days_int > 0,
        "lock_details": lock_details
    }
    
    print(f"✅ Validation successful: {validated_data}")
    print("=" * 60)
    
    return validated_data, None


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
    """Create a new Package for a user after successful payment, with lock support."""
    
    if not package_catalog:
        raise ValueError("Invalid package catalog")
    
    print("=" * 60)
    print("📦 CREATING USER PACKAGE")
    print(f"User: {user.id}, Package: {package_catalog.name}")
    print(f"Lock Details: {lock_details}")
    print("=" * 60)
    
    package_amount = package_catalog.amount
    
    # Base catalog duration (fallback 26 days)
    duration_days = package_catalog.duration_days or 26
    
    # Lock duration
    lock_duration_days = 0
    if lock_details and lock_details.get("is_locking"):
        lock_duration_days = lock_details.get("lock_days", 0)
    
    # ✅ Package must outlive the lock — extend expiry if lock is longer
    #effective_duration_days = max(duration_days, lock_duration_days)
    effective_duration_days = lock_duration_days if lock_duration_days > 0 else duration_days
    # Calculate daily bonus rate
    if lock_details and lock_details.get("is_locking"):
        lock_daily_rate = lock_details.get("daily_rate", 6.0)
        daily_rate = lock_daily_rate / 100
        lock_bonus_rate = lock_details.get("bonus_percentage", 0)
    else:
        lock_daily_rate = 0
        daily_rate = package_catalog.bonus_percentage / 100 if package_catalog.bonus_percentage else 0.06
        lock_bonus_rate = 0
    
    now = datetime.now(timezone.utc)
    
    new_package = Package(
        user_id=user.id,
        catalog_id=package_catalog.id,
        package=package_catalog.name,
        type="purchased",
        status="active",
        package_amount=package_amount,
        daily_bonus_rate=Decimal(str(daily_rate)),
        total_bonus_paid=Decimal("0.00"),
        activated_at=now,
        expires_at=now + timedelta(days=effective_duration_days),   # ✅ uses effective duration
        # Lock fields
        is_locked=lock_details.get("is_locking", False) if lock_details else False,
        lock_start_date=now if lock_details and lock_details.get("is_locking") else None,
        lock_end_date=(
            now + timedelta(days=lock_duration_days)
            if lock_details and lock_details.get("is_locking")
            else None
        ),
        lock_duration_days=lock_duration_days,
        lock_bonus_rate=lock_details.get("bonus_percentage", 0) if lock_details else 0,
        lock_daily_rate=lock_daily_rate,
        machine_details={
            "product": package_catalog.name,
            "is_locking": lock_details.get("is_locking", False) if lock_details else False,
            "daily_rate": lock_details.get("daily_rate", 6.0) if lock_details else 6.0,
            "duration_days": effective_duration_days,        # ✅ what the package actually runs for
            "catalog_duration_days": duration_days,          # original catalog value
            "lock_duration_days": lock_duration_days,        # lock length
            "lock_bonus_rate": lock_bonus_rate,
            "total_return": float(lock_details.get("total_return", 0)) if lock_details else 0
        } if lock_details else {}
    )
    
    db.session.add(new_package)
    db.session.flush() 

    if lock_details and lock_details.get("is_locking"):
        lock_payout = Decimal(str(lock_details.get("total_return", 0)))
        if lock_payout > 0:
            if not user.wallet:
                from models import Wallet
                user.wallet = Wallet(user_id=user.id, balance=0, locked_balance=0)
                db.session.add(user.wallet)
                db.session.flush()
            
            current_locked = Decimal(str(user.wallet.locked_balance or 0))
            user.wallet.locked_balance = float(current_locked + lock_payout)
            new_package.lock_earnings = float(lock_payout)
            print(f"🔒 Credited {lock_payout} to locked balance; matures {new_package.lock_end_date}")

        db.session.commit()
    
    print(f"✅ Package created with ID: {new_package.id}")
    print(f"📋 Locked: {new_package.is_locked}")
    print(f"📋 Catalog Duration: {duration_days} days")
    print(f"📋 Lock Duration: {lock_duration_days} days")
    print(f"📋 Effective Expiry: {effective_duration_days} days")
    print(f"📋 Lock Daily Rate: {lock_daily_rate}%, Lock Bonus: {lock_bonus_rate}%")
    print("=" * 60)
    
    return new_package

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

PESAJET_MAX_AMOUNT = 10000


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
        return "https://skylineshop.online/payments/callback"


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