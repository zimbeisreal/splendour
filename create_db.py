from app import app, db
from sqlalchemy import text

with app.app_context():
    rows = db.session.execute(
        text("select tablename from pg_tables where schemaname='public' order by tablename")
    ).scalars().all()
    print(f"{len(rows)} tables:")
    for t in rows:
        print(" -", t)



# #!/usr/bin/env python3
# """
# Simple script to add 10,000 UGX to a user's balance by phone number
# Usage: python add_balance.py
# """

# import sys
# from app import app
# from models import db, User

# def add_balance_to_user(phone_number, amount=100000):
#     """
#     Add balance to a user by phone number
#     """
#     with app.app_context():
#         try:
#             # Find user by phone
#             user = User.query.filter_by(phone=phone_number).first()
            
#             if not user:
#                 print(f"❌ User with phone '{phone_number}' not found!")
#                 return False
            
#             print(f"✅ Found user: {user.username} (ID: {user.id})")
#             print(f"   Phone: {user.phone}")
#             print(f"   Current balance: UGX {user.actual_balance or 0:,.2f}")
            
#             # Add amount to actual_balance
#             user.actual_balance = (user.actual_balance or 0) + amount
#             db.session.commit()
            
#             print(f"✅ Added UGX {amount:,.2f} to user's balance")
#             print(f"   New balance: UGX {user.actual_balance:,.2f}")
#             return True
            
#         except Exception as e:
#             print(f"❌ Error: {e}")
#             db.session.rollback()
#             import traceback
#             traceback.print_exc()
#             return False

# def add_balance_to_user_by_username(username, amount=100000):
#     """
#     Add balance to a user by username (alternative method)
#     """
#     with app.app_context():
#         try:
#             # Find user by username
#             user = User.query.filter_by(username=username).first()
            
#             if not user:
#                 print(f"❌ User with username '{username}' not found!")
#                 return False
            
#             print(f"✅ Found user: {user.username} (ID: {user.id})")
#             print(f"   Phone: {user.phone}")
#             print(f"   Current balance: UGX {user.actual_balance or 0:,.2f}")
            
#             # Add amount to actual_balance
#             user.actual_balance = (user.actual_balance or 0) + amount
#             db.session.commit()
            
#             print(f"✅ Added UGX {amount:,.2f} to user's balance")
#             print(f"   New balance: UGX {user.actual_balance:,.2f}")
#             return True
            
#         except Exception as e:
#             print(f"❌ Error: {e}")
#             db.session.rollback()
#             import traceback
#             traceback.print_exc()
#             return False

# def check_user_balance(phone_number):
#     """
#     Check user balance without modifying
#     """
#     with app.app_context():
#         try:
#             user = User.query.filter_by(phone=phone_number).first()
#             if not user:
#                 print(f"❌ User with phone '{phone_number}' not found!")
#                 return None
            
#             print(f"📱 User: {user.username} (ID: {user.id})")
#             print(f"   Phone: {user.phone}")
#             print(f"   Balance: UGX {user.actual_balance or 0:,.2f}")
#             return user.actual_balance
            
#         except Exception as e:
#             print(f"❌ Error: {e}")
#             return None

# if __name__ == "__main__":
#     # Target phone number
#     phone = "0756393205"
#     amount = 100000
    
#     print("=" * 60)
#     print("💰 ADD BALANCE TO USER")
#     print("=" * 60)
    
#     # Check current balance first
#     print("\n📊 Current balance:")
#     check_user_balance(phone)
    
#     # Add balance
#     print(f"\n💵 Adding UGX {amount:,.2f}...")
#     success = add_balance_to_user(phone, amount)
    
#     if success:
#         print("\n📊 Updated balance:")
#         check_user_balance(phone)
#         print("\n✅ Done!")
#     else:
#         print("\n❌ Failed to add balance")
#         sys.exit(1)

# #!/usr/bin/env python3
# # """
# # Simple script to create wallet for user ID 2 and add 5,000 UGX
# # """

# # from app import app
# # from models import db, User, Wallet

# # def create_wallet_for_user(user_id=2, initial_balance=5000):
# #     """
# #     Create a wallet for a user with initial balance
# #     """
# #     with app.app_context():
# #         try:
# #             # Check if user exists
# #             user = User.query.get(user_id)
# #             if not user:
# #                 print(f"❌ User with ID {user_id} not found!")
# #                 return False
            
# #             print(f"✅ Found user: {user.username} (ID: {user.id})")
# #             print(f"   Phone: {user.phone}")
            
# #             # Check if wallet already exists
# #             existing_wallet = Wallet.query.filter_by(user_id=user.id).first()
# #             if existing_wallet:
# #                 print(f"⚠️  Wallet already exists for user {user.username}")
# #                 print(f"   Current balance: UGX {existing_wallet.balance:,.2f}")
                
# #                 # Add to existing wallet
# #                 existing_wallet.balance = (existing_wallet.balance or 0) + initial_balance
# #                 db.session.commit()
                
# #                 print(f"✅ Added UGX {initial_balance:,.2f} to existing wallet")
# #                 print(f"   New balance: UGX {existing_wallet.balance:,.2f}")
# #                 return True
            
# #             # Create new wallet
# #             wallet = Wallet(
# #                 user_id=user.id,
# #                 balance=initial_balance,
# #                 currency='UGX'
# #             )
# #             db.session.add(wallet)
# #             db.session.commit()
            
# #             print(f"✅ Wallet created for user {user.username}")
# #             print(f"   Balance: UGX {wallet.balance:,.2f}")
# #             print(f"   Currency: {wallet.currency}")
# #             return True
            
# #         except Exception as e:
# #             print(f"❌ Error: {e}")
# #             db.session.rollback()
# #             import traceback
# #             traceback.print_exc()
# #             return False

# # def check_wallet(user_id=2):
# #     """
# #     Check wallet balance for a user
# #     """
# #     with app.app_context():
# #         try:
# #             wallet = Wallet.query.filter_by(user_id=user_id).first()
# #             if not wallet:
# #                 print(f"❌ No wallet found for user ID {user_id}")
# #                 return None
            
# #             user = User.query.get(user_id)
# #             print(f"\n📊 Wallet Details:")
# #             print(f"   User: {user.username} (ID: {user.id})")
# #             print(f"   Balance: UGX {wallet.balance:,.2f}")
# #             print(f"   Currency: {wallet.currency}")
# #             print(f"   Created: {wallet.created_at}")
# #             return wallet.balance
            
# #         except Exception as e:
# #             print(f"❌ Error: {e}")
# #             return None

# # if __name__ == "__main__":
# #     print("=" * 60)
# #     print("💰 CREATE WALLET FOR USER ID 2")
# #     print("=" * 60)
    
# #     # Check if wallet exists
# #     print("\n📊 Checking existing wallet...")
# #     check_wallet(2)
    
# #     # Create/update wallet with 5,000 UGX
# #     print(f"\n💵 Creating wallet with UGX 5,000...")
# #     success = create_wallet_for_user(2, 50000)
    
# #     if success:
# #         print("\n✅ Wallet ready!")
# #         check_wallet(2)
# #     else:
# #         print("\n❌ Failed to create wallet")