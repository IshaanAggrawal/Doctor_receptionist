import os
import psycopg2
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# ALWAYS use the pooled connection string (Port 6543) for Supabase
# This prevents our app from hitting the max connection limit under heavy load.
DB_URL = os.environ.get("SUPABASE_DB_URL_POOLED")

@contextmanager
def get_db_connection():
    """
    Context manager for transactional operations.
    Usage:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ... FOR UPDATE")
                # Do transactional stuff
    
    This ensures that if anything crashes inside the 'with' block, 
    the transaction is rolled back, preventing bad data from saving.
    """
    if not DB_URL:
        raise ValueError("SUPABASE_DB_URL_POOLED environment variable is missing.")

    # We open a connection to the Postgres database
    conn = psycopg2.connect(DB_URL)
    
    try:
        # yield passes the connection to the calling code
        yield conn
        # If the calling code finishes successfully, we commit the transaction!
        conn.commit()
    except Exception as e:
        # If an error happens (e.g. someone else locked the slot first), we undo everything.
        logger.error(f"Database transaction failed. Rolling back. Error: {e}")
        conn.rollback()
        raise e
    finally:
        # No matter what happens (success or failure), we MUST close the connection
        # so we don't leak connections and crash the database.
        conn.close()
