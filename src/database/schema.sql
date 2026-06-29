-- ─────────────────────────────────────────────
-- DentaQ Database Schema (PostgreSQL via Supabase)
-- ─────────────────────────────────────────────

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
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_appt_clinic_status  ON appointments(clinic_id, status);
CREATE INDEX idx_appt_phone          ON appointments(phone_number);
CREATE INDEX idx_appt_token          ON appointments(booking_token);
CREATE INDEX idx_appt_created        ON appointments(created_at DESC);

-- ─────────────────────────────────────────────
-- ONE BOOKING PER PHONE PER DAY — TRIGGER
-- ─────────────────────────────────────────────
-- This enforces the rule dynamically so a user can't book two slots in the same day.
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

-- ─────────────────────────────────────────────
-- ROW LEVEL SECURITY (RLS)
-- ─────────────────────────────────────────────
ALTER TABLE clinics      ENABLE ROW LEVEL SECURITY;
ALTER TABLE slots        ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

-- Patients can only read slots for a specific clinic that are available
CREATE POLICY "public read slots"
    ON slots FOR SELECT
    USING (is_available = true);
