#==========================================================================
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import enum
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, Index, event, Numeric, text, DateTime, func
from extensions import db
from werkzeug.security import check_password_hash, generate_password_hash
from enum import Enum
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func
from typing import Optional


# ===========================================================
# ENUM DEFINITIONS
# ===========================================================


def utc_iso(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
def utc_iso(dt: Optional[datetime]) -> Optional[str]:
    dt = ensure_utc(dt)
    return dt.isoformat() if dt else None

class TransactionType(Enum):
    PACKAGE = "package"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    BONUS = "bonus"
    OTHER = "other"


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PENDING_ADMIN = "pending_admin"
    

class KycStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class BillUtilityType(enum.Enum):
    LIGHT = "LIGHT"
    NWSC = "NWSC"
    DSTV = "DSTV"
    GOTV = "GOTV"

class BillPaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


class BundleType(str, Enum):
    DATA = 'data'
    VOICE = 'voice'
    KIRABO = 'kirabo'
    INTERNATIONAL_VOICE = 'international_voice'
    SUPER = 'super'
    SMS = 'sms'
    REGIONAL = 'regional'
    
    @classmethod
    def get_label(cls, bundle_type):
        labels = {
            cls.DATA: 'Data Bundles',
            cls.VOICE: 'Voice Bundles',
            cls.KIRABO: 'Kirabo Bundles',
            cls.INTERNATIONAL_VOICE: 'International Voice',
            cls.SUPER: 'Super Bundles',
            cls.SMS: 'SMS Bundles',
            cls.REGIONAL: 'Regional Bundles'
        }
        return labels.get(bundle_type, bundle_type)
# ===========================================================
# BASE MIXIN FOR COMMON FIELDS
# ===========================================================

class BaseMixin:
    """Provides created_at and updated_at timestamps to inheriting models."""
    created_at = db.Column(
    DateTime(timezone=True),
    server_default=func.now()
    )

    updated_at = db.Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

# ===========================================================
# USER MODELS
# ===========================================================

class User(db.Model, BaseMixin):
    """Core user entity — one wallet, one profile, many transactions via wallet."""
    __tablename__ = 'users'
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=True, default="user", index=True)
    actual_balance = db.Column(db.Numeric(18, 2), default=0.00, server_default=text("0.00"))
    available_balance = db.Column(db.Numeric(18, 2), default=0.00, server_default=text("0.00"))
     
    profile_photo = db.Column(db.String(255), nullable=True)
    referred_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # ID of user who referred this user
    referral_code_used = db.Column(db.String(20), nullable=True)  # The referral code used during signup
    referral_code = db.Column(db.String(20), unique=True, nullable=True)  # User's own referral code
    referral_bonus_eligible = db.Column(db.Boolean, default=True)  # Track if user is eligible for referral bonuses

    # Rewards / Level system
    current_level = db.Column(db.Integer, nullable=False, default=0, index=True)
    rewards_last_claimed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    salary_last_paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    salary_first_earned_at = db.Column(db.DateTime(timezone=True), nullable=True)


    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)

    member_since = db.Column(db.DateTime(timezone=True), default=db.func.now())

    # Relationships
    profile = db.relationship('UserProfile', uselist=False, back_populates='user', cascade="all,delete-orphan")
    wallet = db.relationship('Wallet', uselist=False, back_populates='user', cascade="all,delete-orphan")
    referrals = db.relationship('Referral', back_populates='referrer', foreign_keys='Referral.referrer_id', overlaps="referrals_made")
    
    bonuses = db.relationship('Bonus', back_populates='user', lazy='dynamic')
    packages = db.relationship('Package', back_populates='user')
    
    # Add these new fields for network tracking
    network_depth = db.Column(db.Integer, default=0)  # User's depth in the network
    direct_referrals_count = db.Column(db.Integer, default=0)  # Count of direct referrals
    total_network_size = db.Column(db.Integer, default=0)  # Total downline size
    
    # Network performance metrics
    network_total_investment = db.Column(db.Numeric(18, 2), default=0)
    network_active_members = db.Column(db.Integer, default=0)
    last_network_calculation = db.Column(db.DateTime, nullable=True)

        # ADD THESE FIELDS:
    last_contacted_by_agent_id = db.Column(db.Integer, db.ForeignKey('sub_admins.id'), nullable=True)
    last_agent_contact_at = db.Column(db.DateTime(timezone=True), nullable=True)
    agent_followup_count = db.Column(db.Integer, default=0)
    
    # Relationships (add these)
   
    agent_contacts = db.relationship(
        'SubAdmin', 
        foreign_keys=[last_contacted_by_agent_id],  # Explicitly specify
        backref='contacted_users'
    )
    
    referral_bonuses = db.relationship(
    'ReferralBonus',
    foreign_keys='ReferralBonus.user_id',
    back_populates='user',
    lazy='dynamic'
)
    # Relationships
    network_ancestors = db.relationship(
        'ReferralNetwork',
        foreign_keys='ReferralNetwork.descendant_id',
        backref='descendant_user',
        lazy='dynamic'
    )
    network_descendants = db.relationship(
        'ReferralNetwork',
        foreign_keys='ReferralNetwork.ancestor_id',
        backref='ancestor_user',
        lazy='dynamic'
    )

    __table_args__ = (
    # For User
    Index('idx_user_phone', 'phone'),
    Index('idx_user_referral_code', 'referral_code')

    )
    
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    def get_or_create_lead(self):
        """Get existing lead or create one"""
        if hasattr(self, 'lead_profile') and self.lead_profile:
            return self.lead_profile
        return Lead.create_from_user(self)
        


    def to_dict(self, include_packages=True, include_bonus=True):
        """Serialize user for JSON responses with optimized queries."""
        print(f"DEBUG to_dict: actual_balance={self.actual_balance}, available_balance={self.available_balance}")
        base_url = "https://sandss.online"
        referral_link = f"{base_url}?ref={self.referral_code}"         
        # 1. First create the basic dictionary
        result = {
            "id": self.id,
            "role": self.role,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "referralCode": self.referral_code,
            "referralLink": referral_link, 
            "memberSince": self.member_since.isoformat() if self.member_since else None,
            "isActive": self.is_active,
            "isVerified": self.is_verified,
            "actualBalance": float(self.actual_balance) if hasattr(self, 'actual_balance') else Decimal("0"),
            "availableBalance": float(self.available_balance) if hasattr(self, 'available_balance') else Decimal("0"),
        }
        total_bonus = self.referral_bonuses.filter_by(
            status="paid"
        ).with_entities(
            db.func.sum(ReferralBonus.bonus_amount)
        ).scalar() or 0

        result["referralBonus"] = float(total_bonus)

        if include_bonus and hasattr(self, 'bonuses'):
            # Since bonuses is a 'dynamic' relationship, it should work with filter_by
            try:
                result["bonus"] = float(self.bonuses.filter_by(status='active')
                                    .with_entities(db.func.sum(Bonus.amount))
                                    .scalar() or 0)
            except AttributeError:
                # Fallback to Python filtering if it's a list
                active_bonuses = [b for b in self.bonuses if getattr(b, 'status', None) == 'active']
                result["bonus"] = float(sum(b.amount for b in active_bonuses if hasattr(b, 'amount')))
        else:
            result["bonus"] = 0

            # ============================================================
        # ✅ PACKAGES WITH ACTIVE COUNT
        # ============================================================
        if include_packages and hasattr(self, 'packages'):
            # ✅ Get ALL packages (not just active) for counting
            all_packages = self.packages
            active_packages = [p for p in all_packages if getattr(p, 'status', None) == 'active']
            
            # ✅ Count active packages
            active_count = len(active_packages)
            
            # ✅ Add active count to result
            result["active_packages_count"] = active_count  # ✅ ADD THIS LINE
            result["total_packages"] = len(all_packages)    # ✅ Add total too
            
            # ✅ Build packages array
            result["packages"] = [
                {
                    "id": p.id,
                    "name": p.catalog.name if p.catalog else getattr(p, 'package', 'Unknown'),
                    "amount": p.catalog.amount if p.catalog else None,
                    "status": getattr(p, 'status', 'unknown'),
                    "bonus_percentage": float(p.catalog.bonus_percentage) if p.catalog and p.catalog.bonus_percentage else 0,
                    "duration_days": p.catalog.duration_days if p.catalog else None,
                    "activated_at": utc_iso(p.activated_at),
                    "expires_at": utc_iso(p.expires_at),
                    "days_remaining": (
                        (ensure_utc(p.expires_at) - datetime.now(timezone.utc)).days
                        if p.expires_at else None
                    ),
                    # ✅ Add extra fields for better frontend display
                    "is_locked": getattr(p, 'is_locked', False),
                    "lock_duration_days": getattr(p, 'lock_duration_days', 0),
                    "lock_daily_rate": float(getattr(p, 'lock_daily_rate', 0)) if getattr(p, 'lock_daily_rate', None) else 0,
                }
                for p in all_packages  # ✅ Include ALL packages (not just active)
            ]
        else:
            result["packages"] = []
            result["active_packages_count"] = 0
            result["total_packages"] = 0

       
        
        return result
   #========================================================
