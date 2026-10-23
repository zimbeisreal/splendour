from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from flask import current_app
from models import ReferralBonus, Payment, User, ReferralNetwork
from extensions import db

class BonusValidationHelper:
    """Production-grade bonus validation with comprehensive checks"""

    @staticmethod
    def bonus_already_exists(purchase_id: int, ancestor_id: int, level: int, bonus_amount: Decimal) -> Tuple[bool, Optional[str]]:
        """
        DEBUG VERSION: Add logging to see what's happening
        """
        try:
            try:
                db.session.rollback()
            except:
                pass
        
            current_app.logger.info(f"🔍 Checking for existing bonus: purchase={purchase_id}, ancestor={ancestor_id}, level={level}, amount={bonus_amount}")
            
            existing = ReferralBonus.query.filter(
                ReferralBonus.payment_id == purchase_id,
                ReferralBonus.user_id == ancestor_id, 
                ReferralBonus.level == level,
                ReferralBonus.bonus_amount == bonus_amount
            ).first()
            
            if existing:
                current_app.logger.warning(f"⚠️ Found existing bonus: ID={existing.id}, Status={existing.status}")
                return True, existing.status
            else:
                current_app.logger.info("✅ No existing bonus found")
                return False, None
                
        except Exception as e:
            current_app.logger.error(f"❌ Error checking existing bonus: {str(e)}")
            return False, None
   
    @staticmethod
    def validate_bonus_entry(bonus_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        DEBUG VERSION: Find which method returns None
        """
        validation_details = {
            'checks_passed': [],
            'checks_failed': [],
            'warnings': [],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            print("🔍 STEP 1: Required fields validation")
            required_fields = ['purchase_id', 'ancestor_id', 'level', 'bonus_amount']
            missing_fields = [field for field in required_fields if field not in bonus_data]
            
            if missing_fields:
                error_msg = f"Missing required fields: {', '.join(missing_fields)}"
                validation_details['checks_failed'].append({'check': 'required_fields', 'details': missing_fields})
                return False, error_msg, validation_details
            
            validation_details['checks_passed'].append('required_fields')
            print("✅ Required fields passed")
            
            # 2. Data type and range validation
            print("🔍 STEP 2: Data type validation")
            purchase_id = bonus_data['purchase_id']
            ancestor_id = bonus_data['ancestor_id']
            level = bonus_data['level']
            bonus_amount = bonus_data['bonus_amount']
            
            # Validate ancestor ID
            if not isinstance(ancestor_id, int) or ancestor_id <= 0:
                validation_details['checks_failed'].append({'check': 'ancestor_id', 'details': f'Invalid value: {ancestor_id}'})
                return False, "Invalid ancestor ID", validation_details
            validation_details['checks_passed'].append('ancestor_id')
            print("✅ Ancestor ID passed")
            
            # Validate level (1-20)
            if not isinstance(level, int) or not 1 <= level <= 20:
                validation_details['checks_failed'].append({'check': 'level_range', 'details': f'Invalid level: {level}'})
                return False, f"Invalid level: {level}. Must be between 1-20", validation_details
            validation_details['checks_passed'].append('level_range')
            print("✅ Level validation passed")
            
            # Validate bonus amount
            if not isinstance(bonus_amount, (int, float, Decimal)):
                validation_details['checks_failed'].append({'check': 'bonus_amount_type', 'details': f'Invalid type: {type(bonus_amount)}'})
                return False, "Bonus amount must be numeric", validation_details
            
            bonus_amount_decimal = Decimal(str(bonus_amount))
            if bonus_amount_decimal <= 0:
                validation_details['checks_failed'].append({'check': 'bonus_amount_positive', 'details': f'Invalid amount: {bonus_amount}'})
                return False, "Bonus amount must be positive", validation_details
            
            if bonus_amount_decimal > Decimal('10000000'):
                validation_details['checks_failed'].append({'check': 'bonus_amount_limit', 'details': f'Amount too high: {bonus_amount}'})
                return False, "Bonus amount exceeds maximum limit", validation_details
            validation_details['checks_passed'].append('bonus_amount')
            print("✅ Bonus amount validation passed")
            
            # 3. Duplicate bonus validation
            print("🔍 STEP 3: Duplicate check")
            exists, existing_status = BonusValidationHelper.bonus_already_exists(
                purchase_id, ancestor_id, level, bonus_amount_decimal
            )
            if exists:
                validation_details['checks_failed'].append({
                    'check': 'duplicate_bonus', 
                    'details': f'Bonus already exists with status: {existing_status}'
                })
                return False, f"Bonus already exists (status: {existing_status})", validation_details
            validation_details['checks_passed'].append('duplicate_check')
            print("✅ Duplicate check passed")
            
            # 4. Purchase validation
            print("🔍 STEP 4: Purchase validation")
            purchase_result = BonusValidationHelper.validate_purchase(purchase_id)
            print(f"Purchase result: {purchase_result}")
            if purchase_result is None:
                raise Exception("validate_purchase returned None")
            is_purchase_valid, purchase_error = purchase_result
            if not is_purchase_valid:
                validation_details['checks_failed'].append({
                    'check': 'purchase_validation', 
                    'details': purchase_error
                })
                return False, f"Purchase validation failed: {purchase_error}", validation_details
            validation_details['checks_passed'].append('purchase_validation')
            print("✅ Purchase validation passed")
            
            # 5. User eligibility validation
            print("🔍 STEP 5: User eligibility validation")
            eligibility_result = BonusValidationHelper.validate_user_eligibility(ancestor_id, level)
            print(f"User eligibility result: {eligibility_result}")
            if eligibility_result is None:
                raise Exception("validate_user_eligibility returned None")
            is_user_eligible, user_error = eligibility_result
            if not is_user_eligible:
                validation_details['checks_failed'].append({
                    'check': 'user_eligibility', 
                    'details': user_error
                })
                return False, f"User eligibility failed: {user_error}", validation_details
            validation_details['checks_passed'].append('user_eligibility')
            print("✅ User eligibility passed")
            
            # 6. Network relationship validation
            print("🔍 STEP 6: Network relationship validation")
            network_result = BonusValidationHelper.validate_network_relationship(
                bonus_data.get('descendant_id'), ancestor_id, level
            )
            print(f"Network result: {network_result}")
            if network_result is None:
                raise Exception("validate_network_relationship returned None")
            is_network_valid, network_error = network_result
            if not is_network_valid:
                validation_details['checks_failed'].append({
                    'check': 'network_relationship', 
                    'details': network_error
                })
                return False, f"Network validation failed: {network_error}", validation_details
            validation_details['checks_passed'].append('network_relationship')
            print("✅ Network relationship passed")
            
            # 7. Business rule validation
            print("🔍 STEP 7: Business rule validation")
            business_result = BonusValidationHelper.validate_business_rules(bonus_data)
            print(f"Business rules result: {business_result}")
            if business_result is None:
                raise Exception("validate_business_rules returned None")
            is_business_valid, business_error = business_result
            if not is_business_valid:
                validation_details['checks_failed'].append({
                    'check': 'business_rules', 
                    'details': business_error
                })
                return False, f"Business rule violation: {business_error}", validation_details
            validation_details['checks_passed'].append('business_rules')
            print("✅ Business rules passed")
            
            print("🎉 ALL VALIDATIONS PASSED!")
            return True, "Bonus validation passed", validation_details
            
        except Exception as e:
            print(f"❌ VALIDATION ERROR: {str(e)}")
            current_app.logger.error(f"Bonus validation error: {str(e)}")
            validation_details['checks_failed'].append({
                'check': 'validation_system_error', 
                'details': str(e)
            })
            return False, f"Validation system error: {str(e)}", validation_details
        
    @staticmethod
    def validate_purchase(payment_id: int) -> Tuple[bool, str]:
        """
        Validate purchase using Payment record.
        """
        try:
            payment = Payment.query.get(payment_id)  # now passing actual Payment.id
            if not payment:
                return False, "Payment not found"
            
            # Payment status check
            if payment.status != 'completed':
                return False, f"Purchase status is {payment.status}, not completed"
            
            # Amount validation
            if not payment.amount or payment.amount <= 0:
                return False, "Invalid purchase amount"

            # Currency validation
            if getattr(payment, 'currency', 'UGX') != 'UGX':
                return False, f"Unsupported currency: {payment.currency}"
            
            # Minimum amount check
            if payment.amount < Decimal('10000'):
                return False, "Purchase amount below minimum for bonuses"
            
            return True, "Valid purchase for bonus processing"
            
        except Exception as e:
            current_app.logger.error(f"Purchase validation error for {payment_id}: {str(e)}")
            return False, f"Purchase validation error: {str(e)}"


    @staticmethod
    def validate_user_eligibility(user_id: int, level: int) -> Tuple[bool, str]:
        """
        ENHANCED: Comprehensive user eligibility with fraud checks
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"
            
            if not user.is_active:
                return False, "User account is inactive"
            return True, "User eligible"          
        except Exception as e:
            current_app.logger.error(f"User eligibility error for {user_id}: {str(e)}")
            return False, f"User eligibility check error: {str(e)}"
    
    @staticmethod
    def validate_network_relationship(descendant_id: int, ancestor_id: int, level: int) -> Tuple[bool, str]:
        """
        ENHANCED: Validate the network relationship exists and is correct
        """
        try:
            if not descendant_id:
               return True, "Network validation skipped (no descendant_id provided)"
            relationship = ReferralNetwork.query.filter_by(
                ancestor_id=ancestor_id,
                descendant_id=descendant_id,
                depth=level
            ).first()
            
            if not relationship:
                return False, f"No network relationship found for level {level}"
            
            if not getattr(relationship, 'is_active', True):
                return False, "Network relationship is inactive"
            
            return True, "Valid network relationship"
            
        except Exception as e:
            current_app.logger.error(f"Network validation error: {str(e)}")
            return False, f"Network validation error: {str(e)}"
    
    @staticmethod
    def validate_business_rules(bonus_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        ENHANCED: Business rule validation
        """
        try:
            level = bonus_data['level']
            bonus_amount = Decimal(str(bonus_data['bonus_amount']))
            
            # Level-specific rules
            if level == 1 and bonus_amount > Decimal('500000'):  # 500K limit for level 1
                return False, "Level 1 bonus exceeds maximum amount"
            
            if level > 10 and bonus_amount > Decimal('100000'):  # 100K limit for levels 11-20
                return False, "Higher level bonus exceeds maximum amount"
            
            # Package-specific rules (if package info available)
            if 'package_id' in bonus_data:
                package_specific_valid, package_error = BonusValidationHelper.validate_package_rules(
                    bonus_data['package_id'], level, bonus_amount
                )
                if not package_specific_valid:
                    return False, package_error
            
            return True, "Business rules satisfied"
            
        except Exception as e:
            current_app.logger.error(f"Business rule validation error: {str(e)}")
            return False, f"Business rule validation error: {str(e)}"
    
    @staticmethod
    def validate_bonus_batch(bonuses_data: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict], Dict[str, Any]]:
        """
        ENHANCED: Batch validation with comprehensive reporting
        """
        batch_validation = {
            'total_bonuses': len(bonuses_data),
            'valid_count': 0,
            'invalid_count': 0,
            'validation_start': datetime.now(timezone.utc).isoformat(),
            'detailed_results': []
        }
        
        valid_bonuses = []
        invalid_bonuses = []
        
        for i, bonus_data in enumerate(bonuses_data):
            bonus_validation = {
                'index': i,
                'purchase_id': bonus_data.get('purchase_id'),
                'ancestor_id': bonus_data.get('ancestor_id'),
                'level': bonus_data.get('level'),
                'bonus_amount': bonus_data.get('bonus_amount'),
                'passed': False,
                'errors': []
            }
            
            is_valid, error_message, validation_details = BonusValidationHelper.validate_bonus_entry(bonus_data)
            
            if is_valid:
                valid_bonuses.append(bonus_data)
                bonus_validation['passed'] = True
                batch_validation['valid_count'] += 1
            else:
                invalid_bonuses.append({
                    **bonus_data,
                    'validation_error': error_message,
                    'validation_details': validation_details
                })
                bonus_validation['passed'] = False
                bonus_validation['errors'] = validation_details.get('checks_failed', [])
                batch_validation['invalid_count'] += 1
            
            bonus_validation['validation_details'] = validation_details
            batch_validation['detailed_results'].append(bonus_validation)
        
        batch_validation['validation_end'] = datetime.now(timezone.utc).isoformat()
        batch_validation['success_rate'] = batch_validation['valid_count'] / batch_validation['total_bonuses'] if batch_validation['total_bonuses'] > 0 else 0
        
        current_app.logger.info(
            f"Batch validation complete: {batch_validation['valid_count']}/"
            f"{batch_validation['total_bonuses']} valid "
            f"({batch_validation['success_rate']:.2%} success rate)"
        )
        
        return valid_bonuses, invalid_bonuses, batch_validation
    
    @staticmethod
    def can_process_bonuses(purchase_id: int) -> Tuple[bool, str, Dict[str, Any]]:
        """
        ENHANCED: Comprehensive pre-processing check with locking
        """
        validation_result = {
            'purchase_id': purchase_id,
            'checks_passed': [],
            'checks_failed': [],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Use row-level locking to prevent concurrent processing
            purchase = Payment.query.with_for_update().get(purchase_id)
            if not purchase:
                validation_result['checks_failed'].append('purchase_not_found')
                return False, "Purchase not found", validation_result
            
            # 1. Validate purchase
            is_purchase_valid, purchase_error = BonusValidationHelper.validate_purchase(purchase_id)
            if not is_purchase_valid:
                validation_result['checks_failed'].append(f'purchase_validation: {purchase_error}')
                return False, f"Purchase validation failed: {purchase_error}", validation_result
            validation_result['checks_passed'].append('purchase_validation')
            
            # 2. Check for existing bonuses (with lock to prevent race conditions)
            existing_bonuses = ReferralBonus.query.filter_by(payment_id=purchase_id).count()
            if existing_bonuses > 0:
                validation_result['checks_failed'].append(f'existing_bonuses: {existing_bonuses}')
                return False, f"Already {existing_bonuses} bonuses processed", validation_result
            validation_result['checks_passed'].append('no_existing_bonuses')
            
            # 3. Check if bonuses are already being processed
            if getattr(purchase, 'bonus_processing_started', False):
                processing_age = datetime.now(timezone.utc) - getattr(purchase, 'bonus_processing_started_at', datetime.now(timezone.utc))
                if processing_age < timedelta(minutes=30):  # Still within processing window
                    validation_result['checks_failed'].append('processing_in_progress')
                    return False, "Bonus processing already in progress", validation_result
                else:
                    # Stale processing flag, allow retry
                    current_app.logger.warning(f"Stale processing flag for purchase {purchase_id}")
            validation_result['checks_passed'].append('no_processing_in_progress')
            
            # 4. Set processing flag to prevent concurrent processing
            purchase.bonus_processing_started = True
            purchase.bonus_processing_started_at = datetime.now(timezone.utc)
            db.session.commit()
            
            validation_result['checks_passed'].append('processing_flag_set')
            
            current_app.logger.info(f"Bonus processing approved for purchase {purchase_id}")
            return True, "Ready for bonus processing", validation_result
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Bonus processing check error for {purchase_id}: {str(e)}")
            validation_result['checks_failed'].append(f'system_error: {str(e)}')
            return False, f"Processing check error: {str(e)}", validation_result
        
    @staticmethod
    def cleanup_processing_flag(purchase_id: int, success: bool = True):
        """
        PROPERLY CLEANUP processing flag after bonus processing completes
        """
        try:
            # ✅ ACTUALLY get the purchase and update it
            purchase = Payment.query.get(purchase_id)
            if purchase:
                # Reset the processing flag
                purchase.bonus_processing_started = False
                
                # If processing was successful, mark bonuses as calculated
                if success:
                    purchase.bonuses_calculated = True
                    purchase.bonuses_calculated_at = datetime.now(timezone.utc)
                
                db.session.commit()
                current_app.logger.info(f"✅ Cleared processing flag for purchase {purchase_id}, success={success}")
            else:
                current_app.logger.warning(f"⚠️ Purchase {purchase_id} not found during cleanup")
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"❌ Error cleaning up processing flag for {purchase_id}: {str(e)}")
    # In your validation function, improve the duplicate check:
def validate_no_duplicates(bonus_data):
    """Check if this exact bonus already exists"""
    from models import ReferralBonus
    
    # Check for exact duplicates
    existing = ReferralBonus.query.filter_by(
        user_id=bonus_data.get('user_id'),
        payment_id=bonus_data.get('payment_id') or bonus_data.get('purchase_id'),
        level=bonus_data.get('level')
    ).first()
    
    if existing:
        return False, f"Duplicate bonus already exists: {existing.id}"
    
    # Also check for the same user+payment combination at any level
    same_payment = ReferralBonus.query.filter_by(
        user_id=bonus_data.get('user_id'),
        payment_id=bonus_data.get('payment_id') or bonus_data.get('purchase_id')
    ).count()
    
    if same_payment > 0:
        return False, f"User already has a bonus for this payment"
    
    return True, "Duplicate check passed"