import os
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

# Fetch Twilio credentials from environment variables
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.environ.get("TWILIO_PHONE")

# Initialize Twilio Client
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}")
        twilio_client = None
else:
    logger.warning("Twilio credentials missing. SMS notifications will be disabled.")
    twilio_client = None


def send_sms(to_phone: str, message: str) -> bool:
    """
    Base function to send an SMS.
    Returns True if successful, False otherwise.
    """
    if not twilio_client or not TWILIO_PHONE:
        logger.warning(f"SMS Mock: Would have sent to {to_phone}: {message}")
        return False
        
    try:
        message = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=to_phone
        )
        logger.info(f"SMS sent successfully to {to_phone}. SID: {message.sid}")
        return True
    except TwilioRestException as e:
        logger.error(f"Twilio API Error sending SMS to {to_phone}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending SMS to {to_phone}: {e}")
        return False

# ── NOTIFICATION TEMPLATES ───────────────────────────────────────────────────

def send_otp(phone: str, otp_code: str) -> bool:
    """Send the 6-digit OTP for booking verification."""
    msg = f"Your DentaQ verification code is: {otp_code}. It expires in 5 minutes."
    return send_sms(phone, msg)

def send_booking_confirmation(phone: str, token: str, slot_time: str) -> bool:
    """Send confirmation immediately after successful booking."""
    msg = f"Booking Confirmed! Your slot is at {slot_time}. Your booking token is: {token}. Please show this at the reception."
    return send_sms(phone, msg)

# ── 3-TIER QUEUE NOTIFICATIONS ───────────────────────────────────────────────

def send_tier1_notification(phone: str, wait_mins: int) -> bool:
    """Tier 1: Triggered when there are 5 patients ahead."""
    msg = f"Your turn is approaching. There are 5 patients ahead of you. Estimated wait time: {wait_mins} mins."
    return send_sms(phone, msg)

def send_tier2_notification(phone: str) -> bool:
    """Tier 2: Triggered when there are 2 patients ahead."""
    msg = f"You are almost up! There are 2 patients ahead of you. Please head to the waiting area if you haven't already."
    return send_sms(phone, msg)

def send_tier3_notification(phone: str, token: str) -> bool:
    """Tier 3: Triggered when doctor clicks 'Call Next'."""
    msg = f"The doctor is ready for you now. Please come in. Token: {token}"
    return send_sms(phone, msg)
