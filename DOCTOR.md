# The DentaQ Doctor Experience

This document outlines how Doctors interact with the DentaQ system to manage their active appointments, handle live queues, and process patients efficiently without any technical friction.

---

## 1. Accessing the Secure Dashboard
Doctors do not use a separate app. They use the same web portal as the patients but interact with a secured route.

1. **Login**: The doctor visits the main URL (`https://dentaq.app/`) and clicks the **"👨‍⚕️ Doctor"** button.
2. **Authentication**: They are prompted for the `DOCTOR_PASSWORD`.
3. **Session State**: Once authenticated, Streamlit saves their session. They are immediately redirected to the `doctor_dashboard.py` view, which hides the navigation menu and shows only clinical data.

---

## 2. Managing the Live Queue
The dashboard is designed for high-visibility and ease of use, even on an iPad or tablet in the consultation room.

1. **Auto-Updating List**: The screen displays a live queue (`get_live_queue`) of all patients for the day. 
2. **Status Colors**:
   - `🟢 ARRIVED`: The patient is physically in the waiting room.
   - `🔵 IN CONSULTATION`: The patient is currently sitting with the doctor.
   - `🟡 CONFIRMED`: The patient booked the slot but has not checked in at reception yet.

---

## 3. The "Call Next Patient" Workflow
This is the most critical function of the doctor's dashboard. Instead of shouting a name or having a receptionist walk back and forth, the doctor simply clicks the massive **"📢 CALL NEXT PATIENT"** button.

### What happens under the hood when the button is clicked?
1. **Concurrency Protection (SKIP LOCKED)**: 
   - If there are two doctors working in the same clinic (e.g., Dr. A and Dr. B), and both hit "Call Next" at the exact same millisecond, the database handles it smoothly.
   - Using PostgreSQL's `SELECT ... FOR UPDATE SKIP LOCKED`, the database locks Patient #1 for Dr. A, skips the locked row, and assigns Patient #2 to Dr. B. **No two doctors will ever call the same patient.**
2. **Status Update**: The patient's status instantly changes from `arrived` to `in_consultation`.
3. **Triggering the 3-Tier SMS System**:
   - **Tier 3**: The patient who was just called receives an SMS: *"The doctor is ready for you now. Please come in. Token: VT-9X2K."*
   - **Tier 2**: The patient who is exactly 2 spots behind receives an SMS: *"You are almost up! Please head to the waiting area."*
   - **Tier 1**: The patient who is exactly 5 spots behind receives an SMS: *"Your turn is approaching. Estimated wait time: 75 mins."*
4. **Waiting Room Display Update**: The TV in the waiting room instantly updates to show the called patient's token under the **"👨‍⚕️ Now Serving"** header.

---

## 4. Completing an Appointment
Once the consultation is over:
1. The doctor clicks **"Mark Completed"** next to the patient's name on the dashboard.
2. The patient is removed from the active queue.
3. The doctor can immediately click **"Call Next Patient"** to repeat the cycle.