# USER PROFILE
# ===========================================================

class UserProfile(db.Model, BaseMixin):
    __tablename__ = 'user_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    full_name = db.Column(db.String(150))
    national_id = db.Column(db.String(50), index=True)
    address = db.Column(db.String(255))
    kyc_status = db.Column(db.Enum(KycStatus), default=KycStatus.PENDING, nullable=True)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))

    user = db.relationship('User', back_populates='profile')

# ===========================================================
# WALLET & TRANSACTIONS
# ===========================================================

class Wallet(db.Model, BaseMixin):
    __tablename__ = 'wallets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    balance = db.Column(db.Numeric(precision=18, scale=2), nullable=False, default=0)
    currency = db.Column(db.String(10), default='UGX')
    locked_balance = db.Column(db.Numeric(15, 2), default=0)

    user = db.relationship('User', back_populates='wallet')
    transactions = db.relationship('Transaction', back_populates='wallet', cascade="all,delete-orphan")

class Transaction(db.Model, BaseMixin):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallets.id', ondelete='CASCADE'), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False)  # deposit, withdrawal, bonus, referral, payment
    amount = db.Column(db.Numeric(precision=18, scale=2), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    reference = db.Column(db.String(120), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    phone_number = db.Column(db.String(15), nullable=True)
    purchase_type = db.Column(db.Text, nullable=True)
    bundle_id = db.Column(db.String(50), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    matures_at = db.Column(db.DateTime, nullable=True, index=True)

    wallet = db.relationship('Wallet', back_populates='transactions')

    user_id = db.Column(
    db.Integer,
    db.ForeignKey('users.id', ondelete='CASCADE'),
    nullable=False,
    index=True
)
    user = db.relationship('User', backref='transactions')
    Index('idx_transaction_created', 'created_at'),

# ===========================================================
# PAYMENTS & WITHDRAWALS
# ===========================================================

class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete='SET NULL'), nullable=True)
    package_catalog_id = db.Column(db.Integer, db.ForeignKey('packagecatalog.id'), nullable=True)
    reference = db.Column(db.String(128), nullable=False)
    
    transaction_type = db.Column(db.String(50)) 
    balance_type_used = db.Column(db.String(20), default=None)
    transaction_id = db.Column(
        db.Integer,
        db.ForeignKey('transactions.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    provider = db.Column(db.String(50))
    method = db.Column(db.String(50))
    external_ref = db.Column(db.String(128), index=True)
    idempotency_key = db.Column(db.String(128), index=True)
    features = db.Column(db.JSON, default={})
   
    verified = db.Column(db.Boolean, default=False)
    status = db.Column(db.Enum('pending', 'completed', 'failed', 'cancelled', 
                              name='paymentstatus'), nullable=False)
    currency = db.Column(db.String(8), nullable=False, default='UGX')
    amount = db.Column(db.Numeric(precision=10, scale=2), nullable=False)
    raw_response = db.Column(db.Text)
    phone_number = db.Column(db.String(32))
    payment_type = db.Column(db.String(50), default='package', nullable=False)

    user = db.relationship('User', backref=db.backref('payments', lazy=True))
    package_catalog = db.relationship('PackageCatalog', backref='payments')
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    purchase_id = db.Column(db.String(100), nullable=True)
    
    __table_args__ = (
       
        UniqueConstraint('reference', name='uq_payments_reference'),
        UniqueConstraint('idempotency_key', 'external_ref', name='uq_payments_idempotency_external'),
    )

class PackageCatalog(db.Model):
    __tablename__ = 'packagecatalog'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    reward_description = db.Column(db.Text)
    bonus_percentage = db.Column(db.Numeric(5, 2), default=0)
    duration_days = db.Column(db.Integer, default=30)
    features = db.Column(db.JSON)  
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = db.Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    display_name = db.Column(db.String(100), nullable=True)
    # ✅ NEW FIELDS FOR MACHINE LOCKING
    lock_bonus_tiers = db.Column(db.JSON, default={})
    is_locking_package = db.Column(db.Boolean, default=False)  # Is this a locking package?
    locking_duration_days = db.Column(db.Integer, nullable=True)  # Default lock duration
    locking_bonus_rate = db.Column(db.Numeric(5, 2), default=0)  # Extra % for locking
    machine_eligible = db.Column(db.Boolean, default=False)  # Can lock a machine?
    machine_type = db.Column(db.String(50), nullable=True)  # 'mining', 'staking', 'vps'
    daily_return_rate = db.Column(db.Numeric(5, 2), default=0)  # Daily return %
    total_return_rate = db.Column(db.Numeric(5, 2), default=0)  # Total return %
    lock_minimum_days = db.Column(db.Integer, default=7)  # Minimum lock period
    lock_maximum_days = db.Column(db.Integer, default=365)  # Maximum lock period

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'amount': self.amount,
            'reward_description': self.reward_description,
            'bonus_percentage': float(self.bonus_percentage) if self.bonus_percentage else 0,
            'duration_days': self.duration_days,
            'features': self.features or {},
            'is_active': self.is_active,
            'is_locking_package': self.is_locking_package,
            'locking_bonus_rate': float(self.locking_bonus_rate) if self.locking_bonus_rate else 0,
            'machine_eligible': self.machine_eligible,
            'machine_type': self.machine_type,
            'lock_minimum_days': self.lock_minimum_days,
            'lock_maximum_days': self.lock_maximum_days,
            'lock_bonus_tiers': self.lock_bonus_tiers or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Withdrawal(db.Model, BaseMixin):
    __tablename__ = 'withdrawals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))  
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True, index=True)
    destination = db.Column(db.String(255))  # mobile number or bank account
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    processed_at = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(50), default='pending')
    amount = db.Column(db.Numeric(precision=18, scale=2), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    fee = db.Column(db.Numeric(12,2), default=0)
    actual_balance_deducted = db.Column(db.Float, default=0.0)
    available_balance_deducted = db.Column(db.Float, default=0.0)

    wallet_balance_deducted = db.Column(db.Numeric(15, 2), default=0)
    previous_wallet_balance = db.Column(db.Numeric(15, 2), default=0)


    hold_period_applied = db.Column(db.Boolean, default=False) 
    reference = db.Column(db.String(255), nullable=True)
    external_ref = db.Column(db.String(128), index=True)
    net_amount = db.Column(db.Numeric(precision=18, scale=2), nullable=True)
    #provider_reference = db.Column(db.String(255), nullable=True)
    net_amount = db.Column(
    db.Numeric(18, 2),   # or db.DECIMAL(18, 2)
    nullable=True,
    index=True
)
    user = db.relationship('User', backref='withdrawals', foreign_keys=[user_id])


# ===========================================================
# BONUS & REFERRALS
# ===========================================================

class Bonus(db.Model, BaseMixin):
    __tablename__ = 'bonuses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    amount = db.Column(db.Numeric(precision=18, scale=2),  nullable=True)
    type = db.Column(db.String(50))  
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(
    DateTime(timezone=True),
    server_default=func.now()
)
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id'))
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)


    user = db.relationship('User', back_populates='bonuses')
   
#==========================================================================
#for temporary testing the dynamic admin dashboard

class Package(db.Model, BaseMixin):
    __tablename__ = 'packages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    catalog_id = db.Column(db.Integer, db.ForeignKey('packagecatalog.id', ondelete='SET NULL'), nullable=True)
    package = db.Column(db.String(50),  nullable=True)
    type = db.Column(db.String(50))  
    status = db.Column(db.String(20), default='active')
    package_amount = db.Column(db.Numeric(10, 2), nullable=False)  
    total_bonus_received = db.Column(db.Numeric(10, 2), default=0) 
    lock_daily_rate = db.Column(db.Numeric(5, 2), default=0)
    
    activated_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    expires_at = db.Column(
    DateTime(timezone=True),
    server_default=None,
    nullable=True
)

    daily_bonus_rate = db.Column(db.Numeric(10, 5), nullable=False, default=0.05)  
    total_bonus_paid = db.Column(db.Numeric(10, 2), default=0)

    # New columns for Package model
    last_bonus_date = db.Column(
    DateTime(timezone=True),
    nullable=True
)
    next_bonus_date = db.Column(
        DateTime(timezone=True),
        nullable=True
    )
    bonus_count = db.Column(db.Integer, default=0)
    max_bonus_amount = db.Column(db.Numeric(15, 2), default=0)  
    
    total_days_paid = db.Column(db.Integer, default=0)
    is_bonus_locked = db.Column(db.Boolean, default=False)

    

    # ✅ NEW FIELDS FOR MACHINE LOCKING
    is_locked = db.Column(db.Boolean, default=False)
    lock_start_date = db.Column(db.DateTime(timezone=True), nullable=True)
    lock_end_date = db.Column(db.DateTime(timezone=True), nullable=True)
    lock_duration_days = db.Column(db.Integer, nullable=True)
    lock_earnings = db.Column(db.Numeric(18, 2), default=0)  # Total earned from lock
    lock_bonus_rate = db.Column(db.Numeric(5, 2), default=0)  # Extra bonus rate
    
    # Machine details (store as JSON - no foreign key needed)
    machine_details = db.Column(db.JSON, default={})  # {type: 'mining', name: 'Miner-01', specs: {...}}
    machine_id = db.Column(db.String(50), nullable=True)
    
    user = db.relationship('User', back_populates='packages')
    catalog = db.relationship('PackageCatalog', backref='user_packages')

        # ✅ Fixed Indexes - Define as __table_args__
    __table_args__ = (
        db.Index('idx_package_user_status', 'user_id', 'status'),
        db.Index('idx_package_expires', 'expires_at'),
        db.Index('idx_package_user_locked', 'user_id', 'is_locked'),
        db.Index('idx_package_status_expires', 'status', 'expires_at'),
    )
    

    
    def to_dict(self, include_catalog=True):
        """Convert package to dictionary with full details."""
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "package": self.package,
            "type": self.type,
            "status": self.status,
            "package_amount": float(self.package_amount or 0),
            "total_bonus_received": float(self.total_bonus_received or 0),
            "activated_at": utc_iso(self.activated_at),
            "expires_at": utc_iso(self.expires_at),
            "daily_bonus_rate": float(self.daily_bonus_rate or 0),
            "total_bonus_paid": float(self.total_bonus_paid or 0),
            "bonus_count": self.bonus_count or 0,
            "total_days_paid": self.total_days_paid or 0,
            "is_locked": self.is_locked,
            "lock_start_date": utc_iso(self.lock_start_date),
            "lock_end_date": utc_iso(self.lock_end_date),
            "lock_duration_days": self.lock_duration_days,
            "lock_earnings": float(self.lock_earnings or 0),
            "lock_bonus_rate": float(self.lock_bonus_rate or 0),
            "machine_details": self.machine_details or {},
            "machine_id": self.machine_id,
            "created_at": utc_iso(self.created_at),
            "updated_at": utc_iso(self.updated_at)
        }
        
        # Include catalog data if available
        if include_catalog and self.catalog:
            result["catalog"] = {
                "id": self.catalog.id,
                "name": self.catalog.name,
                "display_name": self.catalog.display_name,
                "amount": self.catalog.amount,
                "duration_days": self.catalog.duration_days,
                "bonus_percentage": float(self.catalog.bonus_percentage or 0),
                "features": self.catalog.features or {},
                "daily_return_rate": float(self.catalog.daily_return_rate or 0),
                "total_return_rate": float(self.catalog.total_return_rate or 0),
                "machine_eligible": self.catalog.machine_eligible,
                "lock_bonus_tiers": self.catalog.lock_bonus_tiers or {},
                "is_locking_package": self.catalog.is_locking_package,
                "locking_bonus_rate": float(self.catalog.locking_bonus_rate or 0)
            }
            
            # Add computed progress
            result.update(calculate_package_progress(self))
            
        return result
    
    @property
    def is_expired(self):
        """Check if package is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)
    
    @property
    def days_remaining(self):
        """Get days remaining until expiry"""
        if not self.expires_at:
            return None
        now = datetime.utcnow()
        expiry = self.expires_at.replace(tzinfo=None)
        delta = expiry - now
        return max(0, delta.days)
    
    @property
    def total_return(self):
        """Calculate total return including bonuses"""
        if not self.package_amount:
            return 0
        return float(self.package_amount) + float(self.total_bonus_received)

    


# ===========================================================
# DATABASE EVENT LISTENERS (Python-level)
# ===========================================================

@event.listens_for(Package, 'after_insert')
def package_purchased_trigger(mapper, connection, target):
    """When a user buys a package, update lead status to converted"""
    # Use connection.execute() for raw SQL to avoid session conflicts
    from sqlalchemy.sql import text
    
    # Check if lead exists and not converted
    result = connection.execute(
        text("""
            SELECT id, assigned_agent_id FROM leads 
            WHERE user_id = :user_id AND is_converted = false
        """),
        {"user_id": target.user_id}
    ).first()
    
    if result:
        lead_id, assigned_agent_id = result
        
        # Update lead
        connection.execute(
            text("""
                UPDATE leads 
                SET is_converted = true, 
                    converted_at = :converted_at,
                    converted_package_id = :package_id,
                    lead_status = 'converted',
                    updated_at = :updated_at
                WHERE id = :lead_id
            """),
            {
                "converted_at": datetime.now(timezone.utc),
                "package_id": target.id,
                "lead_id": lead_id,
                "updated_at": datetime.now(timezone.utc)
            }
        )
        
        # Update agent's conversion counter
        if assigned_agent_id:
            connection.execute(
                text("""
                    UPDATE sub_admins 
                    SET conversions_today = conversions_today + 1,
                        updated_at = :updated_at
                    WHERE id = :agent_id
                """),
                {
                    "agent_id": assigned_agent_id,
                    "updated_at": datetime.now(timezone.utc)
                }
            )


@event.listens_for(User, 'after_insert')
def user_registration_trigger(mapper, connection, target):
    """Auto-create lead when user registers"""
    connection.execute(
        text("""
            INSERT INTO leads (user_id, phone, name, email, source_type, lead_status, created_at, updated_at)
            VALUES (:user_id, :phone, :username, :email, 'registration', 'new', :now, :now)
            ON CONFLICT (user_id) DO NOTHING
        """),
        {
            "user_id": target.id,
            "phone": target.phone,
            "username": target.username,
            "email": target.email,
            "now": datetime.now(timezone.utc)
        }
    )
def calculate_package_progress(package):
        """Calculate package progress."""
        if not package.activated_at:
            return {'days_active': 0, 'days_remaining': 0, 'progress': 0}
        
        now = datetime.now(timezone.utc)
        activated = ensure_utc(package.activated_at)
        days_active = max(0, (now - activated).days)
        
        duration = package.catalog.duration_days if package.catalog else 26
        progress = min((days_active / duration) * 100, 100) if duration > 0 else 0
        days_remaining = max(0, duration - days_active)
        
        return {
            'days_active': days_active,
            'days_remaining': days_remaining,
            'progress': progress
        }

class ReferralBonus(db.Model, BaseMixin):
    __tablename__ = 'referral_bonuses'  # Fixed table name
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.String(50))  # 'direct', 'indirect', 'level_bonus'
    status = db.Column(db.String(20), default='active')
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True, index=True)
    referred_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    level = db.Column(db.Integer, nullable=False)  # 1-20
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bonus_amount = db.Column(db.Numeric(10, 2), nullable=False)
    ancestor_id = db.Column(db.Integer, nullable=True)
    #amount = db.Column(db.Numeric(10, 2), nullable=True) 
   

    qualifying_amount = db.Column(db.Numeric(18, 2), nullable=False)  # Amount that triggered bonus
    bonus_percentage = db.Column(db.Numeric(5, 4), nullable=False)  # Actual percentage applied
    calculated_on = db.Column(db.DateTime, default=db.func.now())
    transaction_reference = db.Column(db.String(120), index=True)  # Link to original transaction
    security_hash = db.Column(db.String(128), unique=True, nullable=False, index=True)
    processing_id = db.Column(db.String(64), unique=False, nullable=True, index=True)
    threat_level = db.Column(db.String(50), default='low')

    
  
    network_path = db.Column(db.String(500))  # Store the referral path as string (e.g., "1->5->12")
    is_paid_out = db.Column(db.Boolean, default=False)
    paid_out_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship(
    'User',
    foreign_keys=[user_id],
    back_populates='referral_bonuses'
)
    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referral_earnings')
    referred_user = db.relationship('User', foreign_keys=[referred_id], backref='referred_by_me')
    payment = db.relationship('Payment', backref='referral_bonus')\
    
    __table_args__ = (
        Index('idx_bonus_level_payout', 'level', 'is_paid_out'),
        Index('idx_bonus_calculated', 'calculated_on'),
       db.UniqueConstraint('payment_id', 'user_id', 'level', name='unique_payment_user_level'),
    )
    

class Referral(db.Model, BaseMixin):
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True) # who referred
    referred_email = db.Column(db.String(120))
    referred_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True) # who was referred
    reward_issued = db.Column(db.Boolean, default=False)
    ReferralBonus = db.Column(db.Integer, default=0)
    
    status = db.Column(db.String(20), default='pending')  
    created_at = db.Column(
    DateTime(timezone=True),
    server_default=func.now()
)
    completed_at = db.Column(db.DateTime, nullable=True)

    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_made')
    referred = db.relationship('User', foreign_keys=[referred_id], backref='referrals_received')

    
# ===========================================================
# AUDITING & WEBHOOKS
# ===========================================================

class AuditLog(db.Model, BaseMixin):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    action = db.Column(db.String(255))
    ip_address = db.Column(db.String(50))

class WebhookEvent(db.Model, BaseMixin):
    __tablename__ = 'webhook_events'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)
    event_type = db.Column(db.String(100))
    payload = db.Column(db.JSON, nullable=False)
    signature = db.Column(db.String(255))
    reference = db.Column(db.String(120), index=True)
    processed = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(50), default='pending')
    remarks = db.Column(db.String(255))
    webhook_id = db.Column(db.String(64), unique=True, nullable=True, index=True)

    def mark_processed(self, success=True, remarks=None):
        self.processed = True
        self.status = 'success' if success else 'failed'
        self.remarks = remarks
        self.processed_at = datetime.now(timezone.utc)

# ===========================================================
# SUPPORT & SESSIONS
# ===========================================================

class SupportTicket(db.Model, BaseMixin):
    __tablename__ = 'support_tickets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    subject = db.Column(db.String(255))
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='open')

class LoginSession(db.Model, BaseMixin):
    __tablename__ = 'login_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    session_token = db.Column(db.String(255), unique=True, nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    device = db.Column(db.String(100))
    location = db.Column(db.String(120))
    logout_time = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, default=True)

    def end_session(self):
        self.is_active = False
        self.logout_time = datetime.now(timezone.utc)

class LoginAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ip_address = db.Column(db.String(45))
    success = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))

# ===========================================================
#   ------------IDEMPOTENCY KEY TRACKING
# ===========================================================

class IdempotencyKey(db.Model, BaseMixin):
    __tablename__ = 'idempotency_keys'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # models.py - Add to IdempotencyKey class
    withdrawal_id = db.Column(db.Integer, db.ForeignKey('withdrawals.id'), nullable=True)
    @staticmethod
    def make_expires(ttl_seconds: int = 3600):
        return datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    @staticmethod
    def cleanup_expired():
        """Remove expired idempotency keys."""
        now = datetime.now(timezone.utc)
        db.session.query(IdempotencyKey).filter(IdempotencyKey.expires_at < now).delete()
        db.session.commit()

class ReferralNetwork(db.Model, BaseMixin):
    """Tracks hierarchical relationships up to 20 levels"""
    __tablename__ = 'referral_network'
    
    id = db.Column(db.Integer, primary_key=True)
    ancestor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)  # Parent/upper level user
    descendant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)  # Child/lower level user
    depth = db.Column(db.Integer, nullable=False)  # Level distance (1-20)
    path_length = db.Column(db.Integer, nullable=False)  # Direct path length
    created_at = db.Column(
    DateTime(timezone=True),
    server_default=func.now()
)
    
    # Index for efficient tree traversal
    __table_args__ = (
        Index('idx_network_ancestor_depth', 'ancestor_id', 'depth'),
        Index('idx_network_descendant_ancestor', 'descendant_id', 'ancestor_id'),
        UniqueConstraint('ancestor_id', 'descendant_id', name='uq_network_relationship'),
            #-- Indexes for performance
 
    )

class ReferralBonusPlan(db.Model):
    """Configurable bonus percentages for each level (1-20)"""
    __tablename__ = 'referral_bonus_plan'
    
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.Integer, nullable=False, unique=True)  # 1 to 20
    bonus_percentage = db.Column(db.Numeric(5, 4), nullable=False)  # e.g., 0.10 for 10%
    minimum_qualifying_amount = db.Column(db.Numeric(18, 2), default=0)  # Min package amount to qualify
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(
    DateTime(timezone=True),
    server_default=func.now()
)
    
    __table_args__ = (
        db.CheckConstraint('level >= 1 AND level <= 20', name='chk_level_range'),
        db.CheckConstraint('bonus_percentage >= 0 AND bonus_percentage <= 1', name='chk_bonus_range'),
    )

class NetworkSnapshot(db.Model):
    """Periodic snapshots of network growth for analytics"""
    __tablename__ = 'network_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    snapshot_date = db.Column(db.Date, nullable=False, index=True)
    
    # Network metrics
    total_downline = db.Column(db.Integer, default=0)
    active_downline = db.Column(db.Integer, default=0)
    direct_referrals = db.Column(db.Integer, default=0)
    network_investment = db.Column(db.Numeric(18, 2), default=0)
    
    # Level-wise breakdown (store as JSON for flexibility)
    level_breakdown = db.Column(db.JSON)  # {1: 5, 2: 25, 3: 120, ...}
    
    __table_args__ = (
        UniqueConstraint('user_id', 'snapshot_date', name='uq_daily_snapshot'),
    )

class BonusPayoutQueue(db.Model):
    """Queue for processing bonus payouts"""
    __tablename__ = 'bonus_payout_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    referral_bonus_id = db.Column(db.Integer, db.ForeignKey('referral_bonuses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    attempt_count = db.Column(db.Integer, default=0)
    next_attempt = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text)
    processed_at = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_pqueue_status_attempt', 'status', 'next_attempt'),


    )
    
    def to_dict(self):
        """Convert activity to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'amount': float(self.amount) if self.amount is not None else 0.0,
            'currency': self.currency
        }
    
    def __repr__(self):
        return f'<Activity {self.id} {self.type} {self.title}>'
    
