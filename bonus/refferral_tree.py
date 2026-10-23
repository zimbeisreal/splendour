from decimal import Decimal
from typing import List, Optional, Dict, Any
from flask import current_app
from sqlalchemy import text
from extensions import db
from models import User, ReferralNetwork, ReferralBonus, Wallet, Transaction
import logging
from typing import List, Tuple, Optional
import traceback
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime, timezone


logger = logging.getLogger(__name__)

MAX_REFERRAL_DEPTH = 20  # your 20-level limit





class ReferralTreeHelper:
    """
    Production-ready 20-level referral network helper using closure table pattern.
    Table expected: referral_network(ancestor_id int, descendant_id int, depth smallint)
    """

    @staticmethod
    def is_descendant(ancestor_id: int, descendant_id: int) -> bool:
        """
        Return True if ancestor_id is an ancestor of descendant_id (depth >= 1)
        """
        try:
            row = db.session.execute(
                text(
                    """
                    SELECT 1 FROM referral_network
                    WHERE ancestor_id = :ancestor AND descendant_id = :descendant AND depth >= 1
                    LIMIT 1
                    """
                ),
                {"ancestor": ancestor_id, "descendant": descendant_id},
            ).scalar()
            return bool(row)
        except SQLAlchemyError:
            current_app.logger.error(
                "is_descendant error:\n" + traceback.format_exc()
            )
            # Conservatively return True to prevent cycles
            return True

    @staticmethod
    def add_new_user(new_user_id: int, referrer_id: int) -> bool:
        """
        Add a new user to the referral network as a child of `referrer_id`.
        Must be called inside an existing transaction (no begin/commit here).
        """
        print("REFERRAL TREE HELPER CALLED")
        print("new_user_id:", new_user_id, "referrer_id:", referrer_id)

        try:
            # 1️⃣ Prevent self-referral
            if new_user_id == referrer_id:
                print("Error: User cannot refer themselves.")
                current_app.logger.warning("User attempted self-referral.")
                return False

            # 2️⃣ Prevent cycles
            cycle = ReferralTreeHelper.is_descendant(new_user_id, referrer_id)
            print("Cycle check:", cycle)
            if cycle:
                print("Error: Referrer is a descendant of the new user. Cycle detected.")
                current_app.logger.warning(
                    f"Cycle detected: referrer_id={referrer_id} is descendant of new_user_id={new_user_id}"
                )
                return False

            # 3️⃣ Insert self-reference for new user
            print("Inserting self-reference for new user")
            db.session.execute(
                text(
                    """
                    INSERT INTO referral_network (ancestor_id, descendant_id, depth, path_length)
                    VALUES (:uid, :uid, 0, 0)
                    ON CONFLICT (ancestor_id, descendant_id) DO NOTHING
                    """
                ),
                {"uid": new_user_id},
            )

            # 4️⃣ Insert self-reference for referrer (idempotent)
            print("Inserting self-reference for referrer")
            db.session.execute(
                text(
                    """
                    INSERT INTO referral_network (ancestor_id, descendant_id, depth, path_length)
                    VALUES (:rid, :rid, 0, 0)
                    ON CONFLICT (ancestor_id, descendant_id) DO NOTHING
                    """
                ),
                {"rid": referrer_id},
            )

            # 5️⃣ Insert all ancestor relationships
            print("Inserting ancestor->new_user relationships")
            db.session.execute(
                text(
                    """
                    INSERT INTO referral_network (ancestor_id, descendant_id, depth, path_length)
                    SELECT ancestor_id, :new_id, depth+1, path_length
                    FROM referral_network
                    WHERE descendant_id = :ref_id AND depth < :max_depth
                    ON CONFLICT (ancestor_id, descendant_id) DO NOTHING
                    """
                ),
                {"new_id": new_user_id, "ref_id": referrer_id, "max_depth": MAX_REFERRAL_DEPTH},
            )

            # 6️⃣ Insert direct referrer relationship
            print("Inserting direct referrer->new_user relationship")
            db.session.execute(
                text(
                    """
                    INSERT INTO referral_network (ancestor_id, descendant_id, depth, path_length)
                    VALUES (:ref_id, :new_id, 1, 0)
                    ON CONFLICT (ancestor_id, descendant_id) DO NOTHING
                    """
                ),
                {"ref_id": referrer_id, "new_id": new_user_id},
            )

            print("Referral network insertion completed successfully")
            return True

        except SQLAlchemyError:
            print("Referral tree insertion FAILED")
            current_app.logger.error("SQLAlchemyError during add_new_user:\n" + traceback.format_exc())
            return False

        except Exception:
            print("Referral tree insertion FAILED (unexpected error)")
            current_app.logger.error("Unexpected error during add_new_user:\n" + traceback.format_exc())
            return False


    @staticmethod
    def is_descendant(ancestor_id: int, descendant_id: int) -> bool:
        """
        Returns True if ancestor_id is an ancestor of descendant_id (depth >= 1)
        """
        try:
            row = db.session.execute(
                text("""
                    SELECT 1 FROM referral_network
                    WHERE ancestor_id = :ancestor AND descendant_id = :descendant AND depth >= 1
                    LIMIT 1
                """),
                {"ancestor": ancestor_id, "descendant": descendant_id},
            ).scalar()
            return bool(row)
        except Exception:
            current_app.logger.error("is_descendant error:\n" + traceback.format_exc())
            return True  # conservative: treat as cycle if query fails


#     # -------------------------
#     # Maintenance helpers
#     # -------------------------
    @staticmethod
    def backfill_self_rows(batch_size: int = 1000) -> int:
        """
        Backfill missing self rows for all users. Returns number of rows inserted.
        Use in migrations / maintenance.
        """
        try:
            with db.session.begin():
                res = db.session.execute(
                    text(
                        """
                        INSERT INTO referral_network (ancestor_id, descendant_id, depth)
                        SELECT id, id, 0
                        FROM users
                        WHERE id NOT IN (
                            SELECT descendant_id FROM referral_network WHERE depth = 0
                        )
                        LIMIT :batch_size
                        """
                    ),
                    {"batch_size": batch_size},
                )
            # res.rowcount may be DB dependent; return positive if no exception
            return 1
        except Exception:
            current_app.logger.exception("backfill_self_rows failed.")
            return 0


    @staticmethod
    def get_ancestors_optimized(user_id: int, max_levels: int = 20) -> List[Dict]:
        """
        Optimized ancestor query with user data in single query
        """
        query = text("""
            SELECT 
                u.id, u.username, u.email, u.phone, u.is_active, u.is_verified,
                rn.depth as level
            FROM referral_network rn
            JOIN users u ON rn.ancestor_id = u.id
            WHERE rn.descendant_id = :user_id 
            AND rn.depth BETWEEN 1 AND :max_levels
            AND u.is_active = TRUE
            ORDER BY rn.depth ASC
        """)
        
        result = db.session.execute(query, {
            'user_id': user_id, 
            'max_levels': max_levels
        })
        
        return [dict(row) for row in result]
    
    @staticmethod
    def get_descendants_optimized(user_id: int, level: int = None) -> List[Dict]:
        """
        Get descendants at specific level or all levels
        """
        if level:
            query = text("""
                SELECT u.id, u.username, u.created_at, u.is_active
                FROM referral_network rn
                JOIN users u ON rn.descendant_id = u.id
                WHERE rn.ancestor_id = :user_id 
                AND rn.depth = :level
                AND u.is_active = TRUE
            """)
            result = db.session.execute(query, {'user_id': user_id, 'level': level})
        else:
            query = text("""
                SELECT u.id, u.username, u.created_at, u.is_active, rn.depth as level
                FROM referral_network rn
                JOIN users u ON rn.descendant_id = u.id
                WHERE rn.ancestor_id = :user_id 
                AND rn.depth > 0
                AND u.is_active = TRUE
                ORDER BY rn.depth ASC
            """)
            result = db.session.execute(query, {'user_id': user_id})
        
        return [dict(row) for row in result]

    @staticmethod
    def validate_referrer(referrer_id: int, new_user_id: int) -> tuple[bool, str]:
        """
        Validate if referrer can refer new user
        Returns: (is_valid, error_message)
        """
        try:
            # Check if referrer exists and is active
            referrer = User.query.filter_by(id=referrer_id, is_active=True).first()
            if not referrer:
                return False, "Referrer does not exist or is inactive"
            
            # Check if referrer is verified
            if not referrer.is_verified:
                return False, "Referrer is not verified"
            
            # Check for self-referral
            if referrer_id == new_user_id:
                return False, "Self-referral is not allowed"
            
            # Check for cycles
            if ReferralTreeHelper.check_cycle(referrer_id, new_user_id):
                return False, "Circular referral detected"
            
            # Check if referrer is a descendant of new user
            if ReferralTreeHelper.is_descendant(referrer_id, new_user_id):
                return False, "Referrer cannot be a descendant of new user"
            
            return True, "Valid referrer"
            
        except Exception as e:
            current_app.logger.error(f"Error validating referrer {referrer_id}: {str(e)}")
            return False, f"Validation error: {str(e)}"

    @staticmethod
    def check_cycle(referrer_id: int, potential_child_id: int) -> bool:
        """Check if adding this referral would create a cycle"""
        try:
            # If potential child is already an ancestor of referrer, it would create a cycle
            return ReferralTreeHelper.is_descendant(referrer_id, potential_child_id)
        except Exception as e:
            current_app.logger.error(f"Error checking cycle: {str(e)}")
            return True  # Fail safe - assume cycle exists on error

    @staticmethod
    def build_referral_path(user_id: int) -> List[int]:
        """Build the complete referral path from root to user"""
        try:
            ancestors = ReferralTreeHelper.get_ancestors_optimized(user_id, 20)
            path = [ancestor['user_id'] for ancestor in ancestors]
            path.reverse()  # Root first, then descendants
            path.append(user_id)  # Add current user at the end
            return path
        except Exception as e:
            current_app.logger.error(f"Error building referral path for {user_id}: {str(e)}")
            return []

    @staticmethod
    def store_referral_path(user_id: int, ancestry_list: List[int]) -> bool:
        """
        Store the referral network relationships using closure table pattern
        """
        try:
            # Delete existing network entries for this user
            db.session.execute(
                text("DELETE FROM referral_network WHERE descendant_id = :user_id"),
                {'user_id': user_id}
            )
            
            # Insert self-reference (depth 0)
            db.session.execute(
                text("""
                    INSERT INTO referral_network (ancestor_id, descendant_id, depth, path_length)
                    VALUES (:user_id, :user_id, 0, 0)
                """),
                {'user_id': user_id}
            )
            
            # Insert relationships with all ancestors
            for i, ancestor_id in enumerate(ancestry_list):
                depth = len(ancestry_list) - i
                path_length = depth
                
                db.session.execute(
                    text("""
                        INSERT INTO referral_network (ancestor_id, descendant_id, depth, path_length)
                        VALUES (:ancestor_id, :descendant_id, :depth, :path_length)
                    """),
                    {
                        'ancestor_id': ancestor_id,
                        'descendant_id': user_id,
                        'depth': depth,
                        'path_length': path_length
                    }
                )
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error storing referral path for {user_id}: {str(e)}")
            return False

   
    # Add this method to your existing ReferralTreeHelper class

    @staticmethod
    def initialize_standalone_user(user_id: int) -> bool:
        """
        Initialize a user who joined without referral (standalone in network)
        """
        try:
           
            query = text("""
                INSERT INTO referral_network (ancestor_id, descendant_id, depth, path_length)
                VALUES (:user_id, :user_id, 0, 0)
            """)
            
            db.session.execute(query, {'user_id': user_id})
            
            # Update user's network depth to 0 (root level)
            user = User.query.get(user_id)
            if user:
                user.network_depth = 0
                user.direct_referrals_count = 0
                user.total_network_size = 0
            
            current_app.logger.info(f"Initialized standalone user {user_id} in referral network")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error initializing standalone user {user_id}: {str(e)}")
            return False

    @staticmethod
    def get_user_network_summary(user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive network summary for a user
        """
        try:
            # Get ancestors (upline)
            ancestors = ReferralTreeHelper.get_ancestors_optimized(user_id, 20)
            
            # Get direct descendants (level 1 downline)
            direct_descendants_query = text("""
                SELECT u.id, u.username, u.created_at, u.is_active
                FROM referral_network rn
                JOIN users u ON rn.descendant_id = u.id
                WHERE rn.ancestor_id = :user_id 
                AND rn.depth = 1
                ORDER BY u.created_at DESC
            """)
            
            direct_descendants_result = db.session.execute(
                direct_descendants_query, 
                {'user_id': user_id}
            )
            direct_descendants = [
                {
                    'id': row.id,
                    'username': row.username, 
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                    'is_active': row.is_active
                }
                for row in direct_descendants_result
            ]
            
            # Get total network size
            total_network_query = text("""
                SELECT COUNT(DISTINCT descendant_id) as total_descendants
                FROM referral_network 
                WHERE ancestor_id = :user_id 
                AND depth > 0
            """)
            
            total_network_result = db.session.execute(
                total_network_query, 
                {'user_id': user_id}
            ).fetchone()
            
            total_network_size = total_network_result.total_descendants if total_network_result else 0
            
            return {
                'user_id': user_id,
                'ancestors_count': len(ancestors),
                'ancestors': ancestors,
                'direct_descendants_count': len(direct_descendants),
                'direct_descendants': direct_descendants,
                'total_network_size': total_network_size,
                'network_depth': ancestors[-1]['level'] if ancestors else 0
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting network summary for user {user_id}: {str(e)}")
            return {
                'user_id': user_id,
                'ancestors_count': 0,
                'ancestors': [],
                'direct_descendants_count': 0, 
                'direct_descendants': [],
                'total_network_size': 0,
                'network_depth': 0
            }

 
    #=================================================================================
    # -------------GET DIRECT REFERRER AND CREDIT WALLETS ATOMICALLY-------------
    #=================================================================================
    
    
    @staticmethod
    def get_direct_referrer(user_id: int) -> Optional[Dict]:
        """
        Get the direct referrer from the referrals table
        """
        result = db.session.execute(
            text("""
                SELECT u.id, u.username, u.email
                FROM referrals r
                JOIN users u ON r.referrer_id = u.id
                WHERE r.referred_id = :user_id AND r.status = 'active'
                LIMIT 1
            """),
            {"user_id": user_id}
        ).fetchone()
        
        if not result:
            return None
        
        return {
            "id": result[0],
            "username": result[1],
            "email": result[2]
        }
    
    @staticmethod
    def credit_direct_referrer_wallet(user_id: int, purchase_amount: Decimal, referrer_id: int, bonus_id: int = None) -> Tuple[bool, str, Optional[int]]:
        """
        Safely credit a direct referrer's wallet with commission from a purchase.
        Follows same pattern as _credit_user_wallet_atomic.
        
        Args:
            user_id: The user who made the purchase (source)
            purchase_amount: Total purchase amount
            referrer_id: The direct referrer being credited
            bonus_id: Optional bonus record ID for tracking
        
        Returns:
            Tuple[bool, str, Optional[int]]: (success, message, transaction_id)
        """
        try:
            commission_rate = Decimal("0.10")  # 10% commission
            commission_amount = purchase_amount * commission_rate
            
            if commission_amount <= Decimal("0"):
                return False, "Invalid commission amount", None
            
            # ========== CREATE NOTIFICATION FOR REFERRER ==========
            from bonus.payment_processor import create_notification
            
            notification_message = (
                f"🎉 You've received a direct referral bonus of UGX {commission_amount:,.2f}! "
                f"✨ User {user_id} made a purchase of UGX {purchase_amount:,.2f}. "
                f"Bonus is visible in your wallet and is available for immediate withdrawal."
            )
            
            notification_success = create_notification(
                referrer_id, 
                notification_message,
                'direct_referral_bonus'
            )
            
            if not notification_success:
                current_app.logger.warning(f"Notification failed for referrer {referrer_id}, but continuing with credit")
            
            # ========== ENSURE WALLET EXISTS WITH FOR UPDATE LOCK ==========
            wallet = Wallet.query.filter_by(user_id=referrer_id).with_for_update().first()
            if not wallet:
                # Create wallet if missing
                wallet = Wallet(user_id=referrer_id, balance=Decimal("0.00"))
                db.session.add(wallet)
                db.session.flush()
                current_app.logger.info(f"Wallet auto-created for referrer {referrer_id}")
            
            # ========== UPDATE WALLET BALANCE ==========
            current_balance = Decimal(str(wallet.balance))
            new_balance = current_balance + commission_amount
            wallet.balance = new_balance
            wallet.updated_at = datetime.now(timezone.utc)
            db.session.add(wallet)
            
            # ========== CREATE TRANSACTION RECORD ==========
            import uuid
            transaction_ref = f"DIRECT_REFERRAL_{user_id}_{referrer_id}_{uuid.uuid4().hex[:8].upper()}"
            
            transaction = Transaction(
                user_id=referrer_id,
                wallet_id=wallet.id,
                type='direct_referral_bonus',
                amount=commission_amount,
                status='completed',
                reference=transaction_ref,
                metadata={
                    'source_user_id': user_id,
                    'purchase_amount': str(purchase_amount),
                    'commission_rate': str(commission_rate),
                    'bonus_id': bonus_id if bonus_id else None,
                    'available_immediately': True,
                    'hold_type': 'none',
                    'credited_at': datetime.now(timezone.utc).isoformat(),
                    'processed_at': datetime.now(timezone.utc).isoformat()
                },
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(transaction)
            
            # ========== UPDATE REFERRAL BONUS RECORD IF PROVIDED ==========
            if bonus_id:
                bonus = db.session.get(ReferralBonus, bonus_id)
                if bonus:
                    bonus.status = "paid"
                    bonus.is_paid_out = True
                    bonus.paid_out_at = datetime.now(timezone.utc)
                    bonus.transaction_reference = transaction_ref
            
            db.session.commit()
            
            current_app.logger.info(
                f"Direct referral bonus credited: Referrer {referrer_id}, "
                f"Amount {commission_amount}, Source User {user_id}, "
                f"Wallet Balance: {new_balance}, Transaction: {transaction_ref}"
            )
            
            return True, f"Direct referrer credited UGX {commission_amount:,.2f}", transaction.id
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Direct referral credit failed for referrer {referrer_id}: {str(e)}", exc_info=True)
            return False, f"Wallet credit failed: {str(e)}", None
    
    @staticmethod
    def process_direct_referral_bonus(user_id: int, purchase_amount: Decimal) -> Tuple[bool, str, Optional[int]]:
        """
        Orchestrate the entire direct referral bonus process.
        
        Args:
            user_id: The user who made the purchase
            purchase_amount: Total purchase amount
        
        Returns:
            Tuple[bool, str, Optional[int]]: (success, message, transaction_id)
        """
        # 1. Get direct referrer
        referrer = ReferralTreeHelper.get_direct_referrer(user_id)
        
        if not referrer:
            current_app.logger.info(f"No direct referrer found for user {user_id}")
            return False, "No direct referrer found", None
        
        # 2. Credit the referrer's wallet
        success, message, transaction_id = ReferralTreeHelper.credit_direct_referrer_wallet(
            user_id=user_id,
            purchase_amount=purchase_amount,
            referrer_id=referrer["id"],
            bonus_id=None  # You can pass a bonus record ID if you track these separately
        )
        
        return success, message, transaction_id