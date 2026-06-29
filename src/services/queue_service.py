import json
import logging
from typing import List, Dict, Any

from src.database.pg_client import get_db_connection
from src.cache.cache_service import redis_client
from src.services.sms_service import send_tier1_notification, send_tier2_notification, send_tier3_notification

logger = logging.getLogger(__name__)

def get_live_queue(clinic_id: str, date_str: str) -> List[Dict[str, Any]]:
    """
    Fetches the live queue for a specific clinic and date.
    It relies on Supabase Realtime to push updates, but we use this 
    for initial load and fast caching.
    """
    # In a full implementation, this would read from the DB directly if cache misses.
    # For boilerplate, we'll assume it hits the DB and formats it.
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.patient_name, a.status, a.queue_position, s.slot_time
                FROM appointments a
                JOIN slots s ON s.id = a.slot_id
                WHERE a.clinic_id = %s
                  AND s.slot_time::DATE = %s::DATE
                  AND a.status IN ('confirmed', 'arrived', 'in_consultation')
                ORDER BY a.queue_position ASC
            """, (clinic_id, date_str))
            
            columns = [desc[0] for desc in cur.description]
            results = [dict(zip(columns, row)) for row in cur.fetchall()]
            
            return results


def call_next_patient(clinic_id: str) -> Dict[str, Any]:
    """
    Doctor clicks 'Call Next'. Atomically:
    1. Finds the next 'arrived' patient using SKIP LOCKED
    2. Marks them 'in_consultation'
    3. Triggers the Tier 3 SMS (It's your turn)
    4. Triggers Tier 1 and Tier 2 SMS for people further down the line.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. SKIP LOCKED prevents two doctors in the same clinic from calling the same patient
                cur.execute("""
                    SELECT a.id, a.phone_number, a.patient_name, a.booking_token
                    FROM appointments a
                    WHERE a.clinic_id = %s
                      AND a.status = 'arrived'
                    ORDER BY a.queue_position ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                """, (clinic_id,))
                
                next_patient = cur.fetchone()
                
                if not next_patient:
                    return {"success": False, "message": "No arrived patients in the queue."}
                
                appt_id, phone, name, token = next_patient
                
                # 2. Update status
                cur.execute("""
                    UPDATE appointments 
                    SET status = 'in_consultation', called_at = NOW() 
                    WHERE id = %s
                """, (appt_id,))
                
                # 3. Find patients at exactly position N+2 (Tier 2) and N+5 (Tier 1) 
                # to send them proactive notifications.
                cur.execute("""
                    SELECT phone_number, queue_position 
                    FROM appointments 
                    WHERE clinic_id = %s 
                      AND status = 'arrived'
                    ORDER BY queue_position ASC
                    LIMIT 5
                """, (clinic_id,))
                upcoming = cur.fetchall()
                
        # --- TRANSACTION ENDS HERE ---
        
        # 4. Trigger Network calls (SMS) OUTSIDE the transaction lock!
        
        # Tier 3 (It's your turn!)
        send_tier3_notification(phone, token)
        
        # Trigger Tier 1 and 2 for people further back in line
        for i, (upc_phone, pos) in enumerate(upcoming):
            if i == 1: # 2nd person in line
                send_tier2_notification(upc_phone)
            elif i == 4: # 5th person in line
                # Assume 15 mins per patient wait time for estimation
                send_tier1_notification(upc_phone, wait_mins=15 * 5)
                
        return {"success": True, "patient_name": name, "token": token}
        
    except Exception as e:
        logger.error(f"Error calling next patient: {e}")
        return {"success": False, "message": "System error calling the next patient."}

def get_unconfirmed_patients(clinic_id: str, date_str: str) -> List[Dict[str, Any]]:
    """Fetches patients who have booked but have not yet 'arrived' at the clinic."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.id, a.patient_name, a.phone_number, a.status, a.queue_position, s.slot_time, s.id as slot_id
                    FROM appointments a
                    JOIN slots s ON s.id = a.slot_id
                    WHERE a.clinic_id = %s
                      AND s.slot_time::DATE = %s::DATE
                      AND a.status = 'confirmed'
                    ORDER BY s.slot_time ASC
                """, (clinic_id, date_str))
                
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching unconfirmed: {e}")
        return []

def update_patient_status(appt_id: str, new_status: str, slot_id: str = None) -> bool:
    """Updates a patient's status. If they are a no-show, frees the slot."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE appointments SET status = %s WHERE id = %s", (new_status, appt_id))
                
                # If marked as no-show, we must re-open the slot
                if new_status == 'no_show' and slot_id:
                    cur.execute("UPDATE slots SET is_available = true WHERE id = %s", (slot_id,))
                    
        # Note: If no_show, we would invalidate the cache for this clinic in a full implementation.
        return True
    except Exception as e:
        logger.error(f"Error updating status: {e}")
        return False

def push_patient_back_in_queue(appt_id: str) -> bool:
    """If a patient is running late, push them down the queue by adding to their position."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE appointments 
                    SET queue_position = queue_position + 5 
                    WHERE id = %s
                """, (appt_id,))
        return True
    except Exception as e:
        logger.error(f"Error delaying patient: {e}")
        return False
