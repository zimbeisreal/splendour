

# bonus_orchestrator.py
from decimal import Decimal
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timedelta, timezone
from flask import current_app
from sqlalchemy import text
import threading
import uuid
import hashlib
import json
from models import Payment, ReferralBonus, User, AuditLog
from bonus.config import BonusConfigHelper


class ProductionBonusOrchestrator:
    """
    Production-grade bonus orchestrator with comprehensive security,
    monitoring, and fault tolerance
    """
    
    def __init__(self):
        self.max_workers = 5
        self.processing_lock = threading.Lock()
        self.active_processes = {}
        
        # Security monitoring
        self.suspicious_activities = []
        self.performance_metrics = {
            'total_processed': 0,
            'successful_calculations': 0,
            'failed_calculations': 0,
            'average_processing_time': 0,
            'last_processed': None
        }
        
        # Initialize in-memory locks ONLY (no Redis)
        self._init_locks()
        
        # Validate bonus configuration on startup
        self._validate_bonus_config()
    
    def _init_locks(self):
        """Initialize in-memory locks without any Redis dependency"""
        current_app.logger.info("🔄 Using in-memory locks for bonus processing")
        self.redis = None  # Explicitly set to None
        self._memory_locks = {}  # Initialize memory locks
    
    def _validate_bonus_config(self):
        """Validate bonus configuration on startup"""
        try:
            is_valid, message = BonusConfigHelper.validate_bonus_configuration()
            if is_valid:
                current_app.logger.info(f"✅ Bonus configuration: {message}")
            else:
                current_app.logger.error(f"❌ Bonus configuration invalid: {message}")
                
            # Log distribution summary
            summary = BonusConfigHelper.get_bonus_distribution_summary()
            current_app.logger.info(
                f"📊 Bonus distribution: {summary['total_percentage']*100:.1f}% total "
                f"across {summary['max_level']} levels"
            )
        except Exception as e:
            current_app.logger.error(f"Bonus configuration validation failed: {e}")
    
    def process_payment_bonuses_secure(self, payment_id: int) -> Tuple[bool, str, Dict[str, Any]]:
        """
        SECURE ENTRY POINT: Process bonuses for a payment with comprehensive security
        Now distributes up to level 20 with configured percentages
        """
        security_context = {
            'payment_id': payment_id,
            'start_time': datetime.now(timezone.utc),
            'security_checks_passed': [],
            'security_checks_failed': [],
            'threat_level': 'low',
            'processing_id': self._generate_processing_id(),
            'bonus_config': BonusConfigHelper.get_bonus_distribution_summary()
        }
        
        try:
            # 1. PRE-PROCESSING SECURITY CHECKS
            current_app.logger.info(
                f"Starting secure bonus processing for payment {payment_id} "
                f"(up to level {BonusConfigHelper.MAX_LEVEL})"
            )
            
            # Check if already processing (prevent duplicates)
            if not self._acquire_processing_lock(payment_id, security_context['processing_id']):
                return False, "Payment already being processed", security_context
            
            # Validate payment exists and is accessible
            payment = self._secure_payment_lookup(payment_id, security_context)
            if not payment:
                return False, "Payment security validation failed", security_context
            
            # 2. BONUS CALCULATION WITH SECURITY CONTEXT
            calculation_result = self._secure_bonus_calculation(payment, security_context)
            if not calculation_result['success']:
                return False, calculation_result['message'], security_context
            
            # 3. BONUS VALIDATION & INTEGRITY CHECKING
            validation_result = self._secure_bonus_validation(
                calculation_result['bonuses'], 
                payment, 
                security_context
            )
            if not validation_result['success']:
                return False, validation_result['message'], security_context
            
            # 4. SECURE BONUS STORAGE
            storage_result = self._secure_bonus_storage(
                validation_result['valid_bonuses'], 
                payment, 
                security_context
            )
            if not storage_result['success']:
                return False, storage_result['message'], security_context
            
            security_context['end_time'] = datetime.now(timezone.utc)
            security_context['processing_duration'] = (
                security_context['end_time'] - security_context['start_time']
            ).total_seconds()
            
            # Log level distribution
            level_distribution = self._analyze_level_distribution(calculation_result['bonuses'])
            security_context['level_distribution'] = level_distribution
            
            current_app.logger.info(
                f"SECURE_PROCESSING_COMPLETE: Payment {payment_id}, "
                f"Bonuses: {len(validation_result['valid_bonuses'])}, "
                f"Levels: {level_distribution['levels_used']}, "
                f"Threat Level: {security_context['threat_level']}, "
                f"Duration: {security_context['processing_duration']:.2f}s"
            )
            
            return True, f"Successfully processed {len(validation_result['valid_bonuses'])} bonuses across {level_distribution['levels_used']} levels", security_context
            
        except Exception as e:
            self._handle_processing_error(payment_id, e, security_context)
            return False, f"Processing error: {str(e)}", security_context
        
        finally:
            self._release_processing_lock(payment_id, security_context['processing_id'])
    
    def _secure_bonus_calculation(self, payment: Payment, security_context: Dict) -> Dict[str, Any]:
        """Secure bonus calculation with monitoring - now up to level 20"""
        try:
            # Import here to avoid circular imports
            from bonus.bonus_calculation import BonusCalculationHelper
            
            # Use the secure calculation method
            success, bonuses, message, audit_info = BonusCalculationHelper.calculate_all_bonuses_secure(payment)
            
            if not success:
                security_context['security_checks_failed'].append(f'calculation_failed: {message}')
                return {'success': False, 'message': message}
            
            # Additional security checks on calculated bonuses
            suspicious_bonuses = []
            level_distribution = {}
            
            for bonus in bonuses:
                # Check for suspicious bonus amounts
                bonus_amount = Decimal(str(bonus.get('amount', 0)))
                level = bonus.get('level', 0)
                
                # Track level distribution
                level_distribution[level] = level_distribution.get(level, 0) + 1
                
                if bonus_amount > Decimal('1000000'):  # 1M UGX
                    security_context['threat_level'] = max(security_context['threat_level'], 'medium')
                    suspicious_bonuses.append(bonus)
                
                # Verify bonus percentage matches configuration
                expected_percentage = BonusConfigHelper.get_bonus_percentage(level)
                actual_percentage = bonus.get('bonus_percentage')
                if actual_percentage and abs(Decimal(str(actual_percentage)) - expected_percentage) > Decimal('0.001'):
                    current_app.logger.warning(
                        f"Bonus percentage mismatch for level {level}: "
                        f"expected {expected_percentage}, got {actual_percentage}"
                    )
            
            if suspicious_bonuses:
                security_context['suspicious_bonuses'] = suspicious_bonuses
            
            security_context['level_distribution_raw'] = level_distribution
            security_context['security_checks_passed'].append('bonus_calculation')
            
            return {
                'success': True,
                'bonuses': bonuses,
                'message': message,
                'audit_info': audit_info
            }
            
        except Exception as e:
            current_app.logger.error(f"Secure bonus calculation failed: {str(e)}")
            security_context['security_checks_failed'].append(f'calculation_error: {str(e)}')
            return {'success': False, 'message': f"Calculation error: {str(e)}"}
    
    def _analyze_level_distribution(self, bonuses: List[Dict]) -> Dict[str, Any]:
        """Analyze how bonuses are distributed across levels"""
        level_stats = {}
        total_bonus = Decimal('0')
        
        for bonus in bonuses:
            level = bonus.get('level', 0)
            amount = Decimal(str(bonus.get('amount', 0)))
            
            if level not in level_stats:
                level_stats[level] = {
                    'count': 0,
                    'total_amount': Decimal('0'),
                    'expected_percentage': float(BonusConfigHelper.get_bonus_percentage(level))
                }
            
            level_stats[level]['count'] += 1
            level_stats[level]['total_amount'] += amount
            total_bonus += amount
        
        # Convert to serializable format
        for level in level_stats:
            level_stats[level]['total_amount'] = float(level_stats[level]['total_amount'])
            if total_bonus > Decimal('0'):
                level_stats[level]['actual_percentage'] = float(
                    level_stats[level]['total_amount'] / total_bonus
                )
            else:
                level_stats[level]['actual_percentage'] = 0.0
        
        return {
            'level_stats': level_stats,
            'levels_used': len(level_stats),
            'max_level_used': max(level_stats.keys()) if level_stats else 0,
            'total_bonus_amount': float(total_bonus)
        }
    
    def _secure_payment_lookup(self, payment_id: int, security_context: Dict) -> Optional[Payment]:
        """Secure payment lookup with validation"""
        try:
            payment = Payment.query.filter_by(id=payment_id).first()
            
            if not payment:
                security_context['security_checks_failed'].append('payment_not_found')
                return None
            
            # Validate payment state
            if payment.status != 'completed':
                security_context['security_checks_failed'].append(f'invalid_status: {payment.status}')
                return None
            
            # Check if bonuses already processed
            existing_bonuses = ReferralBonus.query.filter_by(payment_id=payment_id).count()
            if existing_bonuses > 0:
                security_context['security_checks_failed'].append('bonuses_already_calculated')
                return None
            
            security_context['security_checks_passed'].append('payment_validation')
            return payment
            
        except Exception as e:
            current_app.logger.error(f"Secure payment lookup failed: {str(e)}")
            security_context['security_checks_failed'].append(f'lookup_error: {str(e)}')
            return None
   
    # In your ProductionBonusOrchestrator class, update the validation methods:

    def _secure_bonus_validation(self, bonuses: List[Dict], payment: Payment, security_context: Dict) -> Dict[str, Any]:
        """Secure bonus validation with integrity checks"""
        try:
            valid_bonuses = []
            invalid_bonuses = []
            
            current_app.logger.info(f"🔍 Starting validation for {len(bonuses)} bonuses")
            
            # Basic validation
            for i, bonus in enumerate(bonuses):
                is_valid, reason = self._basic_bonus_validation_with_reason(bonus)
                if is_valid:
                        valid_bonuses.append(bonus)
                        current_app.logger.info(f"✅ Bonus {i+1} valid: User {bonus.get('user_id')}, Level {bonus.get('level')}, Amount {bonus.get('amount')}")
                else:
                        invalid_bonuses.append({
                            **bonus,
                            'validation_error': reason
                        })
                        current_app.logger.warning(f"❌ Bonus {i+1} invalid: {reason}")
                
                        security_context['valid_bonuses_count'] = len(valid_bonuses)
                        security_context['invalid_bonuses_count'] = len(invalid_bonuses)
                        security_context['security_checks_passed'].append('bonus_validation')
                        
                if invalid_bonuses:
                    current_app.logger.warning(
                        f"Found {len(invalid_bonuses)} invalid bonuses for payment {payment.id}. "
                        f"First invalid bonus details: {invalid_bonuses[0]}"
                    )
                
                    return {
                    'success': True,
                    'valid_bonuses': valid_bonuses,
                    'invalid_bonuses': invalid_bonuses,
                    'validation_details': {
                        'total_checked': len(bonuses),
                        'valid_count': len(valid_bonuses),
                        'invalid_count': len(invalid_bonuses)
                    }
                }
                
        except Exception as e:
                current_app.logger.error(f"Bonus validation failed: {str(e)}")
                security_context['security_checks_failed'].append(f'validation_error: {str(e)}')
                return {'success': False, 'message': f"Validation error: {str(e)}"}
        
    
    # In your ProductionBonusOrchestrator class, update the validation:

    def _basic_bonus_validation_with_reason(self, bonus: Dict) -> Tuple[bool, str]:
        """Basic bonus validation with detailed reason reporting"""
        try:
            current_app.logger.info(f"🔍 Validating bonus: {bonus}")
            
            # Check required fields
            required_fields = ['user_id', 'amount', 'level']
            for field in required_fields:
                if field not in bonus:
                    return False, f"Missing required field: {field}"
            
            # Check user_id is valid
            user_id = bonus['user_id']
            if not isinstance(user_id, int):
                # Try to convert to int
                try:
                    bonus['user_id'] = int(user_id)
                    user_id = bonus['user_id']
                except (ValueError, TypeError):
                    return False, f"Invalid user_id type: {type(user_id)}, value: {user_id}"
            
            if user_id <= 0:
                return False, f"Invalid user_id: {user_id}"
            
            # Check user exists in database
            try:
                user = User.query.get(user_id)
                if not user:
                    return False, f"User {user_id} does not exist in database"
            except Exception as e:
                return False, f"Database error checking user {user_id}: {str(e)}"
            
            # Check amount is valid and positive
            try:
                amount = bonus['amount']
                if isinstance(amount, str):
                    # Try to convert string to float
                    try:
                        bonus['amount'] = float(amount)
                        amount = bonus['amount']
                    except ValueError:
                        return False, f"Invalid amount string: {amount}"
                
                if not isinstance(amount, (int, float)):
                    return False, f"Invalid amount type: {type(amount)}, value: {amount}"
                
                if amount <= 0:
                    return False, f"Amount must be positive: {amount}"
                    
                if amount > 10000000:  # 10M UGX sanity check
                    return False, f"Amount too large: {amount}"
                    
            except (ValueError, TypeError) as e:
                return False, f"Invalid amount: {bonus['amount']}, error: {str(e)}"
            
            # Check level is valid
            level = bonus['level']
            if not isinstance(level, int):
                # Try to convert to int
                try:
                    bonus['level'] = int(level)
                    level = bonus['level']
                except (ValueError, TypeError):
                    return False, f"Invalid level type: {type(level)}, value: {level}"
            
            if level < 1 or level > BonusConfigHelper.MAX_LEVEL:
                return False, f"Invalid level: {level}. Must be between 1 and {BonusConfigHelper.MAX_LEVEL}"
            
            # Check purchase_id if present
            if 'purchase_id' in bonus:
                purchase_id = bonus['purchase_id']
                if not isinstance(purchase_id, int):
                    try:
                        bonus['purchase_id'] = int(purchase_id)
                    except (ValueError, TypeError):
                        return False, f"Invalid purchase_id type: {type(purchase_id)}, value: {purchase_id}"
            
            current_app.logger.info(f"✅ Bonus validation passed: User {user_id}, Level {level}, Amount {amount}")
            return True, "Valid bonus"
            
        except Exception as e:
            return False, f"Validation exception: {str(e)}"
    # In your ProductionBonusOrchestrator class, update the _secure_bonus_storage method:

    def _secure_bonus_storage(self, bonuses: List[Dict], payment: Payment, security_context: Dict) -> Dict[str, Any]:
        """Secure bonus storage with transaction safety"""
        try:
            stored_bonuses = []
            
            current_app.logger.info(f"🔄 Starting storage for {len(bonuses)} validated bonuses")
            
            # Use database transaction
            for i, bonus_data in enumerate(bonuses):
                try:

                    # Create bonus record with additional security fields
                    bonus = ReferralBonus(
                        user_id=bonus_data['user_id'],
                        payment_id=payment.id,
                        bonus_amount=bonus_data['amount'],
                        level=bonus_data['level'],
                        status='pending',
                        security_hash=self._calculate_bonus_security_hash(bonus_data),
                        processing_id=security_context['processing_id'],
                        threat_level=security_context['threat_level'],
                        created_at=datetime.now(timezone.utc)
                    )
                    
                    # Add optional fields if they exist
                    optional_fields = ['referrer_id', 'referred_id', 'bonus_percentage', 'qualifying_amount']
                    for field in optional_fields:
                        if field in bonus_data:
                            setattr(bonus, field, bonus_data[field])
                    
                    current_app.db.session.add(bonus)
                    stored_bonuses.append(bonus)
                    current_app.logger.info(f"💾 Stored bonus {i+1}: User {bonus.user_id}, Level {bonus.level}, Amount {bonus.amount}")
                    
                except Exception as e:
                    current_app.logger.error(f"❌ Failed to store bonus {i+1}: {str(e)}")
                    continue
            
            # Mark payment as processed
            payment.bonuses_calculated = True
            payment.bonuses_calculated_at = datetime.now(timezone.utc)
            payment.bonus_processing_id = security_context['processing_id']
            
            # Commit the transaction
            current_app.db.session.commit()
            
            security_context['security_checks_passed'].append('bonus_storage')
            security_context['stored_bonuses_count'] = len(stored_bonuses)
            
            current_app.logger.info(f"✅ Successfully stored {len(stored_bonuses)} bonuses in database")
            
            return {
                'success': True,
                'stored_bonuses': stored_bonuses,
                'message': f"Stored {len(stored_bonuses)} bonuses"
            }
            
        except Exception as e:
            current_app.db.session.rollback()
            current_app.logger.error(f"❌ Bonus storage failed: {str(e)}")
            security_context['security_checks_failed'].append(f'storage_error: {str(e)}')
            return {'success': False, 'message': f"Storage error: {str(e)}"}
        
    # Security utility methods
    def _acquire_processing_lock(self, payment_id: int, processing_id: str) -> bool:
        """Acquire processing lock to prevent duplicates"""
        # ALWAYS use in-memory locks (Redis completely removed)
        with self.processing_lock:
            if payment_id in self._memory_locks:
                return False
            self._memory_locks[payment_id] = processing_id
            return True
        
    def _release_processing_lock(self, payment_id: int, processing_id: str):
        """Release processing lock"""
        # ALWAYS use in-memory locks (Redis completely removed)
        with self.processing_lock:
            if self._memory_locks.get(payment_id) == processing_id:
                del self._memory_locks[payment_id]
    
    def _generate_processing_id(self) -> str:
        """Generate unique processing ID"""
        return f"proc_{uuid.uuid4().hex[:16]}_{int(datetime.now(timezone.utc).timestamp())}"
    
    def _calculate_bonus_security_hash(self, bonus_data: Dict) -> str:
        """Calculate security hash for bonus integrity"""
        # Create a stable representation of the data
        stable_data = {
            'user_id': bonus_data.get('user_id'),
            'amount': str(bonus_data.get('amount')),
            'level': bonus_data.get('level'),
            'payment_id': bonus_data.get('purchase_id')
        }
        data_str = json.dumps(stable_data, sort_keys=True)
        secret = current_app.config.get('SECRET_KEY', 'fallback-secret-key')
        return hashlib.sha256(f"{data_str}{secret}".encode()).hexdigest()
    
    def _handle_processing_error(self, payment_id: int, error: Exception, security_context: Dict):
        """Handle processing errors with security context"""
        security_context['error'] = str(error)
        security_context['end_time'] = datetime.now(timezone.utc)
        
        # Log error with security context
        current_app.logger.error(
            f"BONUS_PROCESSING_ERROR: Payment {payment_id}, "
            f"Processing ID: {security_context['processing_id']}, "
            f"Threat Level: {security_context['threat_level']}, "
            f"Error: {str(error)}"
        )
    
    def get_bonus_configuration_info(self) -> Dict[str, Any]:
        """Get information about the current bonus configuration"""
        return {
            'configuration': BonusConfigHelper.get_bonus_distribution_summary(),
            'max_level': BonusConfigHelper.MAX_LEVEL,
            'validation': BonusConfigHelper.validate_bonus_configuration()
        }


# Create a singleton instance for use throughout the application
bonus_orchestrator = ProductionBonusOrchestrator()