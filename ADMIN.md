# The DentaQ Admin & Receptionist Experience

This document outlines how clinic staff (Receptionists and Administrators) manage the clinic's daily operations, generate slots, and handle patients who walk in without an appointment.

---

## 1. Accessing the Admin Panel
Similar to the doctor, the receptionist uses the central web portal.

1. **Login**: The receptionist clicks the **"⚙️ Reception / Admin"** button on the home screen.
2. **Authentication**: They enter the `ADMIN_PASSWORD`.
3. **Dashboard**: They are securely routed to `admin_panel.py`, which contains a tabbed interface for handling different administrative tasks.

---

## 2. Walk-in Booking (Offline Patients)
Not all patients will scan the QR code. Elderly patients or those without smartphones will walk directly up to the reception desk.

### The Problem with standard systems:
Standard online systems require an OTP (One-Time Password) to book. If a patient doesn't have a phone, they can't be added to the queue, completely breaking the clinic's order.

### The DentaQ Solution:
1. The receptionist opens the **"🚶 Walk-in Booking"** tab.
2. They enter the patient's name. The phone number field is **optional**.
3. They select an available slot from the dropdown menu (which hides taken slots automatically).
4. **Bypass Verification**: When the receptionist clicks "Book", the backend (`booking_service.py`) knows this request came from an internal authenticated source. It **bypasses the Twilio SMS OTP requirement**.
5. **Token Generation**: The system generates a token (e.g., `VT-2M9L`). 
   - The receptionist can simply write this token on a paper sticky note and hand it to the patient. 
   - The patient can now watch the TV screen (`queue_display.py`) in the waiting room and wait for `VT-2M9L` to be called!

---

## 3. Slot Management & Generation
Instead of manually typing out every single 30-minute block for the day, DentaQ automates schedule generation.

1. The admin opens the **"📅 Manage Slots"** tab.
2. They select a date from the calendar widget.
3. They define the clinic's working hours (e.g., Start: `9` [9:00 AM], End: `17` [5:00 PM]).
4. **Execution**: When they click "Generate Slots", the `generate_daily_slots()` service calculates all 30-minute intervals and performs a batch SQL insertion into the PostgreSQL database.
5. **Conflict Resolution**: If some slots were already generated for that day, the SQL `ON CONFLICT DO NOTHING` constraint ensures the system doesn't create duplicate slots or overwrite existing bookings.

---

## 4. Analytics & Peak Monitoring (Future Extension)
Because every single action (Booking, No-Show, Cancellation) is logged into the `analytics_events` append-only table, the Admin Panel acts as the data hub. 

*Admins can view (based on the `analytics_service.py`):*
- The busiest hours of the day.
- The average wait time per patient.
- The exact No-Show rate, helping the clinic decide if they need to shorten the 15-minute grace period.
