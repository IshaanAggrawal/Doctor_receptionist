import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

from src.database.supabase_client import supabase
from src.database.pg_client import get_db_connection
from src.cache.cache_service import get_available_slots, set_available_slots

logger = logging.getLogger(__name__)

def fetch_slots(clinic_id: str, date_str: str) -> List[Dict[str, Any]]:
    """
    Highly optimized function to fetch available slots.
    1. Tries Redis cache first (0 database hits).
    2. Falls back to Supabase REST API if cache misses.
    3. Saves result back to Redis.
    """
    # Try Cache First
    cached = get_available_slots(clinic_id, date_str)
    if cached is not None:
        return cached
        
    # Cache Miss - Hit the Database via REST (Scalable Read)
    if not supabase:
        return []
        
    try:
        # We query the slots table where slot_time starts with our date and is_available is true
        response = supabase.table("slots")\
            .select("id, slot_time")\
            .eq("clinic_id", clinic_id)\
            .eq("is_available", True)\
            .gte("slot_time", f"{date_str}T00:00:00")\
            .lte("slot_time", f"{date_str}T23:59:59")\
            .order("slot_time")\
            .execute()
            
        slots = response.data
        
        # Save to Cache for 30 seconds
        if slots:
            set_available_slots(clinic_id, date_str, slots)
            
        return slots
        
    except Exception as e:
        logger.error(f"Error fetching slots for {clinic_id}: {e}")
        return []


def generate_daily_slots(clinic_id: str, date_str: str, start_hour: int = 9, end_hour: int = 17, slot_duration: int = 30) -> int:
    """
    Admin function to generate slots for a specific day.
    e.g. Generates 30-min slots from 9:00 AM to 5:00 PM.
    """
    start_time = datetime.strptime(f"{date_str} {start_hour}:00", "%Y-%m-%d %H:%M")
    end_time = datetime.strptime(f"{date_str} {end_hour}:00", "%Y-%m-%d %H:%M")
    
    slots_to_insert = []
    current_time = start_time
    
    while current_time < end_time:
        slots_to_insert.append({
            "clinic_id": clinic_id,
            "slot_time": current_time.isoformat(),
            "is_available": True
        })
        current_time += timedelta(minutes=slot_duration)
        
    if not slots_to_insert:
        return 0
        
    # We use pg_client here because inserting 20+ records should be transactional
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Use execute_values for fast batch insertion in real app, 
                # but standard loop works for boilerplate
                inserted = 0
                for s in slots_to_insert:
                    try:
                        cur.execute("""
                            INSERT INTO slots (clinic_id, slot_time, is_available)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (s['clinic_id'], s['slot_time'], s['is_available']))
                        inserted += cur.rowcount
                    except Exception as ins_e:
                        logger.warning(f"Skipped inserting slot {s['slot_time']}: {ins_e}")
                        
        return inserted
    except Exception as e:
        logger.error(f"Failed to generate slots: {e}")
        return 0
