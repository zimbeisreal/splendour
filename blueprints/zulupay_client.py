# ============================================================
# ZULUPAY CLIENT - blueprints/zulupay_client.py
# ============================================================

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict
from decimal import Decimal
from models import db, Payment, PaymentStatus
from flask import current_app

logger = logging.getLogger(__name__)

# ============================================================
# ZULUPAY CONFIGURATION
# ============================================================

ZULUPAY_ENVIRONMENT = os.getenv('ZULUPAY_ENVIRONMENT', 'sandbox')
ZULUPAY_PUBLIC_KEY = os.getenv('ZULUPAY_PUBLIC_KEY')
ZULUPAY_SECRET_KEY = os.getenv('ZULUPAY_SECRET_KEY')
ZULUPAY_AUTH_PIN = os.getenv('ZULUPAY_AUTH_PIN')  # For withdrawals
ZULUPAY_BASE_URL = os.getenv('ZULUPAY_BASE_URL', 'https://zulupay.org')

if not ZULUPAY_PUBLIC_KEY:
    logger.warning("ZULUPAY_PUBLIC_KEY not set in environment variables")

# ============================================================
# ZULUPAY CLIENT (Singleton Pattern)
# ============================================================

class _ZuluPayClient:
    """Internal ZuluPay API Client - Singleton Pattern"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.public_key = ZULUPAY_PUBLIC_KEY
        self.secret_key = ZULUPAY_SECRET_KEY
        self.auth_pin = ZULUPAY_AUTH_PIN
        self.base_url = ZULUPAY_BASE_URL
        self.token = None
        self.token_expiry = None
        
        logger.info(f"ZuluPay Client initialized for {ZULUPAY_ENVIRONMENT}")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Public Key: {self.public_key[:10]}...{self.public_key[-5:] if self.public_key else 'NOT SET'}")
    
    def get_access_token(self) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Get/refresh ZuluPay access token.
        Call /register to get token - reuse until expired.
        """
        # Return cached token if still valid (24 hour expiry)
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token, None
        
        if not self.public_key:
            return None, {"error": "ZuluPay Public Key not configured"}
        
        url = f"{self.base_url}/api/register"
        headers = {
            "Authorization": self.public_key,
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"Getting ZuluPay access token from {url}")
            response = requests.post(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"ZuluPay token response: {data}")
            
            if data.get('status') == 'succesful' or data.get('token'):
                self.token = data.get('token')
                # Set expiry (assuming 24 hours if not provided)
                self.token_expiry = datetime.now() + timedelta(hours=24)
                logger.info("Successfully obtained ZuluPay access token")
                return self.token, None
            else:
                logger.error(f"Failed to get ZuluPay token: {data}")
                return None, {"error": "Authentication failed", "details": data}
                
        except requests.exceptions.HTTPError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(f"ZuluPay HTTP error: {error_detail}")
            return None, {"error": f"HTTP {e.response.status_code if e.response else 'Unknown'}", "details": error_detail}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"ZuluPay connection error: {str(e)}")
            return None, {"error": "Connection failed", "details": str(e)}
        except Exception as e:
            logger.error(f"ZuluPay token request failed: {str(e)}")
            return None, {"error": "Token request failed", "details": str(e)}
    
    def make_request(self, endpoint: str, data: Dict = None, requires_auth: bool = True, requires_pin: bool = False) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Generic ZuluPay API request handler
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if requires_auth:
            token, error = self.get_access_token()
            if error:
                return None, error
            headers["Authorization"] = f"Bearer {token}"
            headers["secret_key"] = self.secret_key
        
        # For withdrawal, add password header
        if requires_pin:
            if not self.auth_pin:
                return None, {"error": "Authorization PIN not configured"}
            headers["password"] = self.auth_pin
        
        try:
            logger.info(f"Making ZuluPay request to {endpoint}")
            logger.debug(f"Request data: {data}")
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            # Log response status
            logger.info(f"ZuluPay response status: {response.status_code}")
            
            # Try to parse JSON response
            try:
                result = response.json()
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response: {response.text}")
                return None, {"error": "Invalid response format", "details": response.text}
            
            # Check for HTTP errors
            if response.status_code >= 400:
                logger.error(f"ZuluPay HTTP error: {response.status_code} - {result}")
                return None, {"error": f"HTTP {response.status_code}", "details": result}
            
            logger.info(f"ZuluPay {endpoint} request successful")
            return result, None
            
        except requests.exceptions.Timeout:
            logger.error("ZuluPay request timeout")
            return None, {"error": "Request timeout"}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"ZuluPay connection error: {str(e)}")
            return None, {"error": "Connection failed", "details": str(e)}
        except Exception as e:
            logger.error(f"ZuluPay request failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, {"error": "Request failed", "details": str(e)}
    
    def collect_money(self, amount: int, phone: str, trans_id: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Collect money from customer (Deposit)
        """
        data = {
            "amount": int(amount),
            "phone": phone,
            "trans_id": trans_id
        }
        return self.make_request("api/deposit", data, requires_auth=True, requires_pin=False)
    
    def disburse_money(self, amount: int, phone: str, trans_id: str, reason: str = "Withdrawal") -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Send money to customer (Withdrawal)
        """
        data = {
            "amount": int(amount),
            "phone": phone,
            "trans_id": trans_id,
            "reason": reason
        }
        return self.make_request("api/withdraw", data, requires_auth=True, requires_pin=True)
    
    def get_transaction_status(self, trans_id: str, type: str = 'deposit') -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Check transaction status
        """
        data = {
            "type": type,  # 'deposit' or 'withdraw'
            "trans_id": trans_id
        }
        return self.make_request("api/transaction", data, requires_auth=True, requires_pin=False)
    
    def get_balance(self) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Get wallet balance
        """
        return self.make_request("api/balance", None, requires_auth=True, requires_pin=False)

# Initialize ZuluPay client (singleton)
_zulupay_client = _ZuluPayClient()

# ============================================================
# ZULUPAY PAYMENT FUNCTIONS
# ============================================================

def initiate_zulupay_payment(user, amount, phone, package=None, payment_type='package'):
    """
    Initiate a ZuluPay payment (Mobile Money deposit)
    """
    try:
        # 1. Create payment record (reuse existing function)
        from blueprints.payments_helpers import create_payment_record
        
        payment = create_payment_record(user, amount, phone, payment_type, package)
        if not payment:
            return None, {"error": "Failed to create payment record"}
        
        # 2. Generate unique transaction ID
        trans_id = payment.reference[:20]  # Use first 20 chars of UUID
        
        # 3. Call ZuluPay API to collect money
        response, error = _zulupay_client.collect_money(
            amount=int(amount),
            phone=phone,
            trans_id=trans_id
        )
        
        if error:
            payment.status = PaymentStatus.FAILED.value
            payment.raw_response = json.dumps({"error": error})
            db.session.commit()
            return None, error
        
        # 4. Update payment record
        payment.external_ref = trans_id
        payment.provider = 'zulupay'
        payment.method = 'ZuluPay'
        payment.raw_response = json.dumps(response)
        payment.status = PaymentStatus.PENDING.value
        db.session.commit()
        
        logger.info(f"ZuluPay payment initiated: {trans_id} for user {user.id}")
        
        # 5. Return success response
        return {
            "payment_id": payment.id,
            "reference": payment.reference,
            "trans_id": trans_id,
            "status": payment.status,
            "provider": "zulupay",
            "message": "Payment initiated successfully",
            "raw_response": response
        }, None
        
    except Exception as e:
        logger.error(f"ZuluPay payment initiation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, {"error": f"Payment initiation failed: {str(e)}"}

def handle_zulupay_webhook(data: Dict) -> Tuple[Dict, int]:
    """
    Handle incoming ZuluPay webhook notification
    """
    try:
        # ZuluPay webhook format:
        # {
        #   "status": "SUCCESSFUL" | "FAILED" | "PENDING",
        #   "type": "DEPOSIT" | "WITHDRAW",
        #   "trans_id": "HKJKS99877",
        #   "amount": 5000,
        #   "phone": "0781234567"
        # }
        
        logger.info(f"Processing ZuluPay webhook: {data}")
        
        webhook_status = data.get('status', '').upper()
        webhook_type = data.get('type', '').upper()
        trans_id = data.get('trans_id')
        
        if not trans_id:
            logger.error("Webhook missing trans_id")
            return {"error": "Missing trans_id"}, 400
        
        # Find payment by external_ref (trans_id)
        payment = Payment.query.filter_by(external_ref=trans_id).first()
        
        if not payment:
            logger.warning(f"Payment not found for trans_id: {trans_id}")
            return {"error": "Payment not found"}, 404
        
        # Update payment based on webhook status
        if webhook_status == 'SUCCESSFUL':
            payment.status = PaymentStatus.COMPLETED.value
            payment.verified = True
            
            # Activate package if this was a package payment
            if payment.package_catalog_id:
                from blueprints.payments_helpers import activate_user_package
                activate_user_package(payment.user_id, payment.package_catalog_id)
                
        elif webhook_status == 'FAILED':
            payment.status = PaymentStatus.FAILED.value
        else:  # PENDING
            payment.status = PaymentStatus.PENDING.value
        
        payment.raw_response = json.dumps(data)
        db.session.commit()
        
        logger.info(f"Webhook processed successfully for trans_id: {trans_id} - Status: {webhook_status}")
        
        # Return acknowledgment (ZuluPay expects 200 OK)
        return {"status": "success", "message": "Webhook processed"}, 200
        
    except Exception as e:
        logger.error(f"Webhook handling failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500

def check_zulupay_transaction_status(trans_id: str, transaction_type: str = 'deposit') -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Manual status check for ZuluPay transaction
    """
    return _zulupay_client.get_transaction_status(trans_id, transaction_type)

def get_zulupay_balance() -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Get ZuluPay wallet balance
    """
    return _zulupay_client.get_balance()