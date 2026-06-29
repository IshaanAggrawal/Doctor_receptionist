import random
import logging
from src.cache.cache_service import redis_client
from src.services.sms_service import send_otp

logger = logging.getLogger(__name__)

def generate_and_send_otp(phone: str) -> bool:
    """
    Generates a 6-digit OTP, saves it to Redis with a 5-minute TTL, 
    and sends it via SMS.
    """
    if not redis_client:
        logger.warning("Redis is down. OTP functionality disabled.")
        return False
        
    # Generate 6 digit code
    otp_code = str(random.randint(100000, 999999))
    
    try:
        # Save to Redis with 300 seconds (5 minutes) expiry
        redis_client.setex(f"otp:{phone}", 300, otp_code)
        
        # Send it using Twilio
        success = send_otp(phone, otp_code)
        if not success:
            logger.error(f"Failed to send OTP SMS to {phone}")
            
        return success
    except Exception as e:
        logger.error(f"Error in OTP generation: {e}")
        return False


def verify_otp(phone: str, entered_code: str) -> dict:
    """
    Verifies the OTP against Redis. Handles rate limiting for wrong attempts.
    """
    if not redis_client:
        return {"success": False, "message": "Verification system offline."}
        
    # 1. Check if they are blocked from trying
    if redis_client.exists(f"otp_blocked:{phone}"):
        return {"success": False, "message": "Too many failed attempts. Try again in 1 hour."}
        
    try:
        # 2. Get the stored OTP
        stored_code = redis_client.get(f"otp:{phone}")
        
        if not stored_code:
            return {"success": False, "message": "OTP expired or not found. Please request a new one."}
            
        # 3. Check if it matches
        if stored_code == entered_code:
            # Success! Delete it so it can't be used twice
            redis_client.delete(f"otp:{phone}")
            redis_client.delete(f"otp_attempts:{phone}")
            return {"success": True, "message": "OTP verified!"}
            
        # 4. Wrong code handling (Rate Limiting)
        attempts_key = f"otp_attempts:{phone}"
        attempts = redis_client.incr(attempts_key)
        
        # Set the expiry of the attempts counter to 1 hour
        if attempts == 1:
            redis_client.expire(attempts_key, 3600)
            
        # If they fail 3 times, block them for 1 hour
        if int(attempts) >= 3:
            redis_client.setex(f"otp_blocked:{phone}", 3600, "1")
            return {"success": False, "message": "Too many failed attempts. Try again in 1 hour."}
            
        return {"success": False, "message": f"Incorrect code. {3 - int(attempts)} attempts remaining."}
        
    except Exception as e:
        logger.error(f"Error verifying OTP: {e}")
        return {"success": False, "message": "System error during verification."}
