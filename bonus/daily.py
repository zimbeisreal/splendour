

print("==============================================================================")
print("===================DAILY BONUS PROCESSOR CALLED===============================")
print("==============================================================================")
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, List, Optional, Tuple
from sqlalchemy.exc import SQLAlchemyError
import uuid
import logging
from extensions import db
from models import User, Wallet, Package, Bonus, Transaction, Notification
from sqlalchemy import text
import pytz

logger = logging.getLogger(__name__)

class BonusSecurityError(Exception):
    pass

class BonusValidationError(Exception):
    pass

TEST_MODE = True

class DailyBonusProcessor:
    """Daily bonus processor - handles both regular and locked packages with tier-specific rates"""
    
    # Standard package rates
    STANDARD_DAILY_RATE = Decimal("0.06")  # 5% daily for standard packages
    STANDARD_MAX_PAYOUT = Decimal("1.20")  # 75% max for standard packages
    
    # Locked package max payout (100% of package amount)
    LOCKED_MAX_PAYOUT = Decimal("1.40")
    
    BONUS_COOLDOWN_HOURS = 0
    FIRST_BONUS_WAIT_HOURS = 0
    HOLD_HOURS = 24
    PROCESS_WEEKDAYS_ONLY = True
    KAMPALA_TZ = pytz.timezone('Africa/Kampala')
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.current_time = None
        self.processed_count = 0
        self.errors = []
    
    # ============================================================
    # DATETIME HELPERS
    # ============================================================
    
    @staticmethod
    def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    
    @staticmethod
    def make_naive_if_needed(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    # ============================================================
    # WEEKDAY CHECK
    # ============================================================
    
    def is_weekday_in_kampala(self) -> bool:
        return True
        # try:
        #     now_utc = datetime.now(timezone.utc)
        #     now_kampala = now_utc.astimezone(self.KAMPALA_TZ)
        #     is_weekday = now_kampala.weekday() < 5
        #     logger.info(f"Kampala time: {now_kampala.strftime('%Y-%m-%d %H:%M:%S %Z')}, Weekday: {is_weekday}")
        #     return is_weekday
        # except Exception as e:
        #     logger.error(f"Error checking Kampala weekday: {e}. Defaulting to allow processing.")
        #     return True

    # ============================================================
    # LOCK STATUS HELPERS
    # ============================================================
    
    def is_package_locked(self, package: Package) -> bool:
        """Check if package is locked"""
        return getattr(package, 'is_locked', False)

    def is_lock_expired(self, package: Package) -> bool:
        """Check if lock period has expired"""
        if not self.is_package_locked(package):
            return False
        lock_end = getattr(package, 'lock_end_date', None)
        if not lock_end:
            return False
        lock_end_utc = self.ensure_utc(lock_end)
        return self.current_time > lock_end_utc

    def get_locked_balance(self, wallet: Wallet) -> Decimal:
        """Get locked balance from wallet"""
        return self.safe_decimal(getattr(wallet, 'locked_balance', Decimal("0")), "locked_balance")
    
    def get_package_daily_rate(self, package: Package) -> Decimal:
        """
        Get the correct daily bonus rate for a package.
        For locked packages: uses the tier-specific rate stored in lock_daily_rate.
        For standard packages: uses STANDARD_DAILY_RATE.
        """
        is_locked = self.is_package_locked(package)
        
        if not is_locked:
            print("PACKAGE IS UNLOCKED: DETECTED===================================")
            # Standard package - use standard rate
            return self.STANDARD_DAILY_RATE
        
        # ✅ LOCKED PACKAGE - Get tier-specific rate
        # Priority 1: Check lock_daily_rate field (set during package creation)
        if hasattr(package, 'lock_daily_rate') and package.lock_daily_rate:
            lock_rate = Decimal(str(package.lock_daily_rate))
            print(f"The daily rate for locked package is {lock_rate}")
            logger.info(f"🔒 Package {package.id} using lock_daily_rate: {lock_rate}%")
            return lock_rate / Decimal("100")
        
        # Priority 2: Check machine_details JSON
        if package.machine_details and package.machine_details.get('daily_rate'):
            lock_rate = Decimal(str(package.machine_details.get('daily_rate')))
            logger.info(f"🔒 Package {package.id} using machine_details daily_rate: {lock_rate}%")
            return lock_rate / Decimal("100")
        
        # Priority 3: Calculate from lock_duration_days (fallback)
        lock_days = package.lock_duration_days or 0
        tier_bonus_map = {
            7: 2.0,   # +2% → 8%
            14: 4.0,  # +4% → 10%
            28: 6.0,  # +6% → 12%
            56: 10.0  # +10% → 16%
        }
        bonus_percent = tier_bonus_map.get(lock_days, 0)
        print(f"the Bonus percent for locked machine is {bonus_percent}")
        total_rate = Decimal("6.0") + Decimal(str(bonus_percent))
        logger.info(f"🔒 Package {package.id} calculated rate from lock_days: {total_rate}%")
        return total_rate / Decimal("100")

    # ============================================================
    # DECIMAL HELPERS
    # ============================================================
    
    def safe_decimal(self, value, field_name: str) -> Decimal:
        if value is None:
            raise BonusValidationError(f"{field_name} cannot be None")
        try:
            if isinstance(value, (int, float, str)):
                return Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            elif isinstance(value, Decimal):
                return value.quantize(Decimal("0.01"), ROUND_HALF_UP)
            else:
                raise BonusValidationError(f"Invalid type for {field_name}: {type(value)}")
        except (InvalidOperation, ValueError, TypeError) as e:
            raise BonusValidationError(f"Decimal conversion failed for {field_name}: {e}")

    # ============================================================
    # VALIDATION METHODS
    # ============================================================
    
    def validate_user(self, user: User) -> bool:
        if not user:
            raise BonusSecurityError("User not found")
        if not user.is_active:
            raise BonusValidationError("User account is inactive")
        return True
    
    def validate_package_status(self, package: Package) -> bool:
        """Validate package status - handles lock expiry"""
        if not package:
            raise BonusValidationError("Package not found")
        
        if package.status != 'active':
            raise BonusValidationError(f"Package status is '{package.status}', not 'active'")
        
        if package.is_bonus_locked:
            raise BonusSecurityError("Package bonus is locked")
        
        if not package.activated_at:
            raise BonusValidationError("Package not activated")
        
        # Check expiration
        if package.expires_at:
            expires_at_utc = self.ensure_utc(package.expires_at)
            if self.current_time > expires_at_utc:
                package.status = 'expired'
                db.session.add(package)
                raise BonusValidationError("Package has expired")
        
        # Check if lock expired - auto-unlock
        if self.is_package_locked(package) and self.is_lock_expired(package):
            package.is_locked = False
            package.lock_end_date = None
            package.lock_duration_days = None
            # ✅ When unlocking, set daily_bonus_rate to standard
            package.daily_bonus_rate = self.STANDARD_DAILY_RATE
            logger.info(f"🔓 Package {package.id} lock expired - auto-unlocked")
            db.session.add(package)
        
        return True
    
    def validate_bonus_timing(self, package: Package) -> bool:
        current_utc = self.current_time
        activated_at_utc = self.ensure_utc(package.activated_at)
        
        if not package.last_bonus_date:
            first_bonus_time = activated_at_utc + timedelta(hours=self.FIRST_BONUS_WAIT_HOURS)
            if current_utc < first_bonus_time:
                hours_remaining = (first_bonus_time - current_utc).total_seconds() / 3600
                raise BonusValidationError(f"First bonus not yet available. {hours_remaining:.1f} hours remaining")
            return True
        
        last_bonus_utc = self.ensure_utc(package.last_bonus_date)
        if last_bonus_utc.date() == current_utc.date():
            raise BonusValidationError(f"Bonus already processed today")
        
        if package.next_bonus_date:
            next_bonus_utc = self.ensure_utc(package.next_bonus_date)
            if current_utc < next_bonus_utc:
                hours_remaining = (next_bonus_utc - current_utc).total_seconds() / 3600
                raise BonusValidationError(f"Bonus cooldown active. {hours_remaining:.1f} hours remaining")
        
        return True

    # ============================================================
    # BONUS CALCULATION - ✅ FIXED with tier-specific rates
    # ============================================================
    
    def validate_bonus_limits(self, package: Package) -> Tuple[Decimal, Decimal, Decimal]:
        """Calculate bonus limits - uses tier-specific rates for locked packages"""
        package_amount = self.safe_decimal(package.package_amount, "package_amount")
        current_total_paid = self.safe_decimal(package.total_bonus_paid or Decimal("0"), "total_bonus_paid")
        
        is_locked = self.is_package_locked(package)
        
        if is_locked:
            # ✅ Get the tier-specific daily rate
            daily_rate = self.get_package_daily_rate(package)
            # Locked packages get 100% max payout
            max_payout = package_amount
            rate_percent = (daily_rate * Decimal("100")).quantize(Decimal("0.01"), ROUND_HALF_UP)
            logger.info(f"🔒 Locked package {package.id} - Rate: {rate_percent}%, Max: {max_payout}")
        else:
            # Standard package: 5% daily, 75% max
            daily_rate = self.STANDARD_DAILY_RATE
            max_payout = (package_amount * self.STANDARD_MAX_PAYOUT).quantize(Decimal("0.01"), ROUND_HALF_UP)
        
        # Update max_bonus_amount if not set
        if not package.max_bonus_amount or package.max_bonus_amount != max_payout:
            package.max_bonus_amount = max_payout
        
        # Check if max payout reached
        if current_total_paid >= max_payout:
            package.status = 'completed'
            db.session.add(package)
            raise BonusValidationError("Maximum bonus payout reached")
        
        # Calculate daily bonus
        daily_bonus = (package_amount * daily_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
        
        # Apply remaining limit
        remaining_limit = max_payout - current_total_paid
        if daily_bonus > remaining_limit:
            daily_bonus = remaining_limit
        
        if daily_bonus <= Decimal("0"):
            raise BonusValidationError("No bonus available - limit reached")
        
        return daily_bonus, max_payout, remaining_limit

    # ============================================================
    # WALLET METHODS
    # ============================================================
    
    def get_user_wallet(self, user_id: int) -> Wallet:
        """Get or create user wallet"""
        wallet = Wallet.query.filter_by(user_id=user_id).first()
        if not wallet:
            naive_current = self.make_naive_if_needed(self.current_time)
            wallet = Wallet(
                user_id=user_id,
                balance=Decimal("0.0"),
                locked_balance=Decimal("0.0"),
                created_at=naive_current
            )
            db.session.add(wallet)
            db.session.flush()
            logger.info(f"Created wallet for user {user_id}")
        
        # Ensure locked_balance exists
        if not hasattr(wallet, 'locked_balance') or wallet.locked_balance is None:
            wallet.locked_balance = Decimal("0.0")
        
        return wallet


    # def update_wallet_balance(self, wallet: Wallet, amount: Decimal, is_locked: bool) -> None:
    #     """
    #     Model B: do NOT credit wallet.balance immediately.
    #     For LOCKED packages: still credit locked_balance (existing behavior — locked
    #     funds are already in a holding bucket and are released by the lock logic).
    #     For UNLOCKED packages: the amount is credited later by maturation
    #     (see mature_pending_bonuses). We only update wallet.updated_at here.
    #     """
    #     naive_current = self.make_naive_if_needed(self.current_time)
        
    #     if is_locked:
    #         # Locked packages already have their own "hold" semantics — keep as-is
    #         current_locked = self.get_locked_balance(wallet)
    #         wallet.locked_balance = current_locked + amount
    #         logger.info(f"🔒 Added {amount} to locked balance for wallet {wallet.id}")
    #     else:
    #         HOLD_HOURS = 24
    #         # Model B: defer the credit until mature. Nothing to do to wallet.balance.
    #         logger.info(f"⏳ Deferred credit of {amount} for wallet {wallet.id} (matures in {HOLD_HOURS}h)")
        
    #     wallet.updated_at = naive_current

    def update_wallet_balance(self, wallet: Wallet, amount: Decimal, is_locked: bool) -> None:
        """Update balance (regular or locked) based on package type"""
        naive_current = self.make_naive_if_needed(self.current_time)
        
        if is_locked:
            # Credit to locked balance
            current_locked = self.get_locked_balance(wallet)
            wallet.locked_balance = current_locked + amount
            logger.info(f"🔒 Added {amount} to locked balance for wallet {wallet.id}")
        else:
            # Credit to regular balance
            current_balance = self.safe_decimal(wallet.balance, "wallet_balance")
            wallet.balance = current_balance + amount
            logger.info(f"Added {amount} to regular balance for wallet {wallet.id}")
        
        wallet.updated_at = naive_current

    # ============================================================
    # UPDATE METHODS
    # ============================================================
    
    def update_package_after_bonus(self, package: Package, daily_bonus: Decimal) -> None:
        """Update package after successful bonus payment"""
        try:
            naive_current = self.make_naive_if_needed(self.current_time)
            naive_next = self.make_naive_if_needed(
                self.current_time + timedelta(hours=self.BONUS_COOLDOWN_HOURS)
            )
            
            package.last_bonus_date = naive_current
            package.next_bonus_date = naive_next
            package.bonus_count += 1
            package.total_days_paid += 1
            
            current_total = self.safe_decimal(package.total_bonus_paid or Decimal("0"), "total_bonus_paid")
            package.total_bonus_paid = current_total + daily_bonus
            
            if package.total_bonus_paid >= package.max_bonus_amount:
                package.status = 'completed'
                logger.info(f"Package {package.id} completed - max payout reached")
            
            package.updated_at = naive_current
            
        except Exception as e:
            raise BonusValidationError(f"Failed to update package: {e}")

    # ============================================================
    # TRANSACTION RECORDING
    # ============================================================
    
    def create_bonus_transaction(self, user_id: int, wallet_id: int, 
                                amount: Decimal, package_id: int, is_locked: bool = False) -> str:
        """Create audit trail for bonus payment"""
        try:
            naive_current = self.make_naive_if_needed(self.current_time)
            transaction_ref = f"BONUS-{uuid.uuid4().hex[:12].upper()}"
            
            # Create bonus record
            bonus = Bonus(
                user_id=user_id,
                package_id=package_id,
                type="daily",
                amount=amount,
                status="paid",
                paid_at=naive_current,
                created_at=naive_current
            )
            db.session.add(bonus)
            
            # Create transaction
            HOLD_HOURS = 24
            transaction_type = "bonus_credit_locked" if is_locked else "bonus_credit"
            transaction = Transaction(
                user_id=user_id,
                wallet_id=wallet_id,
                type=transaction_type,
                amount=amount,
                status="completed",
                matures_at=None,
                reference=transaction_ref,
                created_at=naive_current
                #features={'is_locked': is_locked}
            )
            db.session.add(transaction)
            
            # Create notification for significant amounts
            if amount >= Decimal("10000"):
                bucket = "Locked" if is_locked else "Available"
                notification = Notification(
                    user_id=user_id,
                    message=(
                        f"splendour · Daily yield credited\n"
                        f"Amount:   UGX {amount:,.0f}\n"
                        f"Bucket:   {bucket}\n"
                        f"Status:   Credited"
                    ),
                    notification_type='bonus',
                    is_read=False,
                    created_at=naive_current
)
                # lock_msg = " (locked)" if is_locked else ""
                # notification = Notification(
                #     user_id=user_id,
                #     message=f"💰 Daily bonus of UGX {amount:,.2f} added to your {'locked ' if is_locked else ''}wallet{lock_msg}!",
                #     notification_type='bonus',
                #     is_read=False,
                #     created_at=naive_current
                # )
                db.session.add(notification)
                logger.info(f"Bonus notification created for user {user_id}: {amount} (Locked: {is_locked})")
            
            return transaction_ref
            
        except Exception as e:
            raise BonusSecurityError(f"Failed to create bonus records: {e}")

    # ============================================================
    # SINGLE PACKAGE PROCESSING
    # ============================================================
    
    def process_single_package(self, package: Package, wallet: Wallet) -> Dict:
        """Process bonus for a single package"""
        package_result = {
            "package_name": package.package,
            "success": False,
            "bonus_amount": 0.0,
            "error": None,
            "transaction_ref": None
        }
        
        try:
            # Check if locked BEFORE validation
            is_locked = self.is_package_locked(package)
            
            # ✅ Get the daily rate for this package (tier-specific if locked)
            daily_rate = self.get_package_daily_rate(package)
            rate_percent = (daily_rate * Decimal("100")).quantize(Decimal("0.01"), ROUND_HALF_UP)
            logger.info(f"🔍 Package {package.id} - Locked: {is_locked}, Rate: {rate_percent}%")
            
            # Validate
            self.validate_package_status(package)
            self.validate_bonus_timing(package)
            daily_bonus, max_payout, remaining_limit = self.validate_bonus_limits(package)
            
            # Get old balance
            if is_locked:
                old_balance = self.get_locked_balance(wallet)
            else:
                old_balance = self.safe_decimal(wallet.balance, "wallet_balance")
            
            # Update correct balance
            self.update_wallet_balance(wallet, daily_bonus, is_locked)
            
            # Update package
            self.update_package_after_bonus(package, daily_bonus)
            
            # Get new balance
            if is_locked:
                new_balance = self.get_locked_balance(wallet)
            else:
                new_balance = self.safe_decimal(wallet.balance, "wallet_balance")
            
            # Create audit trail
            transaction_ref = self.create_bonus_transaction(
                package.user_id, wallet.id, daily_bonus, package.id, is_locked
            )
            
            package_result.update({
                "success": True,
                "bonus_amount": float(daily_bonus),
                "daily_rate": float(rate_percent),
                "transaction_ref": transaction_ref,
                "old_balance": float(old_balance),
                "new_balance": float(new_balance),
                "remaining_limit": float(remaining_limit - daily_bonus),
                "is_locked": is_locked
            })
            
            self.processed_count += 1
            logger.info(f"✅ Bonus paid for package {package.id}: {daily_bonus} (Rate: {rate_percent}%, Locked: {is_locked})")
            
        except (BonusValidationError, BonusSecurityError) as e:
            package_result["error"] = str(e)
            logger.warning(f"⚠️ Bonus skipped for package {package.id}: {e}")
        except Exception as e:
            package_result["error"] = f"Unexpected error: {str(e)}"
            logger.error(f"❌ Error processing package {package.id}: {e}")
        
        return package_result

    # ============================================================
    # MAIN PROCESSOR
    # ============================================================
    
    def process_user_bonus(self, user_id: int) -> Dict:
        """Main method to process daily bonus for a user"""
        response = {
            "success": False,
            "user_id": user_id,
            "total_bonus": 0.0,
            "wallet_balance": 0.0,
            "locked_balance": 0.0,
            "packages_processed": 0,
            "packages_successful": 0,
            "packages_failed": 0,
            "processed_packages": [],
            "timestamp": self.current_time.isoformat(),
            "error": None
        }

        db_session = db.session
        transaction_open = False

        try:
            transaction_open = True    
            # Validate user
            user = User.query.get(user_id)
            self.validate_user(user)
            
            # Get wallet
            wallet = self.get_user_wallet(user_id)
            initial_balance = self.safe_decimal(wallet.balance, "wallet_balance")
            initial_locked = self.get_locked_balance(wallet)
            
            # Get eligible packages with row locking
            db_session.execute(text("SET LOCAL lock_timeout = '5s'"))
            packages = (
                Package.query
                .filter_by(user_id=user_id, status='active')
                .filter(Package.is_locked == False)
                .with_for_update()
                .all()
            )
            
            if not packages:
                response.update({
                    "success": True,
                    "wallet_balance": float(initial_balance),
                    "locked_balance": float(initial_locked),
                    "message": "No active packages found"
                })
                transaction_open = False
                return response
            
            # Log locked packages found
            locked_packages = [p for p in packages if self.is_package_locked(p)]
            if locked_packages:
                logger.info(f"🔒 Found {len(locked_packages)} locked packages for user {user_id}")
                for p in locked_packages:
                    rate = self.get_package_daily_rate(p)
                    logger.info(f"  - {p.package}: {rate * 100}% daily, locked until {p.lock_end_date}")
            
            # Process pending notifications
            try:
                pending_packages = self.get_pending_packages_with_time(packages)
                if pending_packages:
                    self.create_pending_bonus_notifications(user_id, pending_packages)
            except Exception as e:
                logger.warning(f"Failed to process pending notifications: {e}")
            
            total_bonus = Decimal("0.00")
            total_locked_bonus = Decimal("0.00")
            processed_packages = []
            
            # Process each package
            for package in packages:
                result = self.process_single_package(package, wallet)
                processed_packages.append(result)
                
                if result["success"]:
                    bonus_amount = self.safe_decimal(result["bonus_amount"], "bonus_amount")
                    total_bonus += bonus_amount
                    if result.get("is_locked", False):
                        total_locked_bonus += bonus_amount
            
            successful_packages = [p for p in processed_packages if p["success"]]
            failed_packages = [p for p in processed_packages if not p["success"]]
            
            # Commit if we have successful processing
            if successful_packages:
                try:
                    if total_bonus > 0:
                        lines = [
                            "splendour · Daily yield posted",
                            f"Amount:   UGX {float(total_bonus):,.0f}",
                        ]
                        if total_locked_bonus > 0:
                            lines.append(f"Locked:   UGX {float(total_locked_bonus):,.0f}")
                        lines.append(f"Packages: {len(successful_packages)}")
                        lines.append("Status:   Credited")

                        notification = Notification(
                            user_id=user_id,
                            message="\n".join(lines),
                            notification_type='bonus',
                            is_read=False,
                            created_at=self.make_naive_if_needed(self.current_time)
                        )
                        db_session.add(notification)
                except Exception as e:
                    logger.warning(f"Failed to prepare notification: {e}")
                
                db_session.commit()
                transaction_open = False
            else:
                db_session.rollback()
                transaction_open = False
            
            # Prepare response
            final_balance = self.safe_decimal(wallet.balance, "wallet_balance")
            final_locked = self.get_locked_balance(wallet)
            
            response.update({
                "success": True,
                "total_bonus": float(total_bonus),
                "total_locked_bonus": float(total_locked_bonus),
                "wallet_balance": float(final_balance),
                "locked_balance": float(final_locked),
                "packages_processed": len(processed_packages),
                "packages_successful": len(successful_packages),
                "packages_failed": len(failed_packages),
                "processed_packages": processed_packages
            })

        except (BonusSecurityError, BonusValidationError) as e:
            db_session.rollback()
            transaction_open = False
            response["error"] = str(e)
            logger.error(f"Bonus processing failed for user {user_id}: {e}")
            
        except SQLAlchemyError as e:
            db_session.rollback()
            transaction_open = False
            if "lock_timeout" in str(e) or "could not obtain lock" in str(e):
                response["error"] = "System is busy. Please try again in a few moments."
                logger.warning(f"Lock timeout for user {user_id}: {e}")
            else:
                response["error"] = f"Database error: {str(e)}"
                logger.error(f"Database error processing bonus for user {user_id}: {e}")
            
        except Exception as e:
            db_session.rollback()
            transaction_open = False
            response["error"] = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error processing bonus for user {user_id}: {e}", exc_info=True)

        finally:
            if transaction_open:
                db_session.rollback()
                logger.warning(f"Forced rollback for user {user_id}")

        return response

    # ============================================================
    # PENDING BONUS NOTIFICATIONS
    # ============================================================
    
    def create_pending_bonus_notifications(self, user_id: int, packages_with_remaining_time: List[Tuple[Package, float]]) -> None:
        try:
            naive_current = self.make_naive_if_needed(self.current_time)
            if not packages_with_remaining_time:
                return
            
            packages_with_remaining_time.sort(key=lambda x: x[1])
            
            if len(packages_with_remaining_time) == 1:
                package, hours_left = packages_with_remaining_time[0]
                lock_info = " (locked)" if self.is_package_locked(package) else ""
                rate = self.get_package_daily_rate(package)
                message = f"⏰ Bonus pending for {package.package}{lock_info} at {rate*100}% daily. {hours_left:.1f} hours remaining."
            else:
                closest_package, closest_hours = packages_with_remaining_time[0]
                total_pending = len(packages_with_remaining_time)
                lock_info = " (locked)" if self.is_package_locked(closest_package) else ""
                rate = self.get_package_daily_rate(closest_package)
                message = f"⏰ {total_pending} package(s) have pending bonuses. Next bonus for {closest_package.package}{lock_info} available in {closest_hours:.1f} hours."
            
            # Avoid spam - check if similar notification exists in last 6 hours
            six_hours_ago = self.make_naive_if_needed(self.current_time - timedelta(hours=6))
            existing = Notification.query.filter(
                Notification.user_id == user_id,
                Notification.notification_type == 'bonus_pending',
                Notification.created_at >= six_hours_ago
            ).first()
            
            if existing:
                return
            
            notification = Notification(
                user_id=user_id,
                message=message,
                notification_type='bonus_pending',
                is_read=False,
                created_at=naive_current
            )
            db.session.add(notification)
            logger.info(f"Pending bonus notification created for user {user_id}")
            
        except Exception as e:
            logger.warning(f"Failed to create pending bonus notification: {e}")

    def get_pending_packages_with_time(self, packages: List[Package]) -> List[Tuple[Package, float]]:
        pending_packages = []
        current_utc = self.current_time
        
        for package in packages:
            try:
                if package.status != 'active' or package.is_bonus_locked:
                    continue
                
                # Check if max payout reached
                package_amount = self.safe_decimal(package.package_amount, "package_amount")
                
                if self.is_package_locked(package):
                    max_payout = package_amount  # 100%
                else:
                    max_payout = (package_amount * self.STANDARD_MAX_PAYOUT).quantize(Decimal("0.01"), ROUND_HALF_UP)
                
                current_paid = self.safe_decimal(package.total_bonus_paid or Decimal("0"), "total_bonus_paid")
                
                if current_paid >= max_payout:
                    continue
                
                # Calculate time until next bonus
                if not package.last_bonus_date:
                    activated_at_utc = self.ensure_utc(package.activated_at)
                    first_bonus_time = activated_at_utc + timedelta(hours=self.FIRST_BONUS_WAIT_HOURS)
                    if current_utc < first_bonus_time:
                        hours_left = (first_bonus_time - current_utc).total_seconds() / 3600
                        pending_packages.append((package, hours_left))
                else:
                    if package.next_bonus_date:
                        next_bonus_utc = self.ensure_utc(package.next_bonus_date)
                        if current_utc < next_bonus_utc:
                            hours_left = (next_bonus_utc - current_utc).total_seconds() / 3600
                            pending_packages.append((package, hours_left))
            except Exception as e:
                logger.warning(f"Error checking pending status for package {package.id}: {e}")
                continue
        
        return pending_packages

    # ============================================================
    # RUN METHOD
    # ============================================================
    @staticmethod
    def mature_pending_bonuses(user_id: int) -> Decimal:
        """
        Promote any pending bonus transactions whose matures_at has passed
        to completed, and credit the wallet. Returns amount matured.
        Idempotent — safe to call repeatedly.
        """
        return Decimal("0")
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)  # match your naive column
        
        pending = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.type.in_(['bonus_credit', 'bonus_credit_locked']),
            Transaction.status == 'pending',
            Transaction.matures_at <= now,
        ).all()
        
        if not pending:
            return Decimal("0")
        
        wallet = Wallet.query.filter_by(user_id=user_id).first()
        if not wallet:
            return Decimal("0")
        
        total = Decimal("0")
        for tx in pending:
            amount = Decimal(str(tx.amount))
            tx.status = 'completed'
            total += amount
            
            # Route to the right bucket
            if tx.type == 'bonus_credit_locked':
                wallet.locked_balance = (
                    Decimal(str(wallet.locked_balance or 0)) + amount
                )
            else:
                wallet.balance = (
                    Decimal(str(wallet.balance or 0)) + amount
                )
        
        db.session.commit()
        logger.info(f"Matured {len(pending)} bonuses for user {user_id}: UGX {total}")
        return total

    
    def run(self):
        """Entry point for external callers"""
        # Weekend check
        if self.PROCESS_WEEKDAYS_ONLY and not self.is_weekday_in_kampala():
            logger.info(f"Bonus processing skipped for user {self.user_id} - Weekend in Kampala")
            return {
                "success": True,
                "user_id": self.user_id,
                "total_bonus": 0.0,
                "wallet_balance": 0.0,
                "locked_balance": 0.0,
                "packages_processed": 0,
                "packages_successful": 0,
                "packages_failed": 0,
                "processed_packages": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": None,
                "message": "Bonus processing only available on weekdays (Monday-Friday)"
            }

        self.current_time = datetime.now(timezone.utc)
        self.processed_count = 0
        self.errors = []
        
        return self.process_user_bonus(self.user_id)