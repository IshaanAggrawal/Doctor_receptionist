# DentaQ — Production System Architecture

> Smart Clinic Appointment & Queue Management System  
> Version: 1.0 | Status: Production Design Document  
> Stack: Python · Streamlit · Supabase (PostgreSQL) · Redis · Twilio · Telegram Bot

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Component Breakdown](#3-component-breakdown)
4. [Database Design](#4-database-design)
5. [Transaction Handling](#5-transaction-handling)
6. [Queue System](#6-queue-system)
7. [Caching Layer](#7-caching-layer)
8. [Traffic & Load Handling](#8-traffic--load-handling)
9. [Security & Fraud Prevention](#9-security--fraud-prevention)
10. [Failure Handling & Resilience](#10-failure-handling--resilience)
11. [Project Folder Structure](#11-project-folder-structure)
12. [Environment Variables](#12-environment-variables)
13. [Deployment Checklist](#13-deployment-checklist)
14. [Operational Workflows](#14-operational-workflows)

---

## 1. System Overview

### The Problem

Small clinics (dentists, GPs, physiotherapists) still manage appointments via:
- Phone calls → missed calls, double bookings, no record
- Paper registers → lost, unverifiable, no analytics
- WhatsApp manually → no structure, no queue, no reminders
- **Constant ETA Queries** → with basic online booking, patients still call reception constantly asking "What time should I come?" or "How much longer?".

### What DentaQ Solves

| Feature | How |
|---|---|
| Walk-in QR booking | Patient scans QR on clinic wall → books slot in 60 seconds |
| Bot booking | Patient texts Telegram bot → conversational slot selection |
| **Live ETA Tracking** | **Patients get a live tracking link and can text `/mystatus` to the bot to see dynamic real-time delays, eliminating calls to reception** |
| No-duplicate enforcement | Phone number = identity. One booking per phone per day, enforced at DB level |
| Race condition safety | PostgreSQL row-level locking prevents double-booking under concurrent traffic |
| Anti-flood protection | OTP + rate limiting + IP throttling blocks fake bookings |
| Queue management | Doctor sees live queue. Patients get SMS when it's their turn |
| Auto no-show release | Slot auto-reopens if patient doesn't arrive within 15 mins |
| Analytics | Admin sees peak hours, no-show rate, average wait time |

### User Roles

| Role | Access |
|---|---|
| **Patient** | Scan QR → book slot → get token → arrive → get called |
| **Doctor** | View live queue → call next → mark seen → add notes |
| **Admin / Clinic Owner** | Manage slots, doctors, view analytics, export CSV |
| **Telegram Bot** | Conversational interface for patients to book without QR |

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          PATIENT SIDE                               │
│                                                                     │
│   [QR Code on wall]          [Telegram Bot]        [Direct URL]    │
│         │                         │                     │          │
│         └──────────────┬──────────┘                     │          │
│                        │                                │          │
└────────────────────────┼────────────────────────────────┼──────────┘
                         │                                │
                         ▼                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ENTRY LAYER                                  │
│                                                                     │
│         Streamlit App (app.py)          python-telegram-bot        │
│         (booking UI, queue view)        (bot.py — async)           │
│                        │                        │                  │
└────────────────────────┼────────────────────────┼──────────────────┘
                         │                        │
                         ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       SERVICE LAYER (src/)                          │
│                                                                     │
│   booking_service.py   │  otp_service.py   │  queue_service.py     │
│   slot_service.py      │  sms_service.py   │  analytics_service.py │
│                                                                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
┌──────────────┐  ┌───────────┐  ┌──────────────────────┐
│    REDIS     │  │ SUPABASE  │  │   TWILIO / TELEGRAM  │
│  (Cache +    │  │(PostgreSQL│  │   (SMS + Bot msgs)    │
│   Rate Limit)│  │ + Realtime│  │                      │
└──────────────┘  │ + Auth)   │  └──────────────────────┘
                  └───────────┘
```

### Request Flow (Booking via QR)

```
Patient scans QR
       │
       ▼
Streamlit page loads (clinic_id from QR param)
       │
       ▼
[CACHE CHECK] Redis → available slots cached for 30s
       │  cache hit → show slots instantly (0 DB calls)
       │  cache miss → query Supabase → store in Redis → show slots
       │
       ▼
Patient enters name + phone → clicks "Book"
       │
       ▼
[RATE LIMIT CHECK] Redis → max 3 attempts/IP/hour
       │  blocked → show "Try again later"
       │  pass → continue
       │
       ▼
[DUPLICATE CHECK] Supabase → phone + date already booked?
       │  yes → "You already have a booking today"
       │  no → continue
       │
       ▼
[OTP] Twilio sends 6-digit code → expires in 5 min
       │
       ▼
Patient enters OTP → verified
       │
       ▼
[TRANSACTION] PostgreSQL BEGIN
       │  SELECT slot FOR UPDATE (row lock)
       │  IF slot.is_available = false → ROLLBACK → "Slot taken"
       │  UPDATE slot SET is_available = false
       │  INSERT INTO appointments (...)
       │  COMMIT
       │
       ▼
[CACHE INVALIDATE] Redis: delete slots cache for this clinic+date
       │
       ▼
[SMS] Twilio sends booking token "Your token: VT-4X9K. Slot: 3:00 PM"
       │
       ▼
Supabase Realtime → pushes update to Doctor Dashboard
```

---

## 3. Component Breakdown

### 3.1 Streamlit App (Frontend)

```
Pages:
  /book?clinic=CLINIC_ID     → Patient booking page (public, no login)
  /queue?clinic=CLINIC_ID    → Live queue display (public screen in waiting room)
  /doctor                    → Doctor dashboard (password protected)
  /admin                     → Admin panel (password protected)
```

### 3.2 Telegram Bot

```python
# Conversation states
STATES = {
    ASK_PHONE:    "ask patient for phone number",
    SEND_OTP:     "send OTP, wait for 6-digit reply",
    SHOW_SLOTS:   "show available slots as inline buttons",
    CONFIRM:      "confirm booking, send token",
}
```

Bot handles:
- `/start` → welcome + ask phone
- Slot selection via inline keyboard buttons
- OTP verification inside chat
- `/cancel` to cancel existing booking
- `/mystatus` to check queue position

### 3.3 Services Layer

| Service | Responsibility |
|---|---|
| `booking_service.py` | Orchestrates the full booking flow. Calls slot, OTP, SMS, DB in order. |
| `slot_service.py` | Reads/writes slot availability. Manages cache invalidation. |
| `otp_service.py` | Generates OTP, stores in Redis with TTL, verifies input. |
| `sms_service.py` | Twilio wrapper. Sends OTP, booking confirmation, queue reminders. |
| `queue_service.py` | Manages queue position, "next patient" logic, no-show timer. |
| `analytics_service.py` | Aggregates stats: peak hours, no-show rate, avg wait time. |

---

## 4. Database Design

### Full Schema (PostgreSQL via Supabase)

```sql
-- ─────────────────────────────────────────────
-- CLINICS
-- ─────────────────────────────────────────────
CREATE TABLE clinics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    slug            TEXT UNIQUE NOT NULL,        -- used in QR URL: ?clinic=DR_AHMED
    owner_email     TEXT NOT NULL,
    phone           TEXT,
    address         TEXT,
    timezone        TEXT DEFAULT 'Asia/Karachi',
    max_slots_day   INT DEFAULT 20,
    slot_duration   INT DEFAULT 30,             -- minutes per slot
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────
-- SLOTS (pre-generated per day per clinic)
-- ─────────────────────────────────────────────
CREATE TABLE slots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    slot_time       TIMESTAMPTZ NOT NULL,
    is_available    BOOLEAN DEFAULT true,
    UNIQUE(clinic_id, slot_time)
);

CREATE INDEX idx_slots_clinic_time ON slots(clinic_id, slot_time);
CREATE INDEX idx_slots_available   ON slots(clinic_id, is_available, slot_time);

-- ─────────────────────────────────────────────
-- APPOINTMENTS
-- ─────────────────────────────────────────────
CREATE TABLE appointments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id           UUID NOT NULL REFERENCES clinics(id),
    slot_id             UUID NOT NULL REFERENCES slots(id),
    patient_name        TEXT NOT NULL,
    phone_number        TEXT NOT NULL,
    booking_token       VARCHAR(8) UNIQUE NOT NULL,
    status              TEXT DEFAULT 'confirmed'
                        CHECK (status IN (
                            'pending_otp',
                            'confirmed',
                            'arrived',
                            'in_consultation',
                            'completed',
                            'cancelled',
                            'no_show'
                        )),
    queue_position      INT,
    notes               TEXT,                   -- doctor notes
    booked_via          TEXT DEFAULT 'qr'
                        CHECK (booked_via IN ('qr', 'telegram', 'walk_in', 'admin')),
    ip_address          TEXT,
    otp_verified_at     TIMESTAMPTZ,
    arrived_at          TIMESTAMPTZ,
    called_at           TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now(),

    -- KEY CONSTRAINT: one booking per phone per clinic per day
    UNIQUE(clinic_id, phone_number, (slot_time::DATE))
        -- Note: join with slots table on slot_id to get slot_time for this constraint
        -- Implementation: enforce via trigger (see below) or application layer + DB check
);

CREATE INDEX idx_appt_clinic_status  ON appointments(clinic_id, status);
CREATE INDEX idx_appt_phone          ON appointments(phone_number);
CREATE INDEX idx_appt_token          ON appointments(booking_token);
CREATE INDEX idx_appt_created        ON appointments(created_at DESC);

-- ─────────────────────────────────────────────
-- ONE BOOKING PER PHONE PER DAY — TRIGGER
-- ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION check_one_booking_per_day()
RETURNS TRIGGER AS $$
DECLARE
    slot_date DATE;
    existing_count INT;
BEGIN
    SELECT slot_time::DATE INTO slot_date
    FROM slots WHERE id = NEW.slot_id;

    SELECT COUNT(*) INTO existing_count
    FROM appointments a
    JOIN slots s ON s.id = a.slot_id
    WHERE a.clinic_id = NEW.clinic_id
      AND a.phone_number = NEW.phone_number
      AND s.slot_time::DATE = slot_date
      AND a.status NOT IN ('cancelled', 'no_show')
      AND a.id != NEW.id;

    IF existing_count > 0 THEN
        RAISE EXCEPTION 'DUPLICATE_BOOKING: Phone % already has a booking on %',
            NEW.phone_number, slot_date;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_one_booking_per_day
    BEFORE INSERT ON appointments
    FOR EACH ROW EXECUTE FUNCTION check_one_booking_per_day();

-- ─────────────────────────────────────────────
-- OTP ATTEMPTS (rate limiting at DB level too)
-- ─────────────────────────────────────────────
CREATE TABLE otp_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number    TEXT NOT NULL,
    ip_address      TEXT,
    attempt_count   INT DEFAULT 1,
    blocked_until   TIMESTAMPTZ,
    last_attempt    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_otp_phone  ON otp_attempts(phone_number);
CREATE INDEX idx_otp_ip     ON otp_attempts(ip_address);

-- ─────────────────────────────────────────────
-- ANALYTICS EVENTS (append-only log)
-- ─────────────────────────────────────────────
CREATE TABLE analytics_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   UUID NOT NULL REFERENCES clinics(id),
    event_type  TEXT NOT NULL,          -- 'booking', 'arrival', 'no_show', 'cancellation'
    metadata    JSONB,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_events_clinic_type ON analytics_events(clinic_id, event_type);
CREATE INDEX idx_events_created     ON analytics_events(created_at DESC);
```

### Row Level Security (RLS)

```sql
-- Enable RLS on all tables
ALTER TABLE clinics      ENABLE ROW LEVEL SECURITY;
ALTER TABLE slots        ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

-- Patients can only read slots for a specific clinic (public)
CREATE POLICY "public read slots"
    ON slots FOR SELECT
    USING (is_available = true);

-- Only clinic owner can see their appointments
CREATE POLICY "clinic owner sees own appointments"
    ON appointments FOR SELECT
    USING (
        clinic_id IN (
            SELECT id FROM clinics WHERE owner_email = auth.email()
        )
    );

-- Anyone can insert an appointment (booking flow)
-- Application layer enforces OTP before this call is made
CREATE POLICY "public can book"
    ON appointments FOR INSERT
    WITH CHECK (status = 'pending_otp');
```

---

## 5. Transaction Handling

### The Race Condition Problem

When 50 patients all see "1 slot left" and click at the same time, without proper locking you get double-bookings. PostgreSQL's `SELECT FOR UPDATE` solves this.

### The Booking Transaction (Python)

```python
# src/services/booking_service.py

import psycopg2
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    """Always use this for transactional operations — never use Supabase REST for bookings."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def book_slot(clinic_id: str, slot_id: str, patient_name: str,
              phone_number: str, ip_address: str) -> dict:
    """
    Full atomic booking transaction.
    Returns booking token on success.
    Raises exception on failure (slot taken, duplicate, DB error).
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:

            # STEP 1: Lock the slot row so no other transaction can touch it
            cur.execute("""
                SELECT id, is_available
                FROM slots
                WHERE id = %s
                FOR UPDATE NOWAIT
            """, (slot_id,))
            # NOWAIT = don't queue behind other locks, fail immediately
            # This prevents deadlocks under high concurrency

            slot = cur.fetchone()

            if not slot:
                raise ValueError("SLOT_NOT_FOUND")

            if not slot[1]:  # is_available = false
                raise ValueError("SLOT_ALREADY_TAKEN")

            # STEP 2: Mark slot as taken
            cur.execute("""
                UPDATE slots
                SET is_available = false
                WHERE id = %s
            """, (slot_id,))

            # STEP 3: Generate unique booking token
            booking_token = generate_token()  # e.g. "VT-4X9K"

            # STEP 4: Calculate queue position
            cur.execute("""
                SELECT COUNT(*) + 1 as position
                FROM appointments
                WHERE clinic_id = %s
                  AND status IN ('confirmed', 'arrived')
                  AND slot_id IN (
                      SELECT id FROM slots
                      WHERE slot_time::DATE = (
                          SELECT slot_time::DATE FROM slots WHERE id = %s
                      )
                  )
            """, (clinic_id, slot_id))
            queue_position = cur.fetchone()[0]

            # STEP 5: Insert appointment
            cur.execute("""
                INSERT INTO appointments
                    (clinic_id, slot_id, patient_name, phone_number,
                     booking_token, status, queue_position, ip_address, otp_verified_at)
                VALUES
                    (%s, %s, %s, %s, %s, 'confirmed', %s, %s, NOW())
                RETURNING id, booking_token, queue_position
            """, (clinic_id, slot_id, patient_name, phone_number,
                  booking_token, queue_position, ip_address))

            result = cur.fetchone()

            # STEP 6: Log analytics event
            cur.execute("""
                INSERT INTO analytics_events (clinic_id, event_type, metadata)
                VALUES (%s, 'booking', %s)
            """, (clinic_id, json.dumps({
                "phone": phone_number[-4:],  # last 4 digits only
                "via": "qr",
                "slot_id": slot_id
            })))

            # conn.commit() happens automatically via context manager

            return {
                "appointment_id": result[0],
                "booking_token": result[1],
                "queue_position": result[2]
            }
```

### Handling Transaction Errors

```python
def handle_booking(clinic_id, slot_id, patient_name, phone, ip):
    try:
        result = book_slot(clinic_id, slot_id, patient_name, phone, ip)
        send_confirmation_sms(phone, result["booking_token"])
        invalidate_slots_cache(clinic_id)          # clear Redis cache
        return {"success": True, **result}

    except psycopg2.errors.LockNotAvailable:
        # NOWAIT triggered — another transaction has this slot locked RIGHT NOW
        return {"success": False, "error": "SLOT_BEING_BOOKED",
                "message": "Someone else is booking this slot. Try another."}

    except psycopg2.errors.UniqueViolation as e:
        if "DUPLICATE_BOOKING" in str(e):
            return {"success": False, "error": "ALREADY_BOOKED",
                    "message": "You already have a booking today."}
        return {"success": False, "error": "SLOT_TAKEN",
                "message": "This slot was just taken. Please pick another."}

    except Exception as e:
        log_error(e)
        return {"success": False, "error": "SYSTEM_ERROR",
                "message": "Something went wrong. Please try again."}
```

---

## 6. Queue System

### Queue States

```
confirmed → arrived → in_consultation → completed
                                      → no_show (auto after 15 min)
confirmed → cancelled (patient cancels)
```

### Queue Logic

```python
# src/services/queue_service.py

def get_live_queue(clinic_id: str, date: str) -> list:
    """
    Returns ordered list of today's appointments.
    Uses Redis cache — refreshed every 5 seconds via Supabase Realtime.
    """
    cache_key = f"queue:{clinic_id}:{date}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss — fetch from DB
    result = supabase.table("appointments") \
        .select("*, slots(slot_time)") \
        .eq("clinic_id", clinic_id) \
        .in_("status", ["confirmed", "arrived", "in_consultation"]) \
        .order("queue_position") \
        .execute()

    redis_client.setex(cache_key, 5, json.dumps(result.data))
    return result.data


def call_next_patient(clinic_id: str, doctor_id: str) -> dict:
    """
    Doctor clicks 'Call Next'. Atomically:
    1. Marks current patient as 'completed'
    2. Moves next patient to 'in_consultation'
    3. Sends SMS to patient: "Dr is ready for you"
    4. Invalidates queue cache
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:

            # Get next confirmed patient
            cur.execute("""
                SELECT a.id, a.phone_number, a.patient_name, a.booking_token
                FROM appointments a
                JOIN slots s ON s.id = a.slot_id
                WHERE a.clinic_id = %s
                  AND a.status = 'arrived'
                ORDER BY a.queue_position ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """, (clinic_id,))
            # SKIP LOCKED = if another doctor is also calling next,
            # they get a different patient — no conflicts in multi-doctor clinics

            next_patient = cur.fetchone()
            if not next_patient:
                return {"message": "Queue is empty"}

            appt_id, phone, name, token = next_patient

            cur.execute("""
                UPDATE appointments
                SET status = 'in_consultation', called_at = NOW()
                WHERE id = %s
            """, (appt_id,))

    # SMS outside transaction (network call — never inside a DB transaction)
    send_sms(phone, f"Dr is ready for you now. Please come in. Token: {token}")
    invalidate_queue_cache(clinic_id)

    return {"patient_name": name, "token": token}


def auto_release_no_shows():
    """
    Run this every 5 minutes via a cron job or Supabase Edge Function.
    If a 'confirmed' patient hasn't arrived 15 mins after their slot time,
    mark as no_show and reopen the slot.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE appointments a
                SET status = 'no_show'
                WHERE a.status = 'confirmed'
                  AND (SELECT slot_time FROM slots WHERE id = a.slot_id)
                        < NOW() - INTERVAL '15 minutes'
                RETURNING a.id, a.slot_id, a.clinic_id
            """)
            released = cur.fetchall()

            for appt_id, slot_id, clinic_id in released:
                # Reopen the slot
                cur.execute("""
                    UPDATE slots SET is_available = true WHERE id = %s
                """, (slot_id,))
                # Invalidate cache
                invalidate_slots_cache(clinic_id)

    return len(released)
```

---

## 7. Caching Layer

### Why Cache?

Without caching, every patient who opens the booking page hits the database. For a clinic posted on social media with 200 people opening the link at once, that's 200 simultaneous DB reads per second. Supabase free tier allows ~100 connections. The app crashes.

With Redis caching:
- Available slots: cached 30 seconds → 200 requests hit Redis, 1 hits DB
- Queue state: cached 5 seconds → live enough for display, low DB load
- Clinic info: cached 10 minutes → rarely changes

### Redis Cache Design

```python
# src/services/cache_service.py

import redis
import json
from functools import wraps

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True,
    socket_timeout=2,           # fail fast — never let cache block main flow
    socket_connect_timeout=2
)

# ── Cache Keys ─────────────────────────────────────────────────────
# slots:{clinic_id}:{date}          TTL: 30s   (invalidated on booking)
# queue:{clinic_id}:{date}          TTL: 5s    (invalidated on status change)
# clinic:{clinic_id}                TTL: 600s  (invalidated on admin update)
# rate:{ip_address}                 TTL: 3600s (rate limit counter)
# otp:{phone}                       TTL: 300s  (OTP code, expires in 5 min)
# otp_attempts:{phone}              TTL: 3600s (block counter)

def get_available_slots(clinic_id: str, date: str) -> list | None:
    key = f"slots:{clinic_id}:{date}"
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None

def set_available_slots(clinic_id: str, date: str, slots: list):
    key = f"slots:{clinic_id}:{date}"
    redis_client.setex(key, 30, json.dumps(slots))

def invalidate_slots_cache(clinic_id: str, date: str = None):
    """Call this immediately after a booking is confirmed."""
    if date:
        redis_client.delete(f"slots:{clinic_id}:{date}")
    else:
        # Invalidate all dates for this clinic
        for key in redis_client.scan_iter(f"slots:{clinic_id}:*"):
            redis_client.delete(key)


# ── OTP in Redis ────────────────────────────────────────────────────
def store_otp(phone: str, otp: str):
    """Store OTP with 5-minute expiry. Auto-deletes."""
    redis_client.setex(f"otp:{phone}", 300, otp)

def verify_otp(phone: str, entered_code: str) -> bool:
    stored = redis_client.get(f"otp:{phone}")
    if not stored:
        return False  # expired
    if stored == entered_code:
        redis_client.delete(f"otp:{phone}")  # single use
        return True
    # Wrong code — increment attempt counter
    attempts_key = f"otp_attempts:{phone}"
    attempts = redis_client.incr(attempts_key)
    redis_client.expire(attempts_key, 3600)
    if int(attempts) >= 3:
        redis_client.setex(f"otp_blocked:{phone}", 3600, "1")
    return False

def is_otp_blocked(phone: str) -> bool:
    return redis_client.exists(f"otp_blocked:{phone}") > 0


# ── Rate Limiting ───────────────────────────────────────────────────
def check_rate_limit(ip: str, max_requests: int = 3,
                     window_seconds: int = 3600) -> bool:
    """Returns True if request is allowed, False if blocked."""
    key = f"rate:{ip}"
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, window_seconds)
    return int(count) <= max_requests


# ── Cache Resilience ────────────────────────────────────────────────
def safe_cache_get(key: str):
    """Never crash if Redis is down — just return None (cache miss)."""
    try:
        return redis_client.get(key)
    except redis.RedisError:
        return None  # graceful degradation — app continues without cache

def safe_cache_set(key: str, value: str, ttl: int):
    try:
        redis_client.setex(key, ttl, value)
    except redis.RedisError:
        pass  # cache failure is silent — DB handles the load
```

---

## 8. Traffic & Load Handling

### Scenario: Clinic QR Goes Viral

A clinic posts their QR on Instagram. 500 people open the link in 30 minutes.

#### Without Protection → System Fails

```
500 users → 500 simultaneous Supabase connections
Supabase free: 60 connection limit
→ Connection pool exhausted
→ "Too many connections" error
→ App crashes for everyone
```

#### With DentaQ's Layers → System Survives

```
Layer 1: Redis cache
  500 requests → 1 DB read (slots cached 30s)
  DB sees ~1 req/30s for slot reads

Layer 2: Connection pooling (PgBouncer via Supabase)
  All DB writes go through pooler
  Max 10 real connections → serves unlimited app requests

Layer 3: Streamlit session isolation
  Each user has their own session state
  One user's crash doesn't affect others

Layer 4: Async SMS (Twilio queue)
  SMS never blocks the booking transaction
  Sent after DB commit, in background thread
```

### Connection Pooling Configuration

```python
# Use pgbouncer connection string from Supabase (not direct)
# Direct:   postgresql://user:pass@db.xxx.supabase.co:5432/postgres
# Pooled:   postgresql://user:pass@db.xxx.supabase.co:6543/postgres
#                                                      ^^^^
#                                              PgBouncer port

DATABASE_URL = os.environ["SUPABASE_DB_URL_POOLED"]  # always use pooled
```

### Streamlit Performance Tips

```python
# Cache clinic info for 10 minutes — don't re-fetch on every rerun
@st.cache_data(ttl=600)
def get_clinic_info(clinic_id: str) -> dict:
    return supabase.table("clinics").select("*").eq("id", clinic_id).single().execute().data

# Cache slot list with short TTL
@st.cache_data(ttl=30)
def get_slots_cached(clinic_id: str, date: str) -> list:
    # First try Redis, then DB
    cached = cache_service.get_available_slots(clinic_id, date)
    if cached:
        return cached
    slots = fetch_slots_from_db(clinic_id, date)
    cache_service.set_available_slots(clinic_id, date, slots)
    return slots
```

---

## 9. Security & Fraud Prevention

### Threat Model

| Threat | Attack | Defence |
|---|---|---|
| Slot flooding | Book all slots with fake numbers | OTP required → needs real SIM |
| Duplicate booking | Same person books twice | DB trigger: 1 booking/phone/day |
| Race condition | 2 people book last slot simultaneously | `SELECT FOR UPDATE NOWAIT` |
| Fake OTP | Brute-force 6-digit OTP | 3 attempts then 1-hour block |
| QR link abuse | Share link publicly, mass fake bookings | Rate limit per IP: 3 req/hour |
| Session hijack | Steal booking token | Tokens are 8-char random, single-use at arrival |
| SQL injection | Malicious input in name/phone fields | Parameterized queries only — never f-strings |
| Data scraping | Bot reads all available slots | Slots only shown post-IP rate-limit check |

### Input Validation

```python
import re
from typing import Optional

def validate_phone(phone: str) -> Optional[str]:
    """Normalize and validate phone. Returns clean version or None."""
    # Remove spaces, dashes, parentheses
    clean = re.sub(r'[\s\-\(\)]', '', phone)
    # Accept: +92XXXXXXXXXX, 03XXXXXXXXX, 923XXXXXXXXX
    pattern = r'^(\+92|0|92)[3][0-9]{9}$'
    if re.match(pattern, clean):
        # Normalize to +92 format
        if clean.startswith('0'):
            return '+92' + clean[1:]
        if clean.startswith('92'):
            return '+' + clean
        return clean
    return None

def validate_name(name: str) -> bool:
    """Name must be 2-50 chars, letters and spaces only."""
    return bool(re.match(r'^[A-Za-z\s]{2,50}$', name.strip()))

def sanitize_input(text: str) -> str:
    """Strip any HTML/SQL special chars from free text fields."""
    return re.sub(r'[<>"\'%;()&+]', '', text)[:100]
```

### Booking Token Generation

```python
import secrets
import string

def generate_token() -> str:
    """
    Generate a cryptographically random 8-char booking token.
    Format: VT-XXXX (letters + digits, uppercase)
    Collision probability at 20 bookings/day: negligible.
    """
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(4))
    return f"VT-{random_part}"
    # e.g. VT-4X9K, VT-B2QR
```

---

## 10. Failure Handling & Resilience

### Failure Scenarios and Recovery

```
SCENARIO 1: Redis goes down
─────────────────────────────
Impact:   Cache misses — all requests hit DB directly
          OTP storage unavailable — new bookings temporarily blocked
Recovery: safe_cache_get() returns None → app falls back to DB
          For OTP: store in Supabase otp_attempts table as fallback
          Redis auto-restarts (Railway/Render managed Redis)
Code:     All Redis calls wrapped in try/except — never crash app

SCENARIO 2: Twilio SMS fails
─────────────────────────────
Impact:   Patient doesn't receive OTP or confirmation SMS
Recovery: Booking flow shows OTP on screen as fallback ("SMS failed,
          your code is: 847291 — please note it down")
          Retry SMS in background thread up to 3 times
Code:     Never put SMS inside DB transaction — always after commit

SCENARIO 3: Supabase DB connection drops
─────────────────────────────────────────
Impact:   Bookings fail, queue unreadable
Recovery: Show "System busy, please try again in 30 seconds"
          Streamlit st.error() with retry button
          Queue display falls back to last Redis-cached version
Code:     All DB calls in try/except with user-facing error messages

SCENARIO 4: Concurrent slot booking conflict
─────────────────────────────────────────────
Impact:   Patient clicks "Book" on a slot being booked simultaneously
Recovery: NOWAIT lock raises LockNotAvailable immediately
          User sees: "Someone is booking this slot right now. Pick another."
          No double-booking ever occurs
          Slot list refreshes automatically after 30s cache expiry

SCENARIO 5: Patient books but SMS fails — no token received
────────────────────────────────────────────────────────────
Impact:   Patient can't prove their booking at clinic
Recovery: Booking page shows token on-screen after confirmation
          Patient can also show their phone number to receptionist
          Doctor dashboard can search by phone number
```

### Health Check Endpoint

```python
# Add to app.py for monitoring
def health_check() -> dict:
    status = {"db": "ok", "cache": "ok", "sms": "ok"}
    try:
        supabase.table("clinics").select("id").limit(1).execute()
    except Exception:
        status["db"] = "error"
    try:
        redis_client.ping()
    except Exception:
        status["cache"] = "degraded"  # not fatal
    return status
```

---

## 11. Project Folder Structure

```
DentaQ/
│
├── app.py                          ← Streamlit entry point
├── bot.py                          ← Telegram bot (run separately)
├── requirements.txt
├── .env.example
│
├── src/
│   ├── screens/
│   │   ├── booking_page.py         ← Patient QR booking UI
│   │   ├── queue_display.py        ← Live waiting room screen
│   │   ├── doctor_dashboard.py     ← Doctor: call next, mark seen
│   │   └── admin_panel.py          ← Slot management, analytics
│   │
│   ├── services/
│   │   ├── booking_service.py      ← Core booking transaction
│   │   ├── slot_service.py         ← Slot reads/writes + cache
│   │   ├── queue_service.py        ← Queue logic, no-show timer
│   │   ├── otp_service.py          ← Generate, store, verify OTP
│   │   ├── sms_service.py          ← Twilio SMS wrapper
│   │   └── analytics_service.py    ← Stats aggregation
│   │
│   ├── database/
│   │   ├── supabase_client.py      ← Supabase REST client (reads)
│   │   ├── pg_client.py            ← psycopg2 (transactional writes)
│   │   └── schema.sql              ← Full DB schema (this file)
│   │
│   ├── cache/
│   │   └── cache_service.py        ← Redis wrapper + resilience
│   │
│   └── utils/
│       ├── validators.py           ← Phone, name, input validation
│       ├── token_gen.py            ← Booking token generation
│       ├── qr_generator.py         ← Clinic QR code generation
│       └── logger.py               ← Structured logging
│
├── cron/
│   └── no_show_cleanup.py          ← Runs every 5 min (auto-release slots)
│
└── .streamlit/
    └── secrets.toml                ← All credentials (never commit)
```

---

## 12. Environment Variables

```toml
# .streamlit/secrets.toml

[supabase]
SUPABASE_URL      = "https://xxxx.supabase.co"
SUPABASE_ANON_KEY = "eyJ..."
SUPABASE_DB_URL_POOLED = "postgresql://postgres:pass@db.xxx.supabase.co:6543/postgres"

[redis]
REDIS_HOST = "redis-xxxx.railway.app"
REDIS_PORT = 6379
REDIS_PASSWORD = "xxxx"

[twilio]
TWILIO_ACCOUNT_SID = "ACxxxx"
TWILIO_AUTH_TOKEN  = "xxxx"
TWILIO_PHONE       = "+1415xxxxxxx"

[telegram]
TELEGRAM_BOT_TOKEN = "xxxxxxx:xxxxxxx"

[app]
APP_SECRET_KEY   = "random-32-char-string"
DOCTOR_PASSWORD  = "hashed-password"
ADMIN_PASSWORD   = "hashed-password"
```

---

## 13. Deployment Checklist

### Pre-Launch

- [ ] Run `schema.sql` on Supabase — all tables, indexes, triggers created
- [ ] Enable Row Level Security on all tables
- [ ] Set up Redis on Railway (free tier, auto-restart enabled)
- [ ] Add all secrets to Streamlit Cloud environment variables
- [ ] Test booking flow end-to-end with a real phone number
- [ ] Test slot locking: open two browser tabs, book same slot simultaneously
- [ ] Test OTP block: enter wrong OTP 3 times, verify 1-hour block
- [ ] Test duplicate block: book twice with same phone, verify second is rejected
- [ ] Deploy `bot.py` on Railway as a background worker (not Streamlit)
- [ ] Set up cron job for `no_show_cleanup.py` (every 5 minutes)
- [ ] Generate clinic QR codes and test scan on Android + iOS
- [ ] Load test: simulate 50 concurrent bookings (use `locust` or `k6`)

### Monitoring

- [ ] Add Sentry for error tracking (`pip install sentry-sdk`)
- [ ] Add UptimeRobot to ping `/health` every 5 minutes
- [ ] Set Supabase alerts for DB connections > 80% of limit
- [ ] Set Redis alerts for memory > 80%

### Client Handover

- [ ] Clinic slug configured (e.g. `?clinic=DR_AHMED_DENTAL`)
- [ ] QR code printed and laminated
- [ ] Doctor password set and shared securely
- [ ] Admin onboarded: how to add/remove slots, view analytics
- [ ] Twilio number verified for the clinic's country

---

## Key Technical Decisions (for README / interviews)

| Decision | Why |
|---|---|
| `SELECT FOR UPDATE NOWAIT` instead of application-level locking | DB-level locks are atomic. App locks fail under horizontal scaling and Streamlit's rerun model. |
| Redis for OTP storage, not DB | OTP must auto-expire (TTL). DB-based expiry needs a cron job. Redis TTL is instant and atomic. |
| Phone number as identity, not name | Names are not unique. Phone numbers are. Using phone as the dedup key is simple, reliable, and user-verifiable. |
| Supabase Realtime for doctor dashboard | Push updates without polling. Doctor's queue refreshes automatically when a patient arrives — no page refresh needed. |
| SMS sent outside DB transaction | Network calls inside a transaction hold the DB lock open for seconds. Always commit first, notify after. |
| `SKIP LOCKED` for multi-doctor clinics | Two doctors calling "next" simultaneously get different patients. No coordination needed in application code. |
| Cache TTL of 30s for slots | Short enough that a slot released by a no-show reappears quickly. Long enough to absorb traffic spikes. |

---

## 14. Operational Workflows

### 14.1 How Doctors See Appointments
- **Secure Dashboard**: Doctors log into the `/doctor` route using the `DOCTOR_PASSWORD`.
- **Real-Time Queue**: The dashboard displays a live, auto-updating list of today's appointments fetched from the Redis cache (synced via Supabase Realtime).
- **Patient Tracking**: Patients are grouped by status: **Arrived** (waiting), **In Consultation**, and **Completed**.
- **One-Click Calling**: Clicking "Call Next" uses the `SKIP LOCKED` SQL mechanism to fetch the next patient without conflicts, instantly sending an SMS to the patient and updating the clinic's waiting room screen.

### 14.2 How to Tell Expected Time & Notifications
- **Baseline Calculation**: Expected time is initially based on the clinic's `slot_duration` (e.g., 30 minutes) and the patient's `queue_position`.
- **Dynamic Updates**: As the doctor progresses through the queue, the system tracks the actual time elapsed. If consultations run long, the ETA for downstream patients is dynamically shifted.
- **Patient Visibility**: 
  - **Live Screen**: Patients waiting in the clinic can see their estimated wait time on the Streamlit `/queue` screen.
  - **Remote Status**: Patients can text `/mystatus` to the Telegram bot or check their original booking link to see updated ETA and queue position.
- **3-Tier SMS Notifications**: To keep patients informed without needing to manually check, the system triggers automated SMS alerts based on queue position:
  1. **Tier 1 (5 appointments before)**: "Your turn is approaching. There are 5 patients ahead of you. Estimated wait time: X mins."
  2. **Tier 2 (2 appointments before)**: "You are almost up! There are 2 patients ahead of you. Please head to the waiting area if you haven't already."
  3. **Tier 3 (It's your turn)**: "The doctor is ready for you now. Please come in. Token: [TOKEN]" (Triggered by the doctor clicking 'Call Next').

### 14.3 How We Handle Missed Appointments (No-Shows)
- **15-Minute Grace Period**: Patients are expected to check in (status changed to `arrived`) by their slot time. They are given a 15-minute grace period.
- **Automated Cleanup**: A background cron job (`cron/no_show_cleanup.py`) runs every 5 minutes. It scans for appointments where `status = 'confirmed'` and `slot_time < NOW() - INTERVAL '15 minutes'`.
- **Slot Reopening**: These appointments are automatically marked as `no_show`. The corresponding slot is instantly updated to `is_available = true`.
- **Cache Invalidation**: The Redis slots cache is immediately invalidated, allowing a walk-in or new online user to book the freed-up slot without manual admin intervention.

---

*Document authored for DentaQ v1.0 — Production Client Deployment*