#================================================================================================================
class OTPRequest(db.Model):
    __tablename__ = "otp_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    otp_hash = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(50), index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_otp_phone_purpose', 'phone', 'purpose'),
        db.Index('idx_otp_expiry', 'expires_at'),
    )

# Index for better query performance
__table_args__ = (
    db.Index('idx_activities_timestamp_type', 'timestamp', 'type'),
    db.Index('idx_activities_user_timestamp', 'user_id', 'timestamp'),
)
class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notification_type = db.Column(db.String(50), default='general')
    
    # Relationship
    user = db.relationship('User', foreign_keys=user_id)
    
    def to_dict(self):
        return {
            'id': self.id,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
#=================================================================================================

class BillUtility(db.Model):
    """Cached utility metadata from MarzPay - your source of truth for frontend"""
    __tablename__ = 'bill_utilities'
    
    id = db.Column(db.Integer, primary_key=True)
    utility_code = db.Column(db.String(20), unique=True, nullable=False, index=True)  # LIGHT, NWSC, DSTV, GOTV
    utility_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    requires_area = db.Column(db.Boolean, default=False)
    requires_bouquet = db.Column(db.Boolean, default=False)
    requires_amount = db.Column(db.Boolean, default=True)  # DSTV/GOTV amount is fixed by bouquet
    is_active = db.Column(db.Boolean, default=True)
    
    # Store metadata as JSON (areas list for NWSC, bouquets for DSTV/GOTV)
    meta_data = db.Column(db.JSON, default={})
    
    # Sync tracking
    last_sync_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_bill_utility_active', 'is_active'),
        Index('idx_bill_utility_code_active', 'utility_code', 'is_active'),
    )
    
    def to_dict(self):
        """Return metadata for frontend"""
        return {
            'code': self.utility_code,
            'name': self.utility_name,
            'description': self.description,
            'requires_area': self.requires_area,
            'requires_bouquet': self.requires_bouquet,
            'requires_amount': self.requires_amount,
            'is_active': self.is_active,
            'areas': self.metadata.get('areas', []) if self.requires_area else None,
            'bouquets': self.metadata.get('bouquets', []) if self.requires_bouquet else None,
        }


