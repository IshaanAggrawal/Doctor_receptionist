import json
import psycopg2
import logging
from typing import Dict, Any

from src.database.pg_client import get_db_connection
from src.cache.cache_service import invalidate_slots_cache
from src.services.sms_service import send_booking_confirmation
from src.utils.token_gen import generate_token
from src.utils.validators import validate_phone, sanitize_input

logger = logging.getLogger(__name__)

def book_slot(clinic_id: str, slot_id: str, patient_name: str, phone_number: str, ip_address: str) -> Dict[str, Any]:
    """
    Atomic booking transaction.
    This is the core of DentaQ. It uses row-level locking (SELECT FOR UPDATE NOWAIT)
    to prevent double bookings under high concurrency.
    """
    # 1. Validate and clean input
    clean_phone = validate_phone(phone_number)
    if not clean_phone:
        return {"success": False, "error": "INVALID_PHONE", "message": "Invalid phone format."}
        
    clean_name = sanitize_input(patient_name)
    
    # 2. Enter the transaction block
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                
                # STEP A: Lock the specific slot row NOW!
                # NOWAIT means if someone else is currently booking it, it fails instantly 
                # rather than hanging and waiting.
                cur.execute("""
                    SELECT id, is_available, slot_time 
                    FROM slots 
                    WHERE id = %s 
                    FOR UPDATE NOWAIT
                """, (slot_id,))
                
                slot = cur.fetchone()
                
                if not slot:
                    return {"success": False, "error": "NOT_FOUND", "message": "Slot not found."}
                
                slot_db_id, is_available, slot_time = slot
                
                if not is_available:
                    return {"success": False, "error": "TAKEN", "message": "This slot was just taken by someone else!"}
                
                # STEP B: Mark the slot as taken
                cur.execute("""
                    UPDATE slots 
                    SET is_available = false 
                    WHERE id = %s
                """, (slot_id,))
                
                # STEP C: Generate the unique token
                booking_token = generate_token()
                
                # STEP D: Calculate the dynamic queue position
                # We find how many patients are already confirmed/arrived for today
                cur.execute("""
                    SELECT COUNT(*) + 1 as position
                    FROM appointments
                    WHERE clinic_id = %s
                      AND status IN ('confirmed', 'arrived')
                      AND slot_id IN (
                          SELECT id FROM slots WHERE slot_time::DATE = %s::DATE
                      )
                """, (clinic_id, slot_time))
                queue_position = cur.fetchone()[0]
                
                # STEP E: Insert the actual appointment
                # (The DB trigger will block this if the phone already booked today)
                cur.execute("""
                    INSERT INTO appointments 
                        (clinic_id, slot_id, patient_name, phone_number, 
                         booking_token, status, queue_position, ip_address, otp_verified_at)
                    VALUES 
                        (%s, %s, %s, %s, %s, 'confirmed', %s, %s, NOW())
                    RETURNING id
                """, (clinic_id, slot_id, clean_name, clean_phone, booking_token, queue_position, ip_address))
                
                appt_id = cur.fetchone()[0]
                
                # STEP F: Log Analytics Event
                # We store just the last 4 digits for privacy in analytics
                cur.execute("""
                    INSERT INTO analytics_events (clinic_id, event_type, metadata)
                    VALUES (%s, 'booking', %s)
                """, (clinic_id, json.dumps({
                    "phone_last4": clean_phone[-4:],
                    "via": "qr_web",
                    "slot_id": slot_id
                })))
                
        # --- TRANSACTION ENDS HERE --- 
        # (If we reach here without errors, get_db_connection() automatically runs conn.commit())
        
        # 3. Post-Transaction Actions (Network calls)
        # We do this OUTSIDE the transaction so we don't hold the DB lock while waiting for Redis or Twilio
        
        # Format time for SMS (e.g. '03:00 PM')
        formatted_time = slot_time.strftime("%I:%M %p") 
        
        # Send the confirmation text
        send_booking_confirmation(clean_phone, booking_token, formatted_time)
        
        # Invalidate the cache for this clinic so the slot instantly disappears for others
        invalidate_slots_cache(clinic_id, slot_time.strftime("%Y-%m-%d"))
        
        return {
            "success": True, 
            "appointment_id": appt_id,
            "booking_token": booking_token,
            "queue_position": queue_position,
            "slot_time": formatted_time
        }
        
    except psycopg2.errors.LockNotAvailable:
        # Caught the NOWAIT error!
        logger.warning(f"Race condition blocked: Slot {slot_id} was locked by another user.")
        return {"success": False, "error": "RACE_CONDITION", "message": "Someone else is booking this slot right now. Please select another."}
        
    except psycopg2.errors.UniqueViolation as e:
        # Caught the "One booking per phone per day" constraint!
        if "DUPLICATE_BOOKING" in str(e) or "appointments_phone_number" in str(e):
            return {"success": False, "error": "DUPLICATE", "message": "You already have a booking for today."}
        return {"success": False, "error": "DB_CONSTRAINT", "message": "A database constraint was violated."}
        
    except Exception as e:
        logger.error(f"Unexpected error during booking: {e}")
        return {"success": False, "error": "SYSTEM_ERROR", "message": "An unexpected error occurred. Please try again."}
