import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class PesapalClient:
    """Pesapal API v3 Client"""
    
    def __init__(self):
        self.consumer_key = os.getenv('PESAPAL_CONSUMER_KEY')
        self.consumer_secret = os.getenv('PESAPAL_CONSUMER_SECRET')
        self.environment = os.getenv('PESAPAL_ENVIRONMENT', 'sandbox')  # 'sandbox' or 'production'
        self.token = None
        self.token_expiry = None
        
        # API Endpoints
        if self.environment == 'production':
            self.base_url = 'https://pay.pesapal.com/v3'
        else:
            self.base_url = 'https://cybqa.pesapal.com/pesapalv3'
            
        logger.info(f"Pesapal Client initialized for {self.environment}")
    
    def get_access_token(self) -> Tuple[Optional[str], Optional[Dict]]:
        """Obtain OAuth 2.0 access token"""
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token, None
            
        url = f"{self.base_url}/api/Auth/RequestToken"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "consumer_key": self.consumer_key,
            "consumer_secret": self.consumer_secret
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == '200':
                self.token = data.get('token')
                expiry = data.get('expiryDate')
                if expiry:
                    # Parse expiry and set 5 minutes early for safety
                    expiry_dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                    self.token_expiry = expiry_dt - timedelta(minutes=5)
                else:
                    self.token_expiry = datetime.now() + timedelta(minutes=5)
                    
                logger.info("Successfully obtained Pesapal access token")
                return self.token, None
            else:
                logger.error(f"Failed to get token: {data}")
                return None, {"error": "Authentication failed", "details": data}
                
        except Exception as e:
            logger.error(f"Token request failed: {str(e)}")
            return None, {"error": "Token request failed", "details": str(e)}
    
    def submit_order(self, order_data: Dict) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Submit order to Pesapal"""
        token, error = self.get_access_token()
        if error:
            return None, error
            
        url = f"{self.base_url}/api/Transactions/SubmitOrderRequest"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=order_data, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == '200':
                logger.info(f"Order submitted successfully: {data.get('order_tracking_id')}")
                return data, None
            else:
                logger.error(f"Order submission failed: {data}")
                return None, {"error": "Order submission failed", "details": data}
                
        except Exception as e:
            logger.error(f"Order submission error: {str(e)}")
            return None, {"error": "Order submission failed", "details": str(e)}
    
    def get_transaction_status(self, order_tracking_id: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Query transaction status"""
        token, error = self.get_access_token()
        if error:
            return None, error
            
        url = f"{self.base_url}/api/Transactions/GetTransactionStatus"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "orderTrackingId": order_tracking_id
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Transaction status retrieved: {data.get('status')}")
            return data, None
            
        except Exception as e:
            logger.error(f"Status query failed: {str(e)}")
            return None, {"error": "Status query failed", "details": str(e)}