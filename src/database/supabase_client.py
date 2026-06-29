import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

# This is the REST client for Supabase.
# We use this for READ operations (fetching slots, checking clinic details)
# because it's fast, scales automatically, and doesn't eat up our Postgres connection pool!
# Note: We do NOT use this for bookings. Bookings use pg_client.py.

if SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Supabase REST client: {e}")
        supabase = None
else:
    logger.warning("Supabase URL or Key missing. REST Client disabled.")
    supabase = None
