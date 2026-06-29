# The DentaQ Patient Experience

This document outlines exactly how a patient interacts with the DentaQ system across different scenarios (Online, Offline Walk-in, and Telegram Bot).

---

## 1. Online Booking (QR Code / Web Link)

**Scenario**: A patient is at home and wants to book an appointment, or they are standing outside the clinic and scan the QR code on the glass door.

### The Flow:
1. **Access**: The patient opens `https://dentaq.app/?page=booking&clinic=DR_AHMED` on their phone.
2. **Selection**: They see a grid of available times (e.g., `02:30 PM`, `03:00 PM`). Slots that have already been booked by others are instantly hidden by the Redis cache.
3. **Details**: They tap `03:00 PM` and enter their name (e.g., "Ali Khan") and phone number (e.g., `03001234567`).
4. **Verification (Anti-Spam)**: The system texts them a 6-digit OTP to prove the phone is real.
5. **Confirmation**: They enter the OTP. The system uses a **Database Lock** to guarantee no one else stole their slot in the last 10 seconds.
6. **Result**: The UI shows a massive success message: **Token VT-9X2K**. They also receive an SMS: *"Booking Confirmed! Your slot is at 03:00 PM. Token: VT-9X2K"*.

---

## 2. Online Booking (Telegram Bot)

**Scenario**: A patient prefers messaging over using a website, or they have a poor internet connection but Telegram works fine.

### The Flow:
1. **Access**: The patient searches for `@DentaQBot` on Telegram and sends `/start`.
2. **Selection**: The bot replies: *"Welcome to Dr. Ahmed's Clinic! Please send your phone number to proceed."*
3. **Verification**: After providing the number, the bot texts an OTP to the phone. The patient types the OTP back into the Telegram chat.
4. **Booking**: The bot shows inline buttons inside the chat: `[02:30 PM] [03:00 PM]`. The patient taps one.
5. **Result**: The bot immediately replies: *"Success! Your token is VT-7B1Q."*
6. **Status Check**: At any time, the patient can text `/mystatus` to the bot, and it will reply: *"There are 3 patients ahead of you. Estimated wait time: 45 minutes."*

---

## 3. Offline / Walk-in Booking (Receptionist Handled)

**Scenario**: An elderly patient walks into the clinic. They don't have a smartphone or don't know how to scan a QR code.

### The Flow:
1. **Access**: The patient walks up to the reception desk.
2. **Selection**: The receptionist logs into the **Admin Panel** (`/?page=admin`) on their computer.
3. **Details**: The receptionist asks for the patient's name and phone number. 
4. **Bypass Verification**: Because the patient is physically present, the receptionist clicks a special **"Walk-in Booking"** button. This bypasses the OTP requirement.
5. **Result**: The system books the next available slot.
6. **Token Delivery**: 
   - If the patient gave a phone number, they instantly get an SMS with their token.
   - If the patient has no phone at all, the receptionist writes the generated token (e.g., `VT-1A8M`) on a sticky note and hands it to them.

---

## 4. The Waiting Room Experience (For all patients)

Regardless of *how* the patient booked (Web, Bot, or Walk-in), they all enter the exact same Live Queue.

1. **Tracking**: 
   - A large TV in the waiting room shows the `/queue` screen: *"Now Serving: VT-9X2K (Ali Khan). Next up: VT-7B1Q."*
2. **Proactive Alerts (3-Tier SMS)**:
   - When the queue moves, if a patient is 5 spots away, they get an SMS: *"Your turn is approaching (5 ahead)."*
   - When they are 2 spots away: *"You are almost up! Head to the waiting room."*
   - When it's their exact turn: *"The doctor is ready for you now. Please come in."*
3. **No-Show Policy**: If the TV says "Now Serving: Ali Khan" and Ali doesn't show up after 15 minutes, the automated background Cron Job silently removes Ali from the queue and bumps everyone else up by one spot.
