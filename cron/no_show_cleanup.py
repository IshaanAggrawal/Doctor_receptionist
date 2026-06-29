import sys
import os
import logging

# We need to add the parent directory to sys.path so we can import our src modules
# when running this script as a standalone cron job.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.pg_client import get_db_connection
from src.cache.cache_service import invalidate_slots_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("no_show_cleanup")

def auto_release_no_shows() -> int:
    """
    Finds patients who are >15 minutes late for their slot and haven't checked in (status='arrived').
    Marks them as 'no_show', reopens their slot, and invalidates the Redis cache.
    """
    released_count = 0
    clinics_to_invalidate = set()

    logger.info("Starting no-show cleanup job...")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Find and update the late appointments atomically
                cur.execute("""
                    UPDATE appointments a
                    SET status = 'no_show'
                    WHERE a.status = 'confirmed'
                      AND (
                          SELECT slot_time 
                          FROM slots 
                          WHERE id = a.slot_id
                      ) < NOW() - INTERVAL '15 minutes'
                    RETURNING a.id, a.slot_id, a.clinic_id
                """)
                
                released = cur.fetchall()
                
                if not released:
                    logger.info("No late patients found. Cleanup finished.")
                    return 0

                # 2. Reopen the slots for those appointments
                for appt_id, slot_id, clinic_id in released:
                    cur.execute("""
                        UPDATE slots 
                        SET is_available = true 
                        WHERE id = %s
                    """, (slot_id,))
                    
                    # Keep track of which clinics need their cache cleared
                    clinics_to_invalidate.add(clinic_id)
                    released_count += 1
                    
        # --- TRANSACTION ENDS HERE ---
        
        # 3. Post-transaction: Clear Redis Cache
        # We do this outside the DB lock.
        for clinic_id in clinics_to_invalidate:
            invalidate_slots_cache(clinic_id)
            logger.info(f"Invalidated slot cache for clinic: {clinic_id}")
            
        logger.info(f"Successfully released {released_count} no-show slots.")
        return released_count

    except Exception as e:
        logger.error(f"Critical error during no-show cleanup: {e}")
        return 0

if __name__ == "__main__":
    # When this script is run by the server (e.g. Railway cron job or Heroku Scheduler),
    # it executes the cleanup immediately.
    auto_release_no_shows()