class BillTransaction(db.Model):
    """Store all bill payment transactions - linked to user and payment"""
    __tablename__ = 'bill_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Core transaction data
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    utility_code = db.Column(db.String(20), nullable=False, index=True)
    meter_number = db.Column(db.String(100), nullable=False, index=True)
    
    # Payment details
    amount = db.Column(db.Numeric(18, 2), nullable=False)  # Original bill amount
    charge = db.Column(db.Numeric(18, 2), default=1500.00)  # MarzPay service charge
    total_amount = db.Column(db.Numeric(18, 2), nullable=False)  # amount + charge
    
    # Customer info from verification
    customer_name = db.Column(db.String(200), nullable=True)
    customer_ref = db.Column(db.String(100), nullable=True)
    outstanding_balance = db.Column(db.Numeric(18, 2), nullable=True)
    
    # Utility-specific fields
    area = db.Column(db.String(100), nullable=True)  # For NWSC
    bouquet_code = db.Column(db.String(50), nullable=True)  # For DSTV/GOTV
    bouquet_name = db.Column(db.String(100), nullable=True)
    
    # MarzPay tracking
    marz_reference = db.Column(db.String(128), unique=True, nullable=False, index=True)  # Your UUID
    marz_uuid = db.Column(db.String(128), nullable=True, index=True)  # Marz's internal UUID
    provider_reference = db.Column(db.String(128), nullable=True, index=True)
    
    # Status tracking
    status = db.Column(db.Enum(BillPaymentStatus), default=BillPaymentStatus.PENDING, nullable=False, index=True)
    verification_status = db.Column(db.String(20), nullable=True)  # Track if verification was done
    
    # Full response storage (for audit)
    verification_response = db.Column(db.JSON, nullable=True)  # Store verify API response
    payment_response = db.Column(db.JSON, nullable=True)  # Store payment API response
    
    # Link to your existing payment system
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Timestamps
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
 
    user = db.relationship('User', backref='bill_transactions')
    payment = db.relationship('Payment', backref='bill_transaction')
  
    __table_args__ = (
        Index('idx_bill_txn_user_status', 'user_id', 'status'),
        Index('idx_bill_txn_utility_meter', 'utility_code', 'meter_number'),
        Index('idx_bill_txn_created', 'created_at'),
        Index('idx_bill_txn_provider_ref', 'provider_reference'),
        UniqueConstraint('marz_reference', name='uq_bill_marz_ref'),
    )
    
    def to_dict(self):
        """Serialize for API responses"""
        return {
            'id': self.id,
            'utility_code': self.utility_code,
            'meter_number': self.meter_number,
            'amount': float(self.amount),
            'charge': float(self.charge),
            'total_amount': float(self.total_amount),
            'customer_name': self.customer_name,
            'area': self.area,
            'bouquet_code': self.bouquet_code,
            'bouquet_name': self.bouquet_name,
            'status': self.status.value if self.status else None,
            'marz_reference': self.marz_reference,
            'provider_reference': self.provider_reference,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class AirtimeDataCatalog(db.Model):
    """Root catalog metadata for airtime/data services"""
    __tablename__ = 'airtime_data_catalog'
    
    id = db.Column(db.Integer, primary_key=True)
    country = db.Column(db.String(2), nullable=False, default='UG')
    currency = db.Column(db.String(3), nullable=False, default='UGX')
    networks = db.Column(db.JSON, default=['MTN'])  # ['MTN']
    min_airtime_amount = db.Column(db.Integer, nullable=False, default=500)
    
    # Service status
    is_active = db.Column(db.Boolean, default=True)
    
    # Sync tracking
    last_sync_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        return {
            'country': self.country,
            'currency': self.currency,
            'networks': self.networks,
            'min_airtime_amount': self.min_airtime_amount,
            'is_active': self.is_active
        }


class AirtimeDataBundle(db.Model):
    """Individual MTN bundles (data, voice, combo)"""
    __tablename__ = 'airtime_data_bundles'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), unique=True, nullable=False, index=True)  # RACT_UG_Data_201
    bundle_name = db.Column(db.String(100), nullable=False)  # "Daily bundle of 165MB"
    bundle_type = db.Column(db.String(20), nullable=False, index=True)  # 'data', 'voice', 'combo'
    price = db.Column(db.Integer, nullable=False)  # Amount in UGX
    
    rtn = db.Column(db.Integer, nullable=True)  # MTN's internal code (present in all bundles)
    subcategory = db.Column(db.String(50), nullable=True)  # For regional bundles (e.g., "Greater Masaka")
    # Metadata
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    
    # Optional: store raw response for future parsing
    raw_data = db.Column(db.JSON, default={})
    
    # Sync tracking
    last_sync_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    #catalog_id = db.Column(db.Integer, db.ForeignKey('airtime_data_catalog.id'), nullable=True)
    __table_args__ = (
        Index('idx_bundle_type_active', 'bundle_type', 'is_active'),
        Index('idx_product_active', 'product_id', 'is_active'),
    )
    
    def to_dict(self):
        """Return bundle data for frontend"""
        return {
            'product_id': self.product_id,
            'name': self.bundle_name,
            'type': self.bundle_type,
            'price': self.price,
            'price_formatted': f"{self.price:,}",
            'currency': 'UGX',
            'description': self.description
        }
