# security_config.py
from decimal import Decimal
from datetime import timedelta

class BonusSecurityConfig:
    """Production security configuration for bonus engine"""
    
    # Financial Limits
    MAX_BONUS_AMOUNT = Decimal('10000000')  # 10M UGX
    MIN_BONUS_AMOUNT = Decimal('1')         # 1 UGX
    DAILY_BONUS_LIMIT_PER_USER = Decimal('5000000')  # 5M UGX
    HOURLY_BONUS_LIMIT_PER_USER = Decimal('1000000') # 1M UGX
    
    # System Limits
    MAX_LEVEL = 20
    MAX_ANCESTORS_PER_CALCULATION = 20
    MAX_BONUS_BATCH_SIZE = 100
    MAX_RETRY_ATTEMPTS = 5
    MAX_CONCURRENT_PROCESSING = 10
    
    # Timing & Rate Limiting
    BONUS_CALCULATION_TIMEOUT = timedelta(minutes=5)
    PAYOUT_PROCESSING_TIMEOUT = timedelta(minutes=10)
    RATE_LIMIT_REQUESTS_PER_MINUTE = 100
    RATE_LIMIT_BONUS_CALCS_PER_HOUR = 1000
    
    # Fraud Detection Thresholds
    SUSPICIOUS_BONUS_THRESHOLD = Decimal('1000000')  # 1M UGX
    RAPID_REFERRAL_THRESHOLD = 10  # Referrals per hour
    SAME_DEVICE_THRESHOLD = 3      # Accounts per device
    SAME_IP_THRESHOLD = 5          # Accounts per IP
    
    # Security Keys (Should be in environment variables)
    WEBHOOK_SECRET_KEY = "bonus_webhook_secret_2024"
    IDEMPOTENCY_KEY_TTL = timedelta(hours=24)
    
    # Audit & Compliance
    AUDIT_RETENTION_DAYS = 1095  # 3 years
    DATA_BACKUP_INTERVAL_HOURS = 24