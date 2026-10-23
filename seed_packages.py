"""
seed_packages.py - express Package Catalog Seeder
Usage: python seed_packages.py [--clear] [--test]
"""

import sys
import json
import logging
from datetime import datetime, timedelta
from app import app
from extensions import db
from models import PackageCatalog, Package, User, Payment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# PACKAGE CATALOG DATA - Complete with all fields
# ============================================================

# ============================================================
# express · EXPRESS · PACKAGE CATALOG
# Aligned with the frontend PRODUCTS array in static/js/profile.js
# ============================================================

PACKAGE_CATALOG = {

    # ────────────────────────────────────────────────────────
    # DAILY WITHDRAWAL · 15% per day × 15 days · total = profit
    # ────────────────────────────────────────────────────────
    "daily_20k": {
        "name": "Daily 20K",
        "display_name": "Daily 20K",
        "amount": 20000,
        "bonus_percentage": 15.00,
        "duration_days": 15,
        "reward_description": "Earn UGX 3,000 per day for 15 days. Total profit: UGX 45,000.",
        "features": {
            "daily_profit": 3000,
            "total_profit": 45000,
            "total_returns": 45000,
            "daily_rate": 15.0,
            "total_rate": 225.0,
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
        "name": "Daily 50K",
        "display_name": "Daily 50K",
        "amount": 50000,
        "bonus_percentage": 15.00,
        "duration_days": 15,
        "reward_description": "Earn UGX 7,500 per day for 15 days. Total profit: UGX 112,500.",
        "features": {
            "daily_profit": 7500,
            "total_profit": 112500,
            "total_returns": 112500,
            "daily_rate": 15.0,
            "total_rate": 225.0,
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
    "daily_100k": {
        "name": "Daily 100K",
        "display_name": "Daily 100K",
        "amount": 100000,
        "bonus_percentage": 15.00,
        "duration_days": 15,
        "reward_description": "Earn UGX 15,000 per day for 15 days. Total profit: UGX 225,000.",
        "features": {
            "daily_profit": 15000,
            "total_profit": 225000,
            "total_returns": 225000,
            "daily_rate": 15.0,
            "total_rate": 225.0,
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
    "daily_200k": {
        "name": "Daily 200K",
        "display_name": "Daily 200K",
        "amount": 200000,
        "bonus_percentage": 15.00,
        "duration_days": 15,
        "reward_description": "Earn UGX 30,000 per day for 15 days. Total profit: UGX 450,000.",
        "features": {
            "daily_profit": 30000,
            "total_profit": 450000,
            "total_returns": 450000,
            "daily_rate": 15.0,
            "total_rate": 225.0,
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

    # ────────────────────────────────────────────────────────
    # LOCK PRODUCTS · fixed returns (capital + profit)
    # ────────────────────────────────────────────────────────
    "lock_1d_30k": {
        "name": "1-Day 30K",
        "display_name": "1-Day 30K",
        "amount": 30000,
        "bonus_percentage": 33.33,
        "duration_days": 1,
        "reward_description": "Lock UGX 30,000 for 1 day. Total return: UGX 40,000.",
        "features": {
            "daily_profit": 0,
            "total_profit": 10000,
            "total_returns": 40000,
            "daily_rate": 0.0,
            "total_rate": 33.33,
            "referral_bonus": 0,
            "support_level": "1-Day",
            "machine_emoji": "",
        },
        "is_active": True,
        "is_locking_package": True,
        "locking_bonus_rate": 0.0,
        "machine_eligible": True,
        "machine_type": "locked",
        "lock_minimum_days": 1,
        "lock_maximum_days": 1,
        "lock_bonus_tiers": {},
    },
    "lock_3d_50k": {
        "name": "3-Day 50K",
        "display_name": "3-Day 50K",
        "amount": 50000,
        "bonus_percentage": 62.00,
        "duration_days": 3,
        "reward_description": "Lock UGX 50,000 for 3 days. Total return: UGX 81,000.",
        "features": {
            "daily_profit": 0,
            "total_profit": 31000,
            "total_returns": 81000,
            "daily_rate": 0.0,
            "total_rate": 62.0,
            "referral_bonus": 0,
            "support_level": "3-Day",
            "machine_emoji": "",
        },
        "is_active": True,
        "is_locking_package": True,
        "locking_bonus_rate": 0.0,
        "machine_eligible": True,
        "machine_type": "locked",
        "lock_minimum_days": 3,
        "lock_maximum_days": 3,
        "lock_bonus_tiers": {},
    },
    "lock_3d_100k": {
        "name": "3-Day 100K",
        "display_name": "3-Day 100K",
        "amount": 100000,
        "bonus_percentage": 43.00,
        "duration_days": 3,
        "reward_description": "Lock UGX 100,000 for 3 days. Total return: UGX 143,000.",
        "features": {
            "daily_profit": 0,
            "total_profit": 43000,
            "total_returns": 143000,
            "daily_rate": 0.0,
            "total_rate": 43.0,
            "referral_bonus": 0,
            "support_level": "3-Day",
            "machine_emoji": "",
        },
        "is_active": True,
        "is_locking_package": True,
        "locking_bonus_rate": 0.0,
        "machine_eligible": True,
        "machine_type": "locked",
        "lock_minimum_days": 3,
        "lock_maximum_days": 3,
        "lock_bonus_tiers": {},
    },
    "lock_7d_55k": {
        "name": "7-Day 55K",
        "display_name": "7-Day 55K",
        "amount": 55000,
        "bonus_percentage": 67.27,
        "duration_days": 7,
        "reward_description": "Lock UGX 55,000 for 7 days. Total return: UGX 92,000.",
        "features": {
            "daily_profit": 0,
            "total_profit": 37000,
            "total_returns": 92000,
            "daily_rate": 0.0,
            "total_rate": 67.27,
            "referral_bonus": 0,
            "support_level": "7-Day",
            "machine_emoji": "",
        },
        "is_active": True,
        "is_locking_package": True,
        "locking_bonus_rate": 0.0,
        "machine_eligible": True,
        "machine_type": "locked",
        "lock_minimum_days": 7,
        "lock_maximum_days": 7,
        "lock_bonus_tiers": {},
    },
    "lock_7d_115k": {
        "name": "7-Day 115K",
        "display_name": "7-Day 115K",
        "amount": 115000,
        "bonus_percentage": 50.43,
        "duration_days": 7,
        "reward_description": "Lock UGX 115,000 for 7 days. Total return: UGX 173,000.",
        "features": {
            "daily_profit": 0,
            "total_profit": 58000,
            "total_returns": 173000,
            "daily_rate": 0.0,
            "total_rate": 50.43,
            "referral_bonus": 0,
            "support_level": "7-Day",
            "machine_emoji": "",
        },
        "is_active": True,
        "is_locking_package": True,
        "locking_bonus_rate": 0.0,
        "machine_eligible": True,
        "machine_type": "locked",
        "lock_minimum_days": 7,
        "lock_maximum_days": 7,
        "lock_bonus_tiers": {},
    },
    "lock_14d_150k": {
        "name": "14-Day 150K",
        "display_name": "14-Day 150K",
        "amount": 150000,
        "bonus_percentage": 56.00,
        "duration_days": 14,
        "reward_description": "Lock UGX 150,000 for 14 days. Total return: UGX 234,000.",
        "features": {
            "daily_profit": 0,
            "total_profit": 84000,
            "total_returns": 234000,
            "daily_rate": 0.0,
            "total_rate": 56.0,
            "referral_bonus": 0,
            "support_level": "14-Day",
            "machine_emoji": "",
        },
        "is_active": True,
        "is_locking_package": True,
        "locking_bonus_rate": 0.0,
        "machine_eligible": True,
        "machine_type": "locked",
        "lock_minimum_days": 14,
        "lock_maximum_days": 14,
        "lock_bonus_tiers": {},
    },
}

# ============================================================
# PACKAGE MAP — slug → display name
# ============================================================
PACKAGE_MAP = {
    "daily_20k":     "Daily 20K",
    "daily_50k":     "Daily 50K",
    "daily_100k":    "Daily 100K",
    "daily_200k":    "Daily 200K",
    "lock_1d_30k":   "1-Day 30K",
    "lock_3d_50k":   "3-Day 50K",
    "lock_3d_100k":  "3-Day 100K",
    "lock_7d_55k":   "7-Day 55K",
    "lock_7d_115k":  "7-Day 115K",
    "lock_14d_150k": "14-Day 150K",
}

ALLOWED_AMOUNTS = set(catalog["amount"] for catalog in PACKAGE_CATALOG.values())


# ============================================================
# SEED FUNCTIONS
# ============================================================

def clear_all_package_data():
    """Clear all package-related data in proper order"""
    with app.app_context():
        try:
            logger.info("🗑️  Clearing all package data...")
            
            # Step 1: Delete payments
            payment_count = db.session.query(Payment).count()
            if payment_count > 0:
                db.session.query(Payment).delete()
                logger.info(f"   ✅ Deleted {payment_count} payments")
            
            # Step 2: Delete user packages
            package_count = db.session.query(Package).count()
            if package_count > 0:
                db.session.query(Package).delete()
                logger.info(f"   ✅ Deleted {package_count} user packages")
            
            # Step 3: Delete catalog
            catalog_count = db.session.query(PackageCatalog).count()
            if catalog_count > 0:
                db.session.query(PackageCatalog).delete()
                logger.info(f"   ✅ Deleted {catalog_count} catalog entries")
            
            db.session.commit()
            
            # Reset sequences
            try:
                db.session.execute("ALTER SEQUENCE packagecatalog_id_seq RESTART WITH 1")
                db.session.execute("ALTER SEQUENCE packages_id_seq RESTART WITH 1")
                db.session.execute("ALTER SEQUENCE payments_id_seq RESTART WITH 1")
                db.session.commit()
                logger.info("   ✅ Sequences reset")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not reset sequences: {e}")
            
            logger.info("✅ All package data cleared successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error clearing data: {e}")
            db.session.rollback()
            return False


def seed_package_catalog(force=False):
    """
    Seed the PackageCatalog table with all package definitions
    
    Args:
        force (bool): If True, clear existing data before seeding
    """
    with app.app_context():
        try:
            logger.info("=" * 70)
            logger.info("📦 SEEDING PACKAGE CATALOG")
            logger.info("=" * 70)
            
            # Check existing entries
            existing_count = PackageCatalog.query.count()
            
            if existing_count > 0 and not force:
                logger.info(f"📦 Found {existing_count} existing catalog entries")
                response = input("⚠️  Do you want to clear existing catalog and re-seed? (y/n): ")
                if response.lower() == 'y':
                    if not clear_all_package_data():
                        return False
                else:
                    logger.info("ℹ️  Keeping existing catalog. Updating only...")
            elif force and existing_count > 0:
                logger.info("🗑️  Force mode: Clearing existing data...")
                if not clear_all_package_data():
                    return False
            
            # Seed/update packages
            seeded_count = 0
            updated_count = 0
            
            for package_key, details in PACKAGE_CATALOG.items():
                existing = PackageCatalog.query.filter_by(name=details['name']).first()
                
                if existing:
                    # Update existing package
                    existing.display_name = details.get('display_name')
                    existing.amount = details['amount']
                    existing.bonus_percentage = details['bonus_percentage']
                    existing.duration_days = details['duration_days']
                    existing.reward_description = details['reward_description']
                    existing.features = details['features']
                    existing.is_active = details['is_active']
                    
                    # Locking fields
                    existing.is_locking_package = details.get('is_locking_package', False)
                    existing.locking_bonus_rate = details.get('locking_bonus_rate', 0)
                    existing.locking_duration_days = details.get('locking_duration_days', None)
                    existing.machine_eligible = details.get('machine_eligible', False)
                    existing.machine_type = details.get('machine_type', 'standard')
                    existing.daily_return_rate = details.get('daily_return_rate', 0)
                    existing.total_return_rate = details.get('total_return_rate', 0)
                    existing.lock_minimum_days = details.get('lock_minimum_days', 7)
                    existing.lock_maximum_days = details.get('lock_maximum_days', 56)
                    existing.lock_bonus_tiers = details.get('lock_bonus_tiers', {})
                    
                    existing.updated_at = datetime.utcnow()
                    updated_count += 1
                    logger.info(f"🔄 Updated: {details['display_name']} (UGX {details['amount']:,})")
                else:
                    # Create new package
                    new_package = PackageCatalog(
                        name=details['name'],
                       # display_name=details.get('display_name'),
                        amount=details['amount'],
                        bonus_percentage=details['bonus_percentage'],
                        duration_days=details['duration_days'],
                        reward_description=details['reward_description'],
                        features=details['features'],
                        is_active=details['is_active'],
                        
                        # Locking fields
                        is_locking_package=details.get('is_locking_package', False),
                        locking_bonus_rate=details.get('locking_bonus_rate', 0),
                        locking_duration_days=details.get('locking_duration_days', None),
                        machine_eligible=details.get('machine_eligible', False),
                        machine_type=details.get('machine_type', 'standard'),
                        daily_return_rate=details.get('daily_return_rate', 0),
                        total_return_rate=details.get('total_return_rate', 0),
                        lock_minimum_days=details.get('lock_minimum_days', 7),
                        lock_maximum_days=details.get('lock_maximum_days', 56),
                        lock_bonus_tiers=details.get('lock_bonus_tiers', {})
                    )
                    db.session.add(new_package)
                    seeded_count += 1
                    logger.info(f"✅ Created: {details['display_name']} (UGX {details['amount']:,})")
            
            db.session.commit()
            
            logger.info("=" * 70)
            logger.info(f"✅ Seeding complete: {seeded_count} created, {updated_count} updated")
            logger.info("=" * 70)
            
            # Verify
            verify_package_catalog()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Database error: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False


def verify_package_catalog():
    """Verify all packages were seeded correctly"""
    with app.app_context():
        packages = PackageCatalog.query.order_by(PackageCatalog.amount.asc()).all()
        
        print("\n" + "=" * 120)
        print("📊 PACKAGE CATALOG VERIFICATION")
        print("=" * 120)
        
        print(f"{'Name':<20} {'Amount':>15} {'Days':>8} {'Daily %':>10} {'Locking':>10} {'Machine':>10} {'Tiers':>12} {'Min Lock':>10}")
        print("-" * 120)
        
        total_entries = 0
        locking_count = 0
        machine_count = 0
        
        for pkg in packages:
            tiers = pkg.lock_bonus_tiers or {}
            tier_str = f"{len(tiers)} tiers" if tiers else "None"
            total_entries += 1
            if pkg.is_locking_package:
                locking_count += 1
            if pkg.machine_eligible:
                machine_count += 1
                
            print(f"{pkg.display_name or pkg.name:<20} UGX {pkg.amount:>10,} "
                  f"{pkg.duration_days:>8} "
                  f"{float(pkg.bonus_percentage or 0):>9.1f}% "
                  f"{'✅' if pkg.is_locking_package else '❌':>10} "
                  f"{'✅' if pkg.machine_eligible else '❌':>10} "
                  f"{tier_str:>12} "
                  f"{pkg.lock_minimum_days or 0:>10}d")
        
        print("-" * 120)
        print(f"Total packages: {total_entries}")
        print(f"Locking packages: {locking_count}")
        print(f"Machine eligible: {machine_count}")
        print(f"Amount range: UGX {packages[0].amount:,} - UGX {packages[-1].amount:,}" if packages else "No packages")
        print("=" * 120)
        
        return packages


def seed_test_user():
    """Create a test user if none exists"""
    with app.app_context():
        try:
            from werkzeug.security import generate_password_hash
            import random
            import string
            
            # Check if test user exists
            user = User.query.filter_by(email='test@example.com').first()
            if user:
                logger.info(f"ℹ️  Test user already exists (ID: {user.id})")
                return user.id
            
            # Create test user
            referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            test_user = User(
                username='test_user',
                email='test@example.com',
                phone='256700000000',
                password_hash=generate_password_hash('password123'),
                referral_code=referral_code,
                is_verified=True,
                is_active=True,
                actual_balance=100000,
                available_balance=100000,
                created_at=datetime.utcnow()
            )
            
            db.session.add(test_user)
            db.session.commit()
            
            logger.info(f"✅ Test user created: test_user (ID: {test_user.id})")
            logger.info(f"   Email: test@example.com")
            logger.info(f"   Password: password123")
            logger.info(f"   Referral Code: {referral_code}")
            logger.info(f"   Balance: UGX {test_user.actual_balance:,}")
            
            return test_user.id
            
        except Exception as e:
            logger.error(f"❌ Error creating test user: {e}")
            db.session.rollback()
            return None


def create_test_investment(user_id=None):
    """Create a test investment for a user"""
    with app.app_context():
        try:
            if not user_id:
                user_id = seed_test_user()
                if not user_id:
                    return False
            
            # Get a package from catalog
            catalog = PackageCatalog.query.filter_by(name='Eagle').first()
            if not catalog:
                logger.warning("⚠️  Eagle package not found in catalog")
                return False
            
            # Check if user already has this package
            existing = Package.query.filter_by(
                user_id=user_id,
                catalog_id=catalog.id,
                status='active'
            ).first()
            
            if existing:
                logger.info(f"ℹ️  Test investment already exists for user {user_id}")
                return True
            
            # Create investment
            activated_at = datetime.utcnow()
            expires_at = activated_at + timedelta(days=catalog.duration_days)
            
            # Calculate daily bonus
            daily_bonus_rate = float(catalog.bonus_percentage or 0) / 100
            daily_amount = float(catalog.amount) * daily_bonus_rate
            
            new_investment = Package(
                user_id=user_id,
                catalog_id=catalog.id,
                package=catalog.name,
                type='investment',
                status='active',
                package_amount=catalog.amount,
                total_bonus_received=0,
                total_bonus_paid=0,
                activated_at=activated_at,
                expires_at=expires_at,
                daily_bonus_rate=daily_bonus_rate,
                last_bonus_date=activated_at,
                next_bonus_date=activated_at + timedelta(days=1),
                bonus_count=0,
                max_bonus_amount=float(catalog.amount) * 1.56,  # 156% return
                total_days_paid=0,
                is_bonus_locked=False,
                is_locked=False
            )
            
            db.session.add(new_investment)
            db.session.commit()
            
            logger.info(f"✅ Test investment created for user {user_id}")
            logger.info(f"   Package: {catalog.display_name}")
            logger.info(f"   Amount: UGX {catalog.amount:,}")
            logger.info(f"   Daily Bonus: UGX {daily_amount:,.2f}")
            logger.info(f"   Total Return: UGX {catalog.amount * 1.56:,.2f}")
            logger.info(f"   Status: active")
            logger.info(f"   Expires: {expires_at.strftime('%Y-%m-%d %H:%M')}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating test investment: {e}")
            db.session.rollback()
            return False


def get_package_summary():
    """Get a summary of packages in the system"""
    with app.app_context():
        packages = PackageCatalog.query.all()
        
        print("\n" + "=" * 70)
        print("📊 PACKAGE SUMMARY")
        print("=" * 70)
        
        if not packages:
            print("❌ No packages found in catalog")
            return
        
        print(f"Total Packages: {len(packages)}")
        print(f"Active Packages: {len([p for p in packages if p.is_active])}")
        print(f"Locking Packages: {len([p for p in packages if p.is_locking_package])}")
        print(f"Machine Eligible: {len([p for p in packages if p.machine_eligible])}")
        
        print("\n💰 Investment Range:")
        amounts = [p.amount for p in packages]
        print(f"  Min: UGX {min(amounts):,}")
        print(f"  Max: UGX {max(amounts):,}")
        
        print("\n📈 Daily Returns:")
        for pkg in sorted(packages, key=lambda p: p.amount):
            daily = pkg.features.get('daily_profit', 0) if pkg.features else 0
            print(f"  {pkg.display_name or pkg.name:<15} UGX {pkg.amount:>10,} → UGX {daily:>8,}/day ({pkg.bonus_percentage}%)")
        
        print("\n🔒 Lock Bonus Tiers:")
        for pkg in sorted(packages, key=lambda p: p.amount):
            if pkg.is_locking_package and pkg.lock_bonus_tiers:
                tiers = pkg.lock_bonus_tiers
                tier_str = ', '.join([f"{d}d: {r}%" for d, r in sorted(tiers.items())])
                print(f"  {pkg.display_name or pkg.name:<15} {tier_str}")
        
        print("=" * 70)

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    """Main execution function with command line arguments"""
    print("=" * 70)
    print("🚀 express PACKAGE SEEDER")
    print("=" * 70)
    
    # Parse command line arguments
    args = sys.argv[1:]
    
    if '--help' in args or '-h' in args:
        print("""
Usage: python seed_packages.py [OPTIONS]

Options:
    --clear         Clear all package data before seeding
    --test          Create test user and investment after seeding
    --verify        Verify existing package catalog
    --summary       Show package summary
    --force         Force re-seed without confirmation
    --help, -h      Show this help message

Examples:
    python seed_packages.py              # Normal seed with confirmation
    python seed_packages.py --clear      # Clear and re-seed
    python seed_packages.py --test       # Seed and create test data
    python seed_packages.py --force      # Force re-seed without confirmation
    python seed_packages.py --verify     # Verify existing data
    python seed_packages.py --summary    # Show package summary
        """)
        return
    
    if '--verify' in args:
        verify_package_catalog()
        return
    
    if '--summary' in args:
        get_package_summary()
        return
    
    if '--clear' in args:
        print("\n🗑️  Clearing all packages...")
        clear_all_package_data()
        print("✅ Clear complete!")
        return
    
    # Seed packages
    force = '--force' in args
    success = seed_package_catalog(force=force)
    
    if success:
        print("\n✅ Packages seeded successfully!")
        
        # Create test data if requested
        if '--test' in args:
            print("\n🔧 Seeding test data...")
            user_id = seed_test_user()
            if user_id:
                create_test_investment(user_id)
        
        # Show summary
        get_package_summary()
        
    else:
        print("\n❌ Failed to seed packages")
        sys.exit(1)

if __name__ == "__main__":
    main()