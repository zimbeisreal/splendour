# services/sms_sender.py
"""
SMS sender via Africa's Talking using curl.exe subprocess.
Reliable workaround for Python 3.14 + Windows SSL/TLS issues.
"""
import subprocess
import urllib.parse
import json
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Set up logger for this module
logger = logging.getLogger(__name__)

def send_sms(phone: str, message: str, 
             api_key: str = None, 
             username: str = None,
             sandbox: bool = None) -> bool:
    """
    Send SMS via Africa's Talking API using curl.exe.
    
    Args:
        phone: Recipient phone in E.164 format (+256...)
        message: SMS text content
        api_key: Africa's Talking API key (defaults to app config)
        username: AT username (defaults to app config)
        sandbox: Force sandbox mode (defaults to 'sandbox' in username)
    
    Returns:
        bool: True if SMS queued successfully, False otherwise
    """
    logger.info("=" * 60)
    logger.info("SEND_SMS FUNCTION CALLED")
    logger.info(f"STEP 1: Phone: {phone}")
    logger.info(f"STEP 2: Message: {message}")
    logger.info("=" * 60)
    
    try:
        # Resolve configuration
        logger.info("STEP 3: Loading configuration...")
     
        api_key = os.environ.get('AFRICASTALKING_API_KEY')                                     #api_key or app.config.get('AFRICASTALKING_API_KEY')
        username = os.environ.get('AFRICASTALKING_USERNAME')                              #username or app.config.get('AFRICASTALKING_USERNAME', 'sandbox')
        print(api_key)
        print(username)
        
        logger.info(f"STEP 4: Username: {username}")
        logger.info(f"STEP 5: API Key present: {'Yes' if api_key else 'No'}")
        
        if not api_key:
            logger.error("STEP 6: No API key found!")
            return False
        
        # Determine endpoint
        if sandbox is True or 'sandbox' in username.lower():
            base_url = 'https://api.sandbox.africastalking.com/version1/messaging'
            logger.info("STEP 7: Using SANDBOX endpoint")
        else:
            base_url = 'https://api.africastalking.com/version1/messaging'
            logger.info("STEP 7: Using PRODUCTION endpoint")
        
        logger.info(f"STEP 8: Base URL: {base_url}")
        
        # Form-encoded payload (Africa's Talking requirement - NOT JSON)
        logger.info("STEP 9: Creating form-encoded payload...")
        form_data = urllib.parse.urlencode({
            'username': username,
            'to': phone,
            'message': message
        }, quote_via=urllib.parse.quote)  # Proper URL encoding for +256...
        
        logger.info(f"STEP 10: Form data: {form_data[:100]}...")  # Log first 100 chars only
        
        # Build curl command
        logger.info("STEP 11: Building curl command...")
        import platform
        curl_binary = 'curl.exe' if platform.system() == 'Windows' else 'curl'
        try:
            subprocess.run([curl_binary, '--version'], 
                          capture_output=True, check=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            if curl_binary == 'curl.exe':
                curl_binary = 'curl'
        logger.info(f"Using curl binary: {curl_binary}")
        # 🔧 END CROSS-PLATFORM FIX
        cmd = [
            curl_binary,
            '-s',                      # Silent mode
            '-w', '\n%{http_code}',    # Append HTTP status code on new line
            '-X', 'POST',
            base_url,
            '-H', f'ApiKey: {api_key}',  # Log only first 10 chars of API key
            '-H', 'Accept: application/json',
            '-d', form_data,           # Form-encoded body
            '--noproxy', '*',          # Bypass all proxies (hotspot fix)
            '--connect-timeout', '10', # Connection timeout
            '--max-time', '15'         # Total request timeout
        ]
        
        # Log the actual command (without exposing full API key)
        safe_cmd = cmd.copy()
        for i, arg in enumerate(safe_cmd):
            if arg.startswith('ApiKey:'):
                safe_cmd[i] = 'ApiKey: ***HIDDEN***'
        logger.info(f"STEP 12: Curl command: {' '.join(safe_cmd)}")
        
        logger.info("STEP 13: Executing curl subprocess...")
        # Execute curl.exe
        result = subprocess.run(
            cmd,
            capture_output=True,    # Capture stdout/stderr
            text=True,              # Return strings, not bytes
            timeout=20,             # Python-side timeout safety
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        
        logger.info(f"STEP 14: Subprocess completed")
        logger.info(f"STEP 14a: Return code: {result.returncode}")
        logger.info(f"STEP 14b: STDOUT length: {len(result.stdout)} chars")
        logger.info(f"STEP 14c: STDERR: {result.stderr[:200] if result.stderr else 'None'}")
        
        # Parse response: body + status code on last line
        output = result.stdout.strip()
        lines = output.split('\n')
        logger.info(f"STEP 15: Response lines: {len(lines)}")
        
        # Extract HTTP status code
        status_code = None
        if lines and lines[-1].isdigit():
            status_code = int(lines[-1])
            response_body = '\n'.join(lines[:-1])
            logger.info(f"STEP 16: HTTP Status Code: {status_code}")
        else:
            response_body = output
            logger.warning(f"STEP 16: No status code found in response")
        
        logger.info(f"STEP 17: Response body: {response_body[:500]}")
        
        # Africa's Talking returns 201 for successful SMS queue
        if status_code == 201:
            logger.info("STEP 18: ✅ SMS API returned 201 (success)")
            # Optional: parse response for messageId, cost, etc.
            try:
                response_data = json.loads(response_body)
                recipients = response_data.get('SMSMessageData', {}).get('Recipients', [])
                if recipients:
                    recipient = recipients[0]
                    logger.info(f"STEP 19: ✅ SMS queued: messageId={recipient.get('messageId')}, cost={recipient.get('cost')}, status={recipient.get('status')}")
                else:
                    logger.info("STEP 19: No recipient details in response")
            except json.JSONDecodeError as je:
                logger.warning(f"STEP 19: Could not parse JSON response: {je}")
            except Exception as e:
                logger.warning(f"STEP 19: Error parsing response: {e}")
            
            logger.info("=" * 60)
            logger.info("✅ SMS SENT SUCCESSFULLY")
            logger.info("=" * 60)
            return True
        else:
            logger.warning(f"STEP 18: ⚠️ SMS API returned {status_code}")
            logger.warning(f"STEP 18a: Response body: {response_body[:200]}")
            
            # Try to parse error message
            try:
                error_data = json.loads(response_body)
                error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                logger.warning(f"STEP 18b: API Error message: {error_msg}")
            except:
                pass
            
            logger.info("=" * 60)
            logger.info("❌ SMS SENDING FAILED")
            logger.info("=" * 60)
            return False
            
    except subprocess.TimeoutExpired as te:
        logger.error(f"❌ STEP ERROR: SMS curl timed out after 20 seconds for {phone}")
        logger.error(f"Timeout details: {te}")
        logger.info("=" * 60)
        return False
    except FileNotFoundError as fnfe:
        logger.error("❌ STEP ERROR: curl.exe not found in PATH. Ensure curl is installed.")
        logger.error(f"FileNotFound details: {fnfe}")
        logger.info("=" * 60)
        return False
    except Exception as e:
        logger.exception(f"❌ STEP ERROR: SMS curl subprocess error for {phone}: {e}")
        logger.info("=" * 60)
        return False


def generate_response_code(job_id: int, seeker_id: int) -> str:
    """
    Generate short, unique, SMS-friendly response code.
    Format: J{job:03d}U{seeker:03d} → "J042U123"
    """
    logger.debug(f"Generating response code for job_id={job_id}, seeker_id={seeker_id}")
    code = f"J{job_id:03d}U{seeker_id:03d}"
    logger.debug(f"Generated code: {code}")
    return code


def parse_sms_response(sms_text: str) -> dict:
    """
    Parse inbound SMS reply to extract response code and action.
    
    Expected formats:
    - "YES-J042U123"
    - "NO-J042U123" 
    - "YES J042U123"
    - "j042u123" (code only)
    
    Returns:
        dict with 'action' (yes/no/unknown), 'code', 'valid' (bool)
    """
    import re
    
    logger.debug(f"Parsing SMS response: '{sms_text}'")
    
    text = sms_text.strip().upper()
    
    # Pattern: optional YES/NO + separator + code
    pattern = r'^(YES|NO)?[\s\-]*([A-Z]\d{3}[A-Z]\d{3})$'
    match = re.match(pattern, text)
    
    if match:
        action, code = match.groups()
        result = {
            'action': action.lower() if action else 'unknown',
            'code': code,
            'valid': True
        }
        logger.debug(f"Pattern matched: {result}")
        return result
    
    # Fallback: just look for code pattern anywhere
    code_pattern = r'([A-Z]\d{3}[A-Z]\d{3})'
    code_match = re.search(code_pattern, text)
    
    if code_match:
        result = {
            'action': 'unknown',  # Can't determine yes/no
            'code': code_match.group(1),
            'valid': True
        }
        logger.debug(f"Fallback match (code only): {result}")
        return result
    
    # No valid code found
    result = {
        'action': None,
        'code': None,
        'valid': False
    }
    logger.warning(f"No valid code found in SMS: '{sms_text}'")
    return result