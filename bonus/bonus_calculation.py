
# bonus/bonus_calculation.py
from decimal import Decimal
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timezone
from flask import current_app
from sqlalchemy import text
import hashlib
import json
import secrets

from models import Payment, User, ReferralBonus
from bonus.config import BonusConfigHelper

class BonusCalculationHelper:
    """
    Secure bonus calculation helper - now supports up to level 20
    """
    
    @staticmethod
    def calculate_all_bonuses_secure(payment: Payment) -> Tuple[bool, List[Dict], str, Dict[str, Any]]:
        """
        Calculate bonuses for all levels up to 20 with comprehensive security
        """
        try:
            print(f"🔍 DEBUG - Payment details:")
            print(f"  ID: {payment.id}")
            print(f"  Amount: {payment.amount}")
            print(f"  User ID: {payment.user_id}")
            current_app.logger.info(f"Starting secure bonus calculation for payment {payment.id}")
            
            # Security audit info
            audit_info = {
                'calculation_start': datetime.now(timezone.utc),
                'payment_amount': float(payment.amount),
                'payment_user_id': payment.user_id,
                'levels_processed': 0,
                'total_bonus_calculated': Decimal('0'),
                'security_checks': []
            }
            
            bonuses = []
            total_bonus_amount = Decimal('0')
            
            # Get the user who made the payment
            paying_user = User.query.get(payment.user_id)
            if not paying_user:
                return False, [], "Paying user not found", audit_info
            
            # ✅ Get the purchaser's referrer ONCE (the sponsor)
            purchaser_referrer_id = paying_user.referred_by
            current_app.logger.info(f"🔍 Purchaser: {paying_user.id}, Referrer (Sponsor): {purchaser_referrer_id}")
            
            # Generate batch processing ID
            processing_id = secrets.token_hex(16)
            
            # Calculate bonuses for each level (1 to 20)
            for level in range(1, BonusConfigHelper.MAX_LEVEL + 1):
                level_bonuses = BonusCalculationHelper._calculate_bonuses_for_level(
                    paying_user, payment, level, audit_info, purchaser_referrer_id, processing_id
                )
                bonuses.extend(level_bonuses)
                
                # Sum bonuses for this level
                for bonus in level_bonuses:
                    current_app.logger.info(f"Adding bonus: {bonus}")
                    total_bonus_amount += Decimal(str(bonus.get('bonus_amount', 0)))
            
            audit_info['calculation_end'] = datetime.now(timezone.utc)
            audit_info['levels_processed'] = len(set(bonus.get('level', 0) for bonus in bonuses))
            audit_info['total_bonus_calculated'] = float(total_bonus_amount)
            audit_info['bonuses_count'] = len(bonuses)
            
            current_app.logger.info(
                f"Bonus calculation completed: {len(bonuses)} bonuses across "
                f"{audit_info['levels_processed']} levels, total: {total_bonus_amount}"
            )
            
            return True, bonuses, f"Calculated {len(bonuses)} bonuses", audit_info
            
        except Exception as e:
            current_app.logger.error(f"Bonus calculation error: {str(e)}")
            audit_info['error'] = str(e)
            audit_info['calculation_end'] = datetime.now(timezone.utc)
            return False, [], f"Calculation failed: {str(e)}", audit_info
    
    @staticmethod
    def safe_decimal(value):  # ✅ Keep as static method
        """Safely convert value to Decimal"""
        import decimal
        try:
            return Decimal(str(value))
        except (TypeError, decimal.InvalidOperation) as e:
            current_app.logger.error(f"Invalid bonus amount: {value} - {e}")
            return Decimal('0')
    @staticmethod
    def _calculate_bonuses_for_level(user: User, payment: Payment, level: int, 
                                    audit_info: Dict, purchaser_referrer_id: int = None,
                                    processing_id: str = None) -> List[Dict]:
        """
        Calculate bonuses for a specific level safely.
        """
        bonuses = []

        try:
            users_at_level = BonusCalculationHelper._get_users_at_referral_level(user, level)
            current_app.logger.info(f"🔍 Level {level}: Found {len(users_at_level)} users")

            for target_user in users_at_level:
                try:
                    # ✅ Pass ALL required parameters
                    bonus_data = BonusCalculationHelper._calculate_single_bonus(
                        target_user=target_user,
                        payment=payment,
                        level=level,
                        original_payer_id=user.id,           # The purchaser
                        purchaser_referrer_id=purchaser_referrer_id,  # The sponsor
                        processing_id=processing_id
                    )
                    
                    if bonus_data:
                        bonuses.append(bonus_data)
                        bonus_amount = bonus_data.get('bonus_amount', 0)
                        current_app.logger.info(
                            f"💰 Level {level} bonus: User {target_user.id} - {bonus_amount:.2f} UGX"
                        )
                    else:
                        current_app.logger.info(f"User {target_user.id} did not receive a bonus")
                        
                except Exception as inner_e:
                    current_app.logger.error(f"Error for User {target_user.id}: {inner_e}")
                    audit_info['security_checks'].append(f'level_{level}_user_{target_user.id}_error:{inner_e}')

        except Exception as e:
            current_app.logger.error(f"Error calculating bonuses for level {level}: {str(e)}")
            audit_info['security_checks'].append(f'level_{level}_error:{str(e)}')

        return bonuses
 

    @staticmethod
    def _get_users_at_referral_level(start_user: User, target_level: int) -> List[User]:
        """
        Clean, accurate referral-level traversal.
        Returns exactly one user at the requested level, or [] if none exists.
        """
        try:
            if not start_user or target_level < 1:
                return []

            # LEVEL 1: Direct referrer
            current_referrer_id = start_user.referred_by
            if target_level == 1:
                if not current_referrer_id:
                    current_app.logger.info(f"🔍 Level 1: User {start_user.id} has no referrer")
                    return []
                
                try:
                    current_referrer_id = int(current_referrer_id)
                except:
                    return []

                referrer = User.query.get(current_referrer_id)
                current_app.logger.info(f"🔍 Level 1: User {start_user.id} → Referrer {referrer.id if referrer else 'None'}")
                return [referrer] if referrer else []

            # LEVEL 2+ : Traverse up (target_level - 1) hops
            try:
                current_referrer_id = int(current_referrer_id) if current_referrer_id else None
            except:
                current_referrer_id = None

            if not current_referrer_id:
                return []

            hops_needed = target_level - 1

            for hop in range(hops_needed):
                current_user = User.query.get(current_referrer_id)
                if not current_user:
                    return []

                if not current_user.referred_by:
                    current_app.logger.info(
                        f"🔍 Chain ended early at hop {hop+1} for target level {target_level}"
                    )
                    return []

                try:
                    current_referrer_id = int(current_user.referred_by)
                except:
                    return []

                current_app.logger.info(
                    f"🔍 Hop {hop+1}/{hops_needed}: "
                    f"{current_user.id} → Referrer {current_referrer_id}"
                )

            final_user = User.query.get(current_referrer_id)

            current_app.logger.info(f"TRAVERSE: Level {target_level}, Start user {start_user.id}")
            current_app.logger.info(f"TRAVERSE: Hop {hop}, Current user {current_user.id}, Their referrer {current_user.referred_by}")
            return [final_user] if final_user else []

        except Exception as e:
            current_app.logger.error(f"Error getting users at level {target_level}: {str(e)}")
            return []
    @staticmethod
    def _calculate_single_bonus(target_user: User, payment: Payment, level: int, 
                                original_payer_id: int, purchaser_referrer_id: int = None,
                                processing_id: str = None) -> Optional[Dict]:
        """
        Calculate a single bonus for a target user with ALL required fields.
        """
        try:
            # Validate target user
            if not target_user or not target_user.id:
                return None
                
            if not getattr(target_user, 'referral_bonus_eligible', True):
                current_app.logger.info(f"User {target_user.id} not eligible for bonuses")
                return None

            # Get bonus percentage
            bonus_percentage = BonusConfigHelper.get_bonus_percentage(level)

            # Calculate bonus amount
            payment_amount = Decimal(str(payment.amount))
            bonus_amount = payment_amount * bonus_percentage

            if bonus_amount < Decimal('1'):
                return None

            if bonus_amount > payment_amount:
                return None

            # CRITICAL: Get the correct referrer (sponsor of purchaser)
            correct_referrer_id = target_user.id
            
            # Generate security hash (REQUIRED)
            security_hash = BonusCalculationHelper._generate_security_hash(
                target_user.id, payment.id, level, float(bonus_amount)
            )
            
            # Generate processing ID if not provided
            if not processing_id:
                processing_id = secrets.token_hex(16)
            
            # ✅ COMPLETE BONUS DATA WITH ALL REQUIRED FIELDS
            bonus_data = {
                # Core required fields (NOT NULL in DB)
                'user_id': target_user.id,
                'referrer_id': correct_referrer_id,
                'referred_id': original_payer_id,
                'payment_id': payment.id,
                'level': level,
                'bonus_amount': float(bonus_amount),
                'status': 'pending',                    # ⭐ REQUIRED
                'type': 'referral_bonus',               # ⭐ REQUIRED
                'security_hash': security_hash,         # ⭐ REQUIRED NOT NULL
               
                'processing_id': processing_id,
                'threat_level': 'low',
                'is_paid_out': False,
                
                'ancestor_id': target_user.id,
                'bonus_percentage': float(bonus_percentage),
                'qualifying_amount': float(payment_amount),
                'calculated_on': datetime.now(timezone.utc).isoformat(),
                'purchase_id': payment.id,     
            }

            current_app.logger.info(
                f"💰 Calculated bonus: Level {level}, Recipient: {target_user.id}, "
                f"Referrer: {correct_referrer_id}, Purchaser: {original_payer_id}, "
                f"Amount: {bonus_amount:.2f} UGX"
            )

            return bonus_data

        except Exception as e:
            current_app.logger.error(f"Error in _calculate_single_bonus: {str(e)}")
            return None


    
    @staticmethod
    def _generate_security_hash(user_id: int, payment_id: int, level: int, amount: float) -> str:
        """Generate unique security hash for bonus record"""
        import hashlib
        from flask import current_app
        
        # Create deterministic string
        hash_string = f"{user_id}|{payment_id}|{level}|{amount}|{datetime.now(timezone.utc).timestamp()}"
        
        # Add secret salt from app config
        salt = current_app.config.get('SECRET_KEY', 'finicashi_default_salt')
        
        # Generate SHA256 hash
        return hashlib.sha256(f"{hash_string}|{salt}".encode()).hexdigest()
    
    @staticmethod
    def _calculate_bonus_hash(user_id: int, payment_id: int, amount: Decimal, level: int) -> str:
        """Calculate security hash for bonus integrity"""
        data_str = f"{user_id}_{payment_id}_{amount}_{level}"
        secret = current_app.config.get('SECRET_KEY', 'fallback-secret-key')
        return hashlib.sha256(f"{data_str}{secret}".encode()).hexdigest()
    
    @staticmethod
    def calculate_referral_bonuses_with_practical_validation(payment_id: int) -> bool:
        """
        Calculate bonuses using practical validation
        """
        try:
            from bonus.bonus_payment import BonusPaymentProcessor
            from extensions import db
            payment = Payment.query.get(payment_id)
            if not payment:
                return False
            
            start_user = User.query.get(payment.user_id)
            if not start_user:
                current_app.logger.error(f"user {payment.user_id} not found")
                return False
            
            direct_referrer_id = start_user.referred_by
            total_bonuses = 0
            bonuses_created = 0
            
            for level in range(1, 21):  # 20 levels
                users = BonusCalculationHelper._get_users_at_referral_level(start_user, level)
                
                for user in users:
                    # Use practical validation
                    is_eligible, message = BonusCalculationHelper.validate_user_eligibility(
                        user.id, level, payment.user_id
                    )
                    
                    if is_eligible:
                        bonus_amount = BonusCalculationHelper.calculate_bonus_amount(level, payment.amount)
                        bonus_data = {
                        'user_id': user.id,
                       # 'referrer_id':direct_referrer_id,
                        'payment_id': payment_id,
                        #'amount': bonus_amount,
                        'level': level,
                        'referrer_id': direct_referrer_id,
                        'referred_id': payment.user_id,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                        security_hash = BonusCalculationHelper._calculate_bonus_security_hash(bonus_data)    
                        # Create bonus
                        bonus = ReferralBonus(
                            user_id=user.id,
                            payment_id=payment_id,
                            bonus_amount=bonus_amount,
                           # amount=bonus_amount,
                            level=level,
                            status='pending',
                            referrer_id=direct_referrer_id,
                            referred_id=payment.user_id,
                            type='referral_bonus',
                            qualifying_amount=payment.amount,
                            bonus_percentage=BonusCalculationHelper._get_bonus_percentage(level),
                            calculated_on=datetime.utcnow(),
                            ancestor_id=direct_referrer_id,
                            transaction_reference=payment.reference,
                            security_hash=security_hash,
                            is_paid_out=False,
                            threat_level="low",
                            processing_id='procesing_id'

                        )
                        db.session.add(bonus)
                        total_bonuses += bonus_amount
                        
                        current_app.logger.info(f"💰 Level {level}: User {user.id} - UGX {bonus_amount}")
                    else:
                        current_app.logger.info(f"⏭️ Level {level}: User {user.id} - {message}")
            
            db.session.commit()
            
            # Use the new BonusPaymentProcessor instead of BonusPaymentHelper
            payment_success, payment_message, stats = BonusPaymentProcessor.process_payment_bonuses(payment_id)
            
            current_app.logger.info(f"🎊 Bonus calculation complete: {total_bonuses} calculated, payment: {payment_success}")
            return payment_success
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Bonus calculation error: {str(e)}")
            return False