class SystemSetting(db.Model):
    """System configuration settings"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    setting_type = db.Column(db.String(50), default='string')
    description = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)   

# Add this to your models.py

class AdminAction(db.Model):
    """Audit log for admin actions"""
    __tablename__ = 'admin_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action_type = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    admin = db.relationship('User', foreign_keys=[admin_id])
    
    __table_args__ = (
        Index('idx_admin_actions_admin', 'admin_id'),
        Index('idx_admin_actions_target', 'target_type', 'target_id'),
        Index('idx_admin_actions_created', 'created_at'),
    )
# Add these indexes to ensure performance with large networks
additional_indexes = [
    # For network traversal
    Index('idx_network_ancestor_depth_desc', 'ancestor_id', 'depth', 'descendant_id'),
    Index('idx_network_descendant_depth', 'descendant_id', 'depth'),
    
    # For bonus calculations
    Index('idx_user_network_stats', 'user_id', 'total_network_size', 'network_total_investment'),
    Index('idx_bonus_calculation', 'level', 'status', 'calculated_on'),
    
    # For reporting
    Index('idx_snapshot_user_date', 'user_id', 'snapshot_date'),
]
#============================================================================
#===============SUB ADMIN MODELS FOR CUSTOMER SUPPORT STAFF==================
#===============================================================================

class SubAdmin(db.Model, BaseMixin):
    """Call center agent profile - extends User model"""
    __tablename__ = 'sub_admins'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    
    # Agent identification
    agent_code = db.Column(db.String(20), unique=True, nullable=False)  # e.g., "CC001"
    full_name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), default='customer_acquisition')
    
    # Performance tracking (daily counters)
    total_calls_today = db.Column(db.Integer, default=0)
    total_whatsapp_today = db.Column(db.Integer, default=0)
    total_sms_today = db.Column(db.Integer, default=0)
    conversions_today = db.Column(db.Integer, default=0)  # Leads that purchased packages
    failed_contacts_today = db.Column(db.Integer, default=0)
    
    # Settings
    daily_call_limit = db.Column(db.Integer, default=100)
    daily_whatsapp_limit = db.Column(db.Integer, default=100)
    daily_sms_limit = db.Column(db.Integer, default=100)
    
    # Status
    is_available = db.Column(db.Boolean, default=True)  # Online/offline for assignment
    last_activity_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = db.relationship(
        'User', 
        foreign_keys=[user_id],  # Explicitly tell SQLAlchemy which foreign key to use
        backref=db.backref('sub_admin_profile', uselist=False)
    )
    leads = db.relationship(
        'Lead', 
        foreign_keys='Lead.assigned_agent_id',  # Explicit: use assigned_agent_id
        backref='assigned_agent_rel',
        lazy='dynamic'
    )
    tasks = db.relationship('Task', backref='assigned_agent', lazy='dynamic')
    lead_notes = db.relationship(
        'LeadNote', 
        foreign_keys='LeadNote.agent_id',
        backref='agent_ref', 
        lazy='dynamic'
    )
    communications = db.relationship(
        'CommunicationLog', 
        foreign_keys='CommunicationLog.agent_id',
        backref='agent_ref', 
        lazy='dynamic'
    )

    actions = db.relationship(
        'SubAdminAction',
        foreign_keys='SubAdminAction.agent_id',
        backref='subadmin_agent',
        lazy='dynamic'
    )
    status_updated_leads = db.relationship(
        'Lead',
        foreign_keys='Lead.lead_status_updated_by',  # Explicit: use lead_status_updated_by
        backref='status_updater_rel',
        lazy='dynamic'
    )
    tasks = db.relationship(
        'Task', 
        foreign_keys='Task.assigned_to',
        backref='assigned_agent', 
        lazy='dynamic'
    )
    created_tasks = db.relationship(
        'Task',
        foreign_keys='Task.created_by',
        backref='creator',
        lazy='dynamic'
    )
    __table_args__ = (
        Index('idx_subadmin_agent_code', 'agent_code'),
        Index('idx_subadmin_department', 'department'),
        Index('idx_subadmin_availability', 'is_available'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'agent_code': self.agent_code,
            'full_name': self.full_name,
            'department': self.department,
            'total_calls_today': self.total_calls_today,
            'total_whatsapp_today': self.total_whatsapp_today,
            'total_sms_today': self.total_sms_today,
            'conversions_today': self.conversions_today,
            'is_available': self.is_available,
            'last_activity_at': utc_iso(self.last_activity_at),
            'username': self.user.username if self.user else None,
            'phone': self.user.phone if self.user else None,
        }
    
    def reset_daily_counters(self):
        """Reset daily counters - called by cron job at midnight"""
        self.total_calls_today = 0
        self.total_whatsapp_today = 0
        self.total_sms_today = 0
        self.conversions_today = 0
        self.failed_contacts_today = 0
        db.session.commit()

#======================================================================================
class LeadStatus:
    """Marketing status constants"""
    NEW = 'new'
    ASSIGNED = 'assigned'
    CONTACTED = 'contacted'
    VERY_INTERESTED = 'very_interested'
    INTERESTED = 'interested'
    NOT_INTERESTED = 'not_interested'
    ALREADY_CUSTOMER = 'already_with_package'
    INVALID_NUMBER = 'invalid_number'
    CONVERTED = 'converted'
    FOLLOWUP_SCHEDULED = 'followup_scheduled'
    BLACKLISTED = 'blacklisted'
    
    # Status configuration for UI
    STATUS_CONFIG = {
        NEW: {'color': 'gray', 'icon': '🆕', 'order': 1},
        ASSIGNED: {'color': 'blue', 'icon': '📋', 'order': 2},
        CONTACTED: {'color': 'green', 'icon': '📞', 'order': 3},
        VERY_INTERESTED: {'color': 'purple', 'icon': '🔥', 'order': 4},
        INTERESTED: {'color': 'cyan', 'icon': '👍', 'order': 5},
        NOT_INTERESTED: {'color': 'red', 'icon': '👎', 'order': 6},
        ALREADY_CUSTOMER: {'color': 'orange', 'icon': '✅', 'order': 7},
        INVALID_NUMBER: {'color': 'dark', 'icon': '❌', 'order': 8},
        CONVERTED: {'color': 'success', 'icon': '🎉', 'order': 9},
        FOLLOWUP_SCHEDULED: {'color': 'yellow', 'icon': '⏰', 'order': 10},
    }


class Lead(db.Model, BaseMixin):
    """Marketing lead - extends user data with conversion status"""
    __tablename__ = 'leads'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=True)
    assigned_agent_id = db.Column(db.Integer, db.ForeignKey('sub_admins.id'), nullable=True)
    
    # Lead source (automatic from registration)
    source_type = db.Column(db.String(50), default='registration')  # registration, referral, manual
    source_detail = db.Column(db.String(200))  # referral_code, campaign_name
    
    # Contact information (cached from User for quick access)
    phone = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    
    # Marketing status (YOUR REQUIRED STATUSES)
    lead_status = db.Column(db.String(50), default='new', index=True)
    lead_status_updated_at = db.Column(db.DateTime(timezone=True), default=func.now())
    lead_status_updated_by = db.Column(db.Integer, db.ForeignKey('sub_admins.id'), nullable=True)
    
    # Follow-up tracking
    last_contact_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_contact_method = db.Column(db.String(20))  # call, whatsapp, sms
    next_followup_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    followup_notes = db.Column(db.Text)
    followup_count = db.Column(db.Integer, default=0)
    
    # Interest scoring (calculated from interactions)
    interest_score = db.Column(db.Integer, default=0)  # 0-100
    
    # Conversion tracking
    is_converted = db.Column(db.Boolean, default=False, index=True)
    converted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    converted_package_id = db.Column(db.Integer, db.ForeignKey('packages.id'), nullable=True)
    
    # Blacklist
    is_blacklisted = db.Column(db.Boolean, default=False)
    blacklist_reason = db.Column(db.String(200))
    
    # User relationship
    user = db.relationship('User', backref=db.backref('lead_profile', uselist=False))
    
    # SubAdmin relationships - use foreign_keys to specify which column
    assigned_agent = db.relationship(
        'SubAdmin', 
        foreign_keys=[assigned_agent_id],
        backref='assigned_leads'
    )
    
    status_updater = db.relationship(
        'SubAdmin', 
        foreign_keys=[lead_status_updated_by],
        backref='status_updates'
    )
    
    # Package relationship
    converted_package = db.relationship('Package', foreign_keys=[converted_package_id])
    
    # Child relationships
    notes = db.relationship('LeadNote', backref='lead', lazy='dynamic', cascade='all,delete-orphan')
    tasks = db.relationship('Task', backref='lead', lazy='dynamic', cascade='all,delete-orphan')
    communications = db.relationship('CommunicationLog', backref='lead', lazy='dynamic', cascade='all,delete-orphan')
    __table_args__ = (
        Index('idx_lead_phone_status', 'phone', 'lead_status'),
        Index('idx_lead_assigned_agent', 'assigned_agent_id', 'lead_status'),
        Index('idx_lead_next_followup', 'next_followup_at'),
        Index('idx_lead_converted', 'is_converted'),
        Index('idx_lead_blacklisted', 'is_blacklisted'),
        Index('idx_lead_dashboard_filter', 'assigned_agent_id', 'lead_status', 'is_converted', 'created_at'),
    )
    
    @classmethod
    def create_from_user(cls, user, agent_id=None):
        """Create lead automatically when user registers"""
        lead = cls.query.filter_by(user_id=user.id).first()
        if lead:
            return lead
        
        lead = cls(
            user_id=user.id,
            phone=user.phone,
            name=user.username,
            email=user.email,
            source_type='registration',
            source_detail=f'user_registration_{user.id}',
            lead_status='new',
            assigned_agent_id=agent_id
        )
        db.session.add(lead)
        db.session.commit()
        return lead
    
    def update_status(self, new_status, agent_id, notes=None):
        """Update lead status with logging"""
        old_status = self.lead_status
        self.lead_status = new_status
        self.lead_status_updated_at = datetime.now(timezone.utc)
        self.lead_status_updated_by = agent_id
        
        # Log status change
        if notes:
            note = LeadNote(
                lead_id=self.id,
                agent_id=agent_id,
                note_type='status_change',
                note=notes,
                old_status=old_status,
                new_status=new_status
            )
            db.session.add(note)
        
        db.session.commit()
    
    def record_contact(self, method, agent_id, notes=None):
        """Record a contact attempt"""
        self.last_contact_at = datetime.now(timezone.utc)
        self.last_contact_method = method
        self.followup_count += 1
        
        if self.lead_status == 'new':
            self.lead_status = 'contacted'
            self.lead_status_updated_at = datetime.now(timezone.utc)
            self.lead_status_updated_by = agent_id
        
        if notes:
            note = LeadNote(
                lead_id=self.id,
                agent_id=agent_id,
                note_type='contact',
                note=notes
            )
            db.session.add(note)
        
        db.session.commit()
    
    def schedule_followup(self, followup_at, agent_id, notes=None):
        """Schedule a follow-up task"""
        self.next_followup_at = followup_at
        self.lead_status = 'followup_scheduled'
        self.lead_status_updated_at = datetime.now(timezone.utc)
        self.lead_status_updated_by = agent_id
        
        # Create follow-up task
        task = Task(
            lead_id=self.id,
            assigned_to=agent_id,
            created_by=agent_id,
            task_type='followup_call',
            title=f'Follow-up with {self.name or self.phone}',
            description=notes or 'Scheduled follow-up from previous contact',
            scheduled_for=followup_at,
            priority=2
        )
        db.session.add(task)
        
        if notes:
            note = LeadNote(
                lead_id=self.id,
                agent_id=agent_id,
                note_type='followup_scheduled',
                note=f"Follow-up scheduled for {followup_at.isoformat()}: {notes}"
            )
            db.session.add(note)
        
        db.session.commit()
        return task
    
    def mark_converted(self, package_id, agent_id):
        """Mark lead as converted (purchased package)"""
        self.is_converted = True
        self.converted_at = datetime.now(timezone.utc)
        self.converted_package_id = package_id
        self.lead_status = 'converted'
        self.lead_status_updated_at = datetime.now(timezone.utc)
        self.lead_status_updated_by = agent_id
        
        # Update agent's conversion counter
        agent = SubAdmin.query.get(agent_id)
        if agent:
            agent.conversions_today += 1
            db.session.add(agent)
        
        db.session.commit()
    
    def to_dict(self):
        """Serialize lead for API"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'phone': self.phone,
            'name': self.name,
            'email': self.email,
            'lead_status': self.lead_status,
            'status_config': LeadStatus.STATUS_CONFIG.get(self.lead_status, {}),
            'assigned_agent_id': self.assigned_agent_id,
            'assigned_agent_name': self.assigned_agent.full_name if self.assigned_agent else None,
            'last_contact_at': utc_iso(self.last_contact_at),
            'last_contact_method': self.last_contact_method,
            'next_followup_at': utc_iso(self.next_followup_at),
            'followup_count': self.followup_count,
            'interest_score': self.interest_score,
            'is_converted': self.is_converted,
            'converted_at': utc_iso(self.converted_at),
            'is_blacklisted': self.is_blacklisted,
            'source_type': self.source_type,
            'created_at': utc_iso(self.created_at),
            'updated_at': utc_iso(self.updated_at),
            # Include user data if available
            'user_balance': float(self.user.actual_balance) if self.user else 0,
            'has_active_package': any(p.status == 'active' for p in (self.user.packages if self.user else [])),
        }
#================================================================================
class LeadNote(db.Model, BaseMixin):
    """Notes added by agents on leads"""
    __tablename__ = 'lead_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('sub_admins.id'), nullable=False)
    
    note_type = db.Column(db.String(50), default='general')  # general, status_change, contact, followup, objection, payment
    note = db.Column(db.Text, nullable=False)
    is_private = db.Column(db.Boolean, default=False)  # Only visible to agent and admins
    created_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # For status change tracking
    old_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=True)
    
    __table_args__ = (
        Index('idx_lead_notes_lead', 'lead_id', 'created_at'),
        Index('idx_lead_notes_agent', 'agent_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'agent_id': self.agent_id,
          #  'agent_name': self.agent.full_name if self.agent else None,
            'note_type': self.note_type,
            'note': self.note,
            'is_private': self.is_private,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'created_at': utc_iso(self.created_at),
        }
#==================================================================================
class Task(db.Model, BaseMixin):
    """Follow-up tasks for agents"""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('sub_admins.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('sub_admins.id'), nullable=True)
    
    # Task details
    task_type = db.Column(db.String(50), nullable=False)  # followup_call, followup_whatsapp, send_document, verify_info
    priority = db.Column(db.Integer, default=2)  # 1=high, 2=medium, 3=low
    status = db.Column(db.String(20), default='pending', index=True)  # pending, in_progress, completed, cancelled, overdue
    
    # Content
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Scheduling
    scheduled_for = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reminder_sent = db.Column(db.Boolean, default=False)
    
    # Outcome
    outcome = db.Column(db.String(100))  # interested, not_interested, call_back_requested, etc.
    outcome_notes = db.Column(db.Text)
    
    __table_args__ = (
        Index('idx_tasks_assigned_status', 'assigned_to', 'status'),
        Index('idx_tasks_scheduled', 'scheduled_for', 'status'),
        Index('idx_tasks_lead', 'lead_id'),
    )
    
    @property
    def is_overdue(self):
        """Check if task is overdue"""
        if self.status != 'completed' and self.scheduled_for:
            return datetime.now(timezone.utc) > self.scheduled_for
        return False
    
    def complete(self, agent_id, outcome=None, notes=None):
        """Mark task as completed"""
        self.status = 'completed'
        self.completed_at = datetime.now(timezone.utc)
        self.outcome = outcome
        self.outcome_notes = notes
        
        # Update lead based on outcome
        if self.lead and outcome:
            if outcome == 'interested':
                self.lead.update_status('interested', agent_id, notes)
            elif outcome == 'not_interested':
                self.lead.update_status('not_interested', agent_id, notes)
            elif outcome == 'very_interested':
                self.lead.update_status('very_interested', agent_id, notes)
        
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'lead_phone': self.lead.phone if self.lead else None,
            'lead_name': self.lead.name if self.lead else None,
            'assigned_to': self.assigned_to,
            'agent_name': self.assigned_agent.full_name if self.assigned_agent else None,
            'task_type': self.task_type,
            'priority': self.priority,
            'status': self.status,
            'title': self.title,
            'description': self.description,
            'scheduled_for': utc_iso(self.scheduled_for),
            'completed_at': utc_iso(self.completed_at),
            'is_overdue': self.is_overdue,
            'outcome': self.outcome,
            'created_at': utc_iso(self.created_at),
        }
#=========================================================================================
class CommunicationLog(db.Model, BaseMixin):
    """Log all communication attempts (manual click-to-call/whatsapp/sms)"""
    __tablename__ = 'communication_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('sub_admins.id'), nullable=False)
    
    # Communication type (manual redirects)
    method = db.Column(db.String(20), nullable=False)  # call, whatsapp, sms
    direction = db.Column(db.String(10), default='outbound')
    
    # Simple logging (no external integration needed)
    status = db.Column(db.String(20), default='initiated')  # initiated, completed, failed
    duration_seconds = db.Column(db.Integer, nullable=True)  # Agent can optionally log call duration
    
    # Notes from agent
    agent_notes = db.Column(db.Text)
    outcome = db.Column(db.String(50))  # interested, not_interested, callback_requested, no_answer
    
    # For SMS (optional)
    message_preview = db.Column(db.String(200))  # First 200 chars of SMS
    template_used = db.Column(db.String(100))  # If using template
    
    __table_args__ = (
        Index('idx_comms_lead', 'lead_id', 'created_at'),
        Index('idx_comms_agent', 'agent_id', 'created_at'),
        Index('idx_comms_method', 'method'),
    )
    
    @classmethod
    def log_call(cls, lead_id, agent_id, notes=None, outcome=None, duration=None):
        """Log a manual call (click-to-call)"""
        log = cls(
            lead_id=lead_id,
            agent_id=agent_id,
            method='call',
            agent_notes=notes,
            outcome=outcome,
            duration_seconds=duration,
            status='completed'
        )
        db.session.add(log)
        
        # Update lead's last contact
        lead = Lead.query.get(lead_id)
        if lead:
            lead.record_contact('call', agent_id, notes)
            
            # Update agent's daily counter
            agent = SubAdmin.query.get(agent_id)
            if agent:
                agent.total_calls_today += 1
                db.session.add(agent)
        
        db.session.commit()
        return log
    
    @classmethod
    def log_whatsapp(cls, lead_id, agent_id, notes=None):
        """Log WhatsApp redirect (click-to-whatsapp)"""
        log = cls(
            lead_id=lead_id,
            agent_id=agent_id,
            method='whatsapp',
            agent_notes=notes,
            status='completed'
        )
        db.session.add(log)
        
        lead = Lead.query.get(lead_id)
        if lead:
            lead.record_contact('whatsapp', agent_id, notes)
            
            agent = SubAdmin.query.get(agent_id)
            if agent:
                agent.total_whatsapp_today += 1
                db.session.add(agent)
        
        db.session.commit()
        return log
    
    @classmethod
    def log_sms(cls, lead_id, agent_id, message=None, notes=None):
        """Log SMS (agent manually sends via phone)"""
        log = cls(
            lead_id=lead_id,
            agent_id=agent_id,
            method='sms',
            agent_notes=notes,
            message_preview=message[:200] if message else None,
            status='completed'
        )
        db.session.add(log)
        
        lead = Lead.query.get(lead_id)
        if lead:
            lead.record_contact('sms', agent_id, notes)
            
            agent = SubAdmin.query.get(agent_id)
            if agent:
                agent.total_sms_today += 1
                db.session.add(agent)
        
        db.session.commit()
        return log
    
    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'agent_id': self.agent_id,
            'agent_name': self.agent.full_name if self.agent else None,
            'method': self.method,
            'direction': self.direction,
            'status': self.status,
            'duration_seconds': self.duration_seconds,
            'agent_notes': self.agent_notes,
            'outcome': self.outcome,
            'message_preview': self.message_preview,
            'created_at': utc_iso(self.created_at),
        }
#======================================================================================
# Add to AdminAction model (or create SubAdminAction)
class SubAdminAction(db.Model, BaseMixin):
    __tablename__ = 'sub_admin_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('sub_admins.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=True)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    old_value = db.Column(db.String(200), nullable=True)
    new_value = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    agent = db.relationship(
        'SubAdmin', 
        foreign_keys=[agent_id]
    )
    
    __table_args__ = (
        Index('idx_subadmin_actions_agent', 'agent_id'),
        Index('idx_subadmin_actions_target', 'target_type', 'target_id'),
        Index('idx_subadmin_actions_created', 'created_at'),
    )
#====================================================================================
# Add to models.py

# models.py - Add this to your existing models

class Promoter(db.Model, BaseMixin):
    """Promoter/Marketeer Registration Model - Aligned with User model"""
    __tablename__ = 'promoters'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ============================================================
    # PERSONAL INFORMATION
    # ============================================================
    full_name = db.Column(db.String(200), nullable=False)
    nin = db.Column(db.String(20), nullable=False, unique=True, index=True)  # National ID
    phone_direct = db.Column(db.String(15), nullable=False, unique=True, index=True)
    phone_whatsapp = db.Column(db.String(15), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(200), nullable=False)
    
    # ============================================================
    # PROFESSIONAL INFORMATION
    # ============================================================
    previous_companies = db.Column(db.Text, nullable=True)
    promoted_products = db.Column(db.Text, nullable=False)
    experience_months = db.Column(db.String(20), nullable=False)  # '0-3', '3-6', '12-24', '24+'
    promoter_type = db.Column(db.String(50), nullable=False)  # 'individual', 'group_leader', 'agency', 'team_manager'
    team_size = db.Column(db.Integer, default=0)
    
    # ============================================================
    # EXPECTATIONS & AVAILABILITY
    # ============================================================
    expected_daily = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    expected_weekly = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    available_hours = db.Column(db.String(20), nullable=False)  # '2-3', '4-5', '6-8', '8+'
    preferred_areas = db.Column(db.Text, nullable=True)
    
    # ============================================================
    # SKILLS & COMPETENCIES
    # ============================================================
    skills = db.Column(db.JSON, default=[])  # ["sales", "social_media", "networking", "leadership"]
    
    # ============================================================
    # AUTHENTICATION
    # ============================================================
    password_hash = db.Column(db.String(255), nullable=True)  # For promoter login
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # ============================================================
    # STATUS
    # ============================================================
    status = db.Column(db.String(20), default='pending')  # 'pending', 'verified', 'rejected', 'suspended'
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejected_reason = db.Column(db.Text, nullable=True)
    
    # ============================================================
    # RELATIONSHIPS
    # ============================================================
    # Link to User (if promoter is also a system user)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('promoter_profile', uselist=False))
    
    # Promoter can have a referrer (who recruited them)
    referred_by = db.Column(db.Integer, db.ForeignKey('promoters.id'), nullable=True)
    referrer = db.relationship('Promoter', remote_side=[id], backref='referrals')
    
    # ============================================================
    # TIMESTAMPS (inherited from BaseMixin)
    # ============================================================
    # created_at, updated_at from BaseMixin
    
    # ============================================================
    # INDEXES
    # ============================================================
    __table_args__ = (
        Index('idx_promoter_phone_direct', 'phone_direct'),
        Index('idx_promoter_nin', 'nin'),
        Index('idx_promoter_status', 'status'),
        Index('idx_promoter_type', 'promoter_type'),
        Index('idx_promoter_user', 'user_id'),
        Index('idx_promoter_created', 'created_at'),
        UniqueConstraint('phone_direct', name='uq_promoter_phone'),
        UniqueConstraint('nin', name='uq_promoter_nin'),
    )
    
    # ============================================================
    # METHODS
    # ============================================================
    
    def set_password(self, password: str):
        """Set password hash"""
        from werkzeug.security import generate_password_hash
        if password:
            self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """Verify password"""
        from werkzeug.security import check_password_hash
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def activate(self):
        """Activate promoter account"""
        self.status = 'verified'
        self.is_active = True
        self.verified_at = datetime.now(timezone.utc)
    
    def reject(self, reason: str = None):
        """Reject promoter application"""
        self.status = 'rejected'
        self.is_active = False
        self.rejected_reason = reason
    
    def suspend(self, reason: str = None):
        """Suspend promoter account"""
        self.status = 'suspended'
        self.is_active = False
    
    def reactivate(self):
        """Reactivate promoter account"""
        self.status = 'verified'
        self.is_active = True
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.now(timezone.utc)
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'full_name': self.full_name,
            'nin': self.nin,
            'phone_direct': self.phone_direct,
            'phone_whatsapp': self.phone_whatsapp,
            'email': self.email,
            'location': self.location,
            'previous_companies': self.previous_companies,
            'promoted_products': self.promoted_products,
            'experience_months': self.experience_months,
            'promoter_type': self.promoter_type,
            'team_size': self.team_size,
            'expected_daily': float(self.expected_daily) if self.expected_daily else 0,
            'expected_weekly': float(self.expected_weekly) if self.expected_weekly else 0,
            'available_hours': self.available_hours,
            'preferred_areas': self.preferred_areas,
            'skills': self.skills or [],
            'status': self.status,
            'is_active': self.is_active,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'user_id': self.user_id,
            'referred_by': self.referred_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_public_dict(self):
        """Public-facing dictionary (excludes sensitive data)"""
        return {
            'id': self.id,
            'full_name': self.full_name,
            'phone_direct': self.phone_direct,
            'phone_whatsapp': self.phone_whatsapp,
            'email': self.email,
            'location': self.location,
            'promoter_type': self.promoter_type,
            'team_size': self.team_size,
            'status': self.status,
            'skills': self.skills or []
        }
    
    def __repr__(self):
        return f'<Promoter {self.full_name} ({self.phone_direct})>'

    @classmethod
    def find_by_phone(cls, phone: str):
        """Find promoter by phone number (direct or WhatsApp)"""
        return cls.query.filter(
            (cls.phone_direct == phone) | (cls.phone_whatsapp == phone)
        ).first()
    
    @classmethod
    def find_by_nin(cls, nin: str):
        """Find promoter by National ID"""
        return cls.query.filter_by(nin=nin).first()
    
    @classmethod
    def get_active_promoters(cls):
        """Get all active promoters"""
        return cls.query.filter_by(status='verified', is_active=True).all()

class RewardsLedger(db.Model, BaseMixin):
    __tablename__ = "rewards_ledger"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"))
    type = db.Column(db.String(32), nullable=False)  # level_up, reward_claim, salary_payout
    level = db.Column(db.Integer)
    amount = db.Column(db.Numeric(15, 2))
    period_start = db.Column(db.DateTime(timezone=True))
    period_end = db.Column(db.DateTime(timezone=True))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    user = db.relationship("User", backref="rewards_ledger")