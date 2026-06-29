import streamlit as st
import datetime
from src.services.slot_service import fetch_slots
from src.services.otp_service import generate_and_send_otp, verify_otp
from src.services.booking_service import book_slot
from src.utils.validators import validate_phone


def _step_indicator(current: int):
    def circle(i):
        if i < current:
            bg, color, txt = "#10B981", "#fff", "✓"
        elif i == current:
            bg, color, txt = "#0EA5E9", "#fff", str(i)
        else:
            bg, color, txt = "#E2E8F0", "#94A3B8", str(i)
        return f'<div style="width:32px;height:32px;border-radius:50%;background:{bg};color:{color};display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex-shrink:0;">{txt}</div>'

    def label(i, text, icon):
        if i < current:
            color = "#10B981"
        elif i == current:
            color = "#0EA5E9"
        else:
            color = "#94A3B8"
        return f'<span style="font-size:13px;font-weight:600;margin-left:8px;color:{color};">{icon} {text}</span>'

    def line(i):
        bg = "#10B981" if i < current else "#E2E8F0"
        return f'<div style="flex:1;height:2px;background:{bg};margin:0 8px;"></div>'

    steps = [("Select Slot","📅"), ("Your Details","👤"), ("Verify OTP","🔐"), ("Confirmed!","🎉")]
    html = '<div style="display:flex;align-items:center;margin-bottom:2rem;">'
    for i, (text, icon) in enumerate(steps, 1):
        html += f'<div style="display:flex;align-items:center;">{circle(i)}{label(i, text, icon)}</div>'
        if i < 4:
            html += line(i)
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_booking_page():
    clinic_id = st.query_params.get("clinic", "00000000-0000-0000-0000-000000000000")
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # Session state init
    for key in ["booking_step", "selected_slot", "patient_phone", "patient_name"]:
        if key not in st.session_state:
            st.session_state[key] = 1 if key == "booking_step" else None

    step = st.session_state["booking_step"]

    # ── Page Header ────────────────────────────────────────────────
    st.markdown("""
    <div class="dq-page-header">
        <div>
            <p class="dq-title">🦷 Book Your Appointment</p>
            <p class="dq-subtitle">DentaQ Smart Clinic — Quick &amp; secure booking</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    _step_indicator(step)

    # ──────────────────────────────────────────────────────────────
    # STEP 1: Slot Selection
    # ──────────────────────────────────────────────────────────────
    if step == 1:
        st.markdown("""
        <p style="font-weight:700; font-size:1rem; color:#0F172A; margin-bottom:0.25rem;">
            Select an available time slot
        </p>
        <p style="color:#94A3B8; font-size:0.875rem; margin-top:0;">
            Tap a slot below to begin — available slots shown in white.
        </p>
        """, unsafe_allow_html=True)

        slots = fetch_slots(clinic_id, today)

        if not slots:
            st.warning("⚠️ No slots available for today. Please try again tomorrow or contact the clinic.")
        else:
            cols = st.columns(4)
            for idx, slot in enumerate(slots):
                raw = slot['slot_time']
                if isinstance(raw, str):
                    raw_time = raw.split("T")[1][:5]
                else:
                    raw_time = raw.strftime("%H:%M")
                dt_obj = datetime.datetime.strptime(raw_time, "%H:%M")
                label = dt_obj.strftime("%I:%M %p")

                with cols[idx % 4]:
                    if st.button(label, key=slot['id'], use_container_width=True):
                        st.session_state["selected_slot"] = slot['id']
                        st.session_state["booking_step"] = 2
                        st.rerun()

    # ──────────────────────────────────────────────────────────────
    # STEP 2: Patient Details
    # ──────────────────────────────────────────────────────────────
    elif step == 2:
        st.markdown("""
        <div class="dq-login-card" style="max-width:100%;">
        <p style="font-weight:700; font-size:1.125rem; color:#0F172A; margin-bottom:0.25rem;">Enter your details</p>
        <p style="color:#94A3B8; font-size:0.875rem; margin-top:0; margin-bottom:1.5rem;">
            We'll send a verification code to your phone.
        </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("details_form"):
            name  = st.text_input("Full Name", placeholder="e.g. Ishaan Agrawal")
            phone = st.text_input("Phone Number", placeholder="e.g. +919258895224")
            c1, c2 = st.columns(2)
            with c1:
                submitted = st.form_submit_button("Send OTP →", type="primary", use_container_width=True)
            with c2:
                if st.form_submit_button("← Back", use_container_width=True):
                    st.session_state["booking_step"] = 1
                    st.rerun()

            if submitted:
                clean_phone = validate_phone(phone)
                if not clean_phone:
                    st.error("❌ Invalid phone number. Please use format: +919258895224")
                elif len(name.strip()) < 2:
                    st.error("❌ Please enter your full name.")
                else:
                    with st.spinner("Sending OTP..."):
                        success = generate_and_send_otp(clean_phone)
                    if success:
                        st.session_state["patient_phone"] = clean_phone
                        st.session_state["patient_name"]  = name.strip()
                        st.session_state["booking_step"]  = 3
                        st.rerun()
                    else:
                        st.error("Failed to send OTP. Please check your number or try again.")

    # ──────────────────────────────────────────────────────────────
    # STEP 3: OTP Verification
    # ──────────────────────────────────────────────────────────────
    elif step == 3:
        phone = st.session_state['patient_phone']
        st.info(f"📱 A 6-digit verification code was sent to **{phone}**")

        with st.form("otp_form"):
            otp = st.text_input("Enter 6-digit OTP", placeholder="e.g. 483920", max_chars=6)
            c1, c2 = st.columns(2)
            with c1:
                verified = st.form_submit_button("Confirm Booking ✓", type="primary", use_container_width=True)
            with c2:
                if st.form_submit_button("← Start Over", use_container_width=True):
                    st.session_state["booking_step"] = 1
                    st.rerun()

            if verified:
                otp_result = verify_otp(phone, otp)
                if not otp_result["success"]:
                    st.error(f"❌ {otp_result['message']}")
                else:
                    with st.spinner("Securing your slot..."):
                        booking = book_slot(
                            clinic_id=clinic_id,
                            slot_id=st.session_state["selected_slot"],
                            patient_name=st.session_state["patient_name"],
                            phone_number=phone,
                            ip_address="127.0.0.1"
                        )
                    if booking["success"]:
                        st.session_state["booking_step"]   = 4
                        st.session_state["final_booking"]  = booking
                        st.rerun()
                    else:
                        st.error(booking["message"])
                        if booking.get("error") in ["RACE_CONDITION", "TAKEN"]:
                            if st.button("Browse Other Slots"):
                                st.session_state["booking_step"] = 1
                                st.rerun()

    # ──────────────────────────────────────────────────────────────
    # STEP 4: Success
    # ──────────────────────────────────────────────────────────────
    elif step == 4:
        b = st.session_state.get("final_booking", {})
        token = b.get("booking_token", "—")
        slot_time = b.get("slot_time", "—")
        pos = b.get("queue_position", "—")

        st.markdown(f"""
        <div style="text-align:center; margin:1rem 0 1.5rem;">
            <div style="font-size:2.5rem;">🎉</div>
            <h2 style="color:#0F172A; font-weight:800; margin:0.5rem 0;">Booking Confirmed!</h2>
            <p style="color:#94A3B8;">Show this token at the reception when you arrive.</p>
        </div>
        <div class="dq-token-card">
            <p class="dq-token-label">Your Token</p>
            <p class="dq-token-value">{token}</p>
        </div>
        <div style="background:#fff; border:1.5px solid #E2E8F0; border-radius:12px; padding:1.25rem 1.5rem; margin-top:1rem;">
            <div style="display:flex; justify-content:space-between; padding:0.5rem 0; border-bottom:1px solid #F1F5F9;">
                <span style="color:#94A3B8; font-size:0.875rem;">Appointment Time</span>
                <span style="color:#0F172A; font-weight:600; font-size:0.875rem;">{slot_time}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:0.5rem 0;">
                <span style="color:#94A3B8; font-size:0.875rem;">Queue Position</span>
                <span style="color:#0F172A; font-weight:600; font-size:0.875rem;">#{pos}</span>
            </div>
        </div>
        <p style="color:#94A3B8; font-size:0.8125rem; text-align:center; margin-top:1rem;">
            📲 Details have been sent to your phone via SMS.
        </p>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        if st.button("Book for Another Patient", use_container_width=True):
            for key in ["booking_step", "selected_slot", "patient_phone", "patient_name", "final_booking"]:
                st.session_state.pop(key, None)
            st.rerun()
