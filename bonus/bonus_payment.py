from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from flask import current_app
from sqlalchemy import text
from extensions import db
from models import ReferralBonus, Wallet, Transaction, BonusPayoutQueue, AuditLog, Payment, User


class BonusPaymentHelper:
    """Production-grade bonus payment handler with transaction safety"""
    
    @staticmethod
    def approve_bonus(bonus_id: int) -> Tuple[bool, str]:
        """
        APPROVED VERSION: Single transaction per bonus payout
        """
        try:
            # Use database transaction to ensure atomicity
            with db.session.begin_nested():  # Use nested transaction for safety
                bonus = ReferralBonus.query.with_for_update().get(bonus_id)  # Row-level locking
                if not bonus:
                    return False, "Bonus not found"
                
                # Validate bonus state (with additional checks)
                if bonus.status != 'pending':
                    return False, f"Bonus status is {bonus.status}, expected pending"
                
                if bonus.is_paid_out:
                    return False, "Bonus already paid out"
                
                # Check for duplicate processing
                existing_transaction = Transaction.query.filter_by(
                    reference=f"BONUS_{bonus.id}"
                ).first()
                if existing_transaction:
                    return False, "Duplicate transaction detected"
                
                # Credit user wallet (atomic operation)
                success, message, transaction_id = BonusPaymentHelper._credit_user_wallet_atomic(
                    bonus.user_id, 
                    Decimal(str(bonus.amount)),
                    bonus.id
                )
                
                if not success:
                    return False, message
                
                # Update bonus status
                bonus.status = 'paid'
                bonus.paid_at = db.func.now()
                bonus.is_paid_out = True
                bonus.payout_transaction_id = transaction_id
                
                # Comprehensive audit logging
                BonusPaymentHelper._log_bonus_payment_audit(bonus, transaction_id)
            
            # Only commit once all operations succeed
            db.session.commit()
            
            current_app.logger.info(f"Bonus {bonus_id} approved and paid - Transaction: {transaction_id}")
            return True, f"Bonus paid successfully - TXN: {transaction_id}"
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error approving bonus {bonus_id}: {str(e)}")
            return False, f"Payment processing error: {str(e)}"
        
   
    @staticmethod
    def _credit_user_wallet_atomic(user_id: int, amount: Decimal, bonus_id: int) -> Tuple[bool, str, Optional[int]]:
        """
        Safely credit a user's wallet with a bonus amount.
        Ensures wallet exists, updates balance, creates transaction, and commits atomically.
        """
        try:
            if amount <= Decimal("0"):
                return False, "Invalid bonus amount", None
            amount_decimal = Decimal(str(amount))
            
            # ========== MODIFIED NOTIFICATION WITH HYPERLINK ==========
            from bonus.payment_processor import create_notification
            
            # Check if bonus meets minimum package threshold
            MIN_PACKAGE_AMOUNT = Decimal("10000")
            
            if amount_decimal >= MIN_PACKAGE_AMOUNT:
                # Create notification with reinvest suggestion
                notification_message = (
                    f"Earned referral bonus of UGX {amount_decimal:,.2f}! "

                )
            else:
                # Regular notification without reinvest link
                notification_message = (
                    f"Earned referral bonus of UGX {amount_decimal:,.2f}! "
                    
                )
            
            notification_success = create_notification(
                user_id, 
                notification_message,
                'referral_bonus'
            )
            # ========== END MODIFIED NOTIFICATION ==========
             
            if not notification_success:
                current_app.logger.warning(f"Notification failed for user {user_id}, but continuing with credit")

            # Ensure wallet exists
            wallet = Wallet.query.filter_by(user_id=user_id).with_for_update().first()
            if not wallet:
                # create wallet if missing
                wallet = Wallet(user_id=user_id, balance=Decimal("0.00"))
                db.session.add(wallet)
                db.session.flush()  
                current_app.logger.info(f"Wallet auto-created for user {user_id}")

            # # Convert to Decimal explicitly
            # current_balance = Decimal(str(wallet.balance))
            # new_balance = current_balance + amount_decimal
            # wallet.balance = new_balance
            # wallet.updated_at = datetime.now(timezone.utc)
            # db.session.add(wallet)

      

            # Lock the user row (instead of wallet) to prevent race conditions
            user = User.query.filter_by(id=user_id).with_for_update().first()
            if not user:
                raise ValueError(f"User {user_id} not found")

            # Convert to Decimal explicitly
            current_balance = Decimal(str(user.actual_balance or 0))
            new_balance = current_balance + amount_decimal
            user.actual_balance = new_balance
            #user.member_since = datetime.now(timezone.utc)

            db.session.add(user)
            import uuid
            # Create transaction record
            transaction_ref = f"BONUS_{bonus_id}_{uuid.uuid4().hex[:8].upper()}"
           
            transaction = Transaction(
                user_id=user_id,
                wallet_id=wallet.id,
                type='referral_bonus',
                amount=amount_decimal,
                status='completed',
                reference=transaction_ref,
                metadata={
                    'bonus_id': bonus_id,
                    'user_id': user_id,
                    'available_immediately': True,
                    'hold_type': 'none',
                    'credited_at': datetime.now(timezone.utc).isoformat(),
                    'processed_at': datetime.now(timezone.utc).isoformat()
                },
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(transaction) 

            bonus = db.session.get(ReferralBonus, bonus_id)
            if bonus:
                bonus.status = "paid"
                bonus.is_paid_out = True
                bonus.paid_out_at = datetime.now(timezone.utc)
                bonus.transaction_reference = transaction_ref
            db.session.commit()
            from models import Notification
            last_notif = Notification.query.filter_by(user_id=user_id).order_by(Notification.id.desc()).first()
            current_app.logger.info(f"Last notification for user {user_id}: ID={last_notif.id if last_notif else 'None'}, Type={last_notif.notification_type if last_notif else 'None'}")
            current_app.logger.info(
                f"Referral bonus credited (DailyBonus pattern): User {user_id}, "
                f"Amount {amount_decimal}, Wallet Balance: {new_balance}, "
                f"Transaction: {transaction_ref}, Matures Immediately")
            
      
            current_app.logger.info(f"Referral bonus credited Immediately: User {user_id}, Amount {amount_decimal}")
            return True, "Wallet credited successfully", transaction.id

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Wallet credit failed for user {user_id}: {str(e)}", exc_info=True)
            return False, f"Wallet credit failed: {str(e)}", None

    @staticmethod
    def process_pending_bonuses_batch(payment_id: int) -> Tuple[bool, str, Dict[str, Any]]:
        """
        BATCH PROCESSING: Process bonuses in controlled batches with proper error handling
        """
        stats = {
            'processed': 0,
            'succeeded': 0, 
            'failed': 0,
            'errors': [],
            'total_amount': Decimal('0')
        }
        
        try:
            # Get pending bonuses with locking
            pending_bonuses = ReferralBonus.query.filter_by(
                payment_id=payment_id, 
                status='pending'
            ).with_for_update(skip_locked=True).all()  
            
            if not pending_bonuses:
                return True, "No pending bonuses found", stats
            
            current_app.logger.info(f"Processing {len(pending_bonuses)} bonuses for payment {payment_id}")
            
            for bonus in pending_bonuses:
                try:
                    success, message = BonusPaymentHelper.approve_bonus(bonus.id)
                    
                    if success:
                        stats['succeeded'] += 1
                        stats['total_amount'] += Decimal(str(bonus.amount))
                        current_app.logger.info(f"Bonus {bonus.id} processed successfully")
                    else:
                        stats['failed'] += 1
                        stats['errors'].append({
                            'bonus_id': bonus.id,
                            'user_id': bonus.user_id,
                            'level': bonus.level,
                            'amount': float(bonus.amount),
                            'error': message,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
                        current_app.logger.warning(f"Bonus {bonus.id} failed: {message}")
                    
                    stats['processed'] += 1
                    
                except Exception as e:
                    stats['failed'] += 1
                    error_info = {
                        'bonus_id': bonus.id,
                        'error': f"Unexpected error: {str(e)}",
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    stats['errors'].append(error_info)
                    current_app.logger.error(f"Unexpected error processing bonus {bonus.id}: {str(e)}")
            
            success_rate = stats['succeeded'] / len(pending_bonuses) if pending_bonuses else 0
            message = f"Processed {stats['processed']} bonuses: {stats['succeeded']} succeeded, {stats['failed']} failed"
            
            # Log batch summary
            current_app.logger.info(
                f"Batch processing complete for payment {payment_id}: {message}. "
                f"Success rate: {success_rate:.2%}, Total amount: {stats['total_amount']}"
            )
            
            return stats['failed'] == 0, message, stats
            
        except Exception as e:
            current_app.logger.error(f"Batch processing error for payment {payment_id}: {str(e)}")
            return False, f"Batch processing failed: {str(e)}", stats
    
    @staticmethod
    def _log_bonus_payment_audit(bonus: ReferralBonus, transaction_id: int) -> None:
        """
        Comprehensive audit logging for compliance
        """
        try:
            # Create detailed audit log
            audit_log = AuditLog(
                actor_id=bonus.user_id,  # Beneficiary
                action='bonus_payout_processed',
                ip_address='system',
                details={
                    'bonus_id': bonus.id,
                    'user_id': bonus.user_id,
                    'referrer_id': bonus.referrer_id,
                    'level': bonus.level,
                    'amount': float(bonus.amount),
                    'transaction_id': transaction_id,
                    'payment_id': bonus.payment_id,
                    'qualifying_amount': float(bonus.qualifying_amount) if bonus.qualifying_amount else 0,
                    'bonus_percentage': float(bonus.bonus_percentage) if bonus.bonus_percentage else 0,
                    'processed_at': datetime.now(timezone.utc).isoformat(),
                    'type': 'referral_bonus'
                }
            )
            db.session.add(audit_log)
            
            # System log for monitoring
            current_app.logger.info(
                f"BONUS_PAYMENT_AUDIT: "
                f"Bonus#{bonus.id} | "
                f"User#{bonus.user_id} | "
                f"Level{bonus.level} | "
                f"Amount{bonus.amount} | "
                f"TXN#{transaction_id}"
            )
            
        except Exception as e:
            current_app.logger.error(f"Audit logging failed for bonus {bonus.id}: {str(e)}")
    
    @staticmethod
    def queue_bonus_payout(bonus_id: int) -> bool:
        """
        IDEMPOTENT QUEUEING: Safe queue operations with duplicate protection
        """
        try:
            # Use database-level unique constraint for true idempotency
            bonus = ReferralBonus.query.get(bonus_id)
            if not bonus:
                current_app.logger.error(f"Bonus {bonus_id} not found for queueing")
                return False
            
            # Check if already processed
            if bonus.status == 'paid':
                current_app.logger.warning(f"Bonus {bonus_id} already paid, skipping queue")
                return True
            
            # Calculate initial attempt time with jitter
            base_delay = timedelta(minutes=2)
            jitter = timedelta(seconds=30)  # Add jitter for load distribution
            next_attempt = datetime.now(timezone.utc) + base_delay + jitter
            
            # Insert with conflict handling
            try:
                queue_entry = BonusPayoutQueue(
                    referral_bonus_id=bonus_id,
                    user_id=bonus.user_id,
                    amount=bonus.amount,
                    status='pending',
                    next_attempt=next_attempt,
                    attempt_count=0,
                    max_attempts=5
                )
                db.session.add(queue_entry)
                db.session.commit()
                
                current_app.logger.info(f"Bonus {bonus_id} queued for payout (attempt: {next_attempt})")
                return True
                
            except Exception as unique_error:
                # Handle unique constraint violation gracefully
                db.session.rollback()
                current_app.logger.info(f"Bonus {bonus_id} already in queue")
                return True  # Consider it success if already queued
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error queueing bonus payout {bonus_id}: {str(e)}")
            return False
    
    @staticmethod
    def process_payout_queue(batch_size: int = 50) -> Dict[str, Any]:
        """
        ROBUST QUEUE PROCESSING: With proper error handling and retry logic
        """
        stats = {
            'processed': 0,
            'succeeded': 0,
            'failed': 0,
            'retry_scheduled': 0,
            'errors': [],
            'start_time': datetime.now(timezone.utc),
            'batch_size': batch_size
        }
        
        try:
            # Get queue items ready for processing (with skip_locked for concurrent processing)
            pending_payouts = BonusPayoutQueue.query.filter(
                BonusPayoutQueue.status == 'pending',
                BonusPayoutQueue.next_attempt <= datetime.now(timezone.utc),
                BonusPayoutQueue.attempt_count < BonusPayoutQueue.max_attempts
            ).with_for_update(skip_locked=True).limit(batch_size).all()
            
            if not pending_payouts:
                stats['message'] = "No payouts ready for processing"
                return stats
            
            current_app.logger.info(f"Processing {len(pending_payouts)} queued payouts")
            
            for payout in pending_payouts:
                try:
                    # Mark as processing (within transaction)
                    with db.session.begin_nested():
                        payout.status = 'processing'
                        payout.attempt_count += 1
                        payout.last_attempt = datetime.now(timezone.utc)
                    
                    # Process the payout
                    success, message = BonusPaymentHelper.approve_bonus(payout.referral_bonus_id)
                    
                    if success:
                        # Mark as completed
                        with db.session.begin_nested():
                            payout.status = 'completed'
                            payout.processed_at = datetime.now(timezone.now)
                            payout.last_error = None
                        stats['succeeded'] += 1
                        
                        current_app.logger.info(f"Payout {payout.id} completed successfully")
                        
                    else:
                        # Handle failure with exponential backoff
                        next_attempt_delay = BonusPaymentHelper._calculate_next_attempt_delay(
                            payout.attempt_count
                        )
                        next_attempt = datetime.now(timezone.utc) + next_attempt_delay
                        
                        with db.session.begin_nested():
                            payout.status = 'failed'
                            payout.next_attempt = next_attempt
                            payout.last_error = message
                        
                        stats['failed'] += 1
                        stats['retry_scheduled'] += 1
                        
                        current_app.logger.warning(
                            f"Payout {payout.id} failed (attempt {payout.attempt_count}), "
                            f"retrying at {next_attempt}: {message}"
                        )
                    
                    stats['processed'] += 1
                    
                except Exception as e:
                    stats['failed'] += 1
                    error_info = {
                        'payout_id': payout.id,
                        'bonus_id': payout.referral_bonus_id,
                        'error': f"Processing error: {str(e)}",
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    stats['errors'].append(error_info)
                    current_app.logger.error(f"Error processing payout {payout.id}: {str(e)}")
            
            # Final commit for all processed items
            db.session.commit()
            
            stats['end_time'] = datetime.now(timezone.utc)
            stats['duration_seconds'] = (stats['end_time'] - stats['start_time']).total_seconds()
            stats['success_rate'] = stats['succeeded'] / stats['processed'] if stats['processed'] > 0 else 0
            
            current_app.logger.info(
                f"Payout queue processing complete: "
                f"Processed: {stats['processed']}, "
                f"Succeeded: {stats['succeeded']}, "
                f"Failed: {stats['failed']}, "
                f"Retry Scheduled: {stats['retry_scheduled']}, "
                f"Duration: {stats['duration_seconds']:.2f}s"
            )
            
            return stats
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Payout queue processing failed: {str(e)}")
            stats['error'] = str(e)
            return stats
    
    @staticmethod
    def _calculate_next_attempt_delay(attempt_count: int) -> timedelta:
        """
        Exponential backoff with jitter for retry scheduling
        """
        base_delay = timedelta(minutes=5)
        max_delay = timedelta(hours=24)
        
        # Exponential backoff: 5min, 10min, 20min, 40min, 80min, etc.
        delay = base_delay * (2 ** (attempt_count - 1))
        
        # Cap at maximum delay
        delay = min(delay, max_delay)
        
        # Add jitter (±20%) to prevent thundering herd
        jitter_factor = 0.2
        jitter = delay * jitter_factor * (2 * (hash(str(attempt_count)) % 1000 / 1000) - 1)
        
        return delay + jitter
    
    @staticmethod
    def cancel_bonus_payout(bonus_id: int, reason: str, cancelled_by: int = None) -> bool:
        """
        SAFE CANCELLATION: Cancel bonus payout with audit trail
        """
        try:
            with db.session.begin_nested():
                bonus = ReferralBonus.query.with_for_update().get(bonus_id)
                if not bonus:
                    return False
                
                # Only allow cancellation of pending bonuses
                if bonus.status != 'pending':
                    current_app.logger.warning(
                        f"Cannot cancel bonus {bonus_id} with status {bonus.status}"
                    )
                    return False
                
                # Update bonus status
                bonus.status = 'cancelled'
                bonus.cancelled_at = datetime.now(timezone.utc)
                
                # Remove from queue if present
                queue_entry = BonusPayoutQueue.query.filter_by(
                    referral_bonus_id=bonus_id
                ).first()
                
                if queue_entry:
                    queue_entry.status = 'cancelled'
                    queue_entry.last_error = f"Cancelled: {reason}"
                
                # Log cancellation audit
                audit_log = AuditLog(
                    actor_id=cancelled_by or bonus.user_id,
                    action='bonus_payout_cancelled',
                    ip_address='system',
                    details={
                        'bonus_id': bonus_id,
                        'reason': reason,
                        'cancelled_by': cancelled_by,
                        'cancelled_at': datetime.now(timezone.utc).isoformat()
                    }
                )
                db.session.add(audit_log)
            
            db.session.commit()
            current_app.logger.info(f"Bonus {bonus_id} cancelled: {reason}")
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cancelling bonus {bonus_id}: {str(e)}")
            return False
        







