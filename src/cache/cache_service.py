import os
import json
import redis
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Fetch connection URL from environment variables
# Format expected: rediss://user:password@host:port (Aiven/Upstash usually provides rediss:// for TLS)
REDIS_URL = os.environ.get("REDIS_URL")

# Initialize Redis client. 
# We set decode_responses=True so we get strings back instead of bytes.
# socket_timeout ensures that if Redis goes down, our app fails fast and falls back to the DB gracefully.
if REDIS_URL:
    try:
        redis_client = redis.from_url(
            REDIS_URL, 
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2
        )
    except Exception as e:
        logger.error(f"Failed to initialize Redis client: {e}")
        redis_client = None
else:
    logger.warning("REDIS_URL environment variable is not set. Caching will be disabled.")
    redis_client = None


def get_available_slots(clinic_id: str, date: str) -> Optional[List[Dict[str, Any]]]:
    """Retrieve available slots for a given clinic and date from cache."""
    if not redis_client:
        return None
    
    key = f"slots:{clinic_id}:{date}"
    try:
        cached = redis_client.get(key)
        if cached:
            return json.loads(cached)
    except redis.RedisError as e:
        logger.error(f"Redis get error for key {key}: {e}")
    
    return None

def set_available_slots(clinic_id: str, date: str, slots: List[Dict[str, Any]]) -> None:
    """Cache available slots with a 30-second TTL (Time-To-Live)."""
    if not redis_client:
        return

    key = f"slots:{clinic_id}:{date}"
    try:
        # 30 seconds TTL so it absorbs traffic spikes but updates quickly
        redis_client.setex(key, 30, json.dumps(slots))
    except redis.RedisError as e:
        logger.error(f"Redis set error for key {key}: {e}")

def invalidate_slots_cache(clinic_id: str, date: Optional[str] = None) -> None:
    """Invalidate slot cache when a booking is made or a no-show slot is released."""
    if not redis_client:
        return

    try:
        if date:
            redis_client.delete(f"slots:{clinic_id}:{date}")
        else:
            # If no date is provided, clear all slots for this clinic
            for key in redis_client.scan_iter(f"slots:{clinic_id}:*"):
                redis_client.delete(key)
    except redis.RedisError as e:
        logger.error(f"Redis delete error for clinic {clinic_id}: {e}")

# ── RATE LIMITING ────────────────────────────────────────────────────────────

def check_rate_limit(ip: str, max_requests: int = 3, window_seconds: int = 3600) -> bool:
    """
    Returns True if request is allowed, False if blocked.
    Limits actions (like booking/OTP requests) by IP address.
    """
    if not redis_client:
        return True  # Fail open if Redis is down
        
    key = f"rate:{ip}"
    try:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, window_seconds)
        return int(count) <= max_requests
    except redis.RedisError as e:
        logger.error(f"Redis rate limit error for IP {ip}: {e}")
        return True # Fail open
