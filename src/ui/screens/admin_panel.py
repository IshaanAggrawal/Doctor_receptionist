import streamlit as st
import datetime
from src.services.slot_service import generate_daily_slots, fetch_slots
from src.services.booking_service import book_slot
from src.utils.validators import validate_phone
from src.services.queue_service import get_unconfirmed_patients, update_patient_status, push_patient_back_in_queue


def render_admin_panel():
    if st.session_state.get("authenticated_role") != "admin":
        st.error("Unauthorized access.")
        return

    clinic_id = "00000000-0000-0000-0000-000000000000"
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # ── Page Header ────────────────────────────────────────────────
    st.markdown("""
    <div class="dq-page-header">
        <div>
            <p class="dq-title">⚙️ Reception & Admin Panel</p>
            <p class="dq-subtitle">Manage walk-ins, slots, and patient arrivals</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🚶 Walk-in Booking", "📅 Manage Slots", "📞 Manage Arrivals"])

    # ────────────────────────────────────────────────────────────
    # TAB 1: WALK-IN BOOKING
    # ────────────────────────────────────────────────────────────
    with tab1:
        st.markdown("""
        <p style="font-weight:700; font-size:1rem; color:#0F172A; margin:1rem 0 0.25rem;">Book a Walk-in Patient</p>
        <p style="color:#94A3B8; font-size:0.875rem; margin-bottom:1.25rem;">
            Bypass OTP verification for patients standing at the desk.
        </p>
        """, unsafe_allow_html=True)

        slots = fetch_slots(clinic_id, today)

        if not slots:
            st.warning("⚠️ No available slots for today. Generate slots in the 'Manage Slots' tab first.")
        else:
            with st.form("walkin_form"):
                name  = st.text_input("Patient Name", placeholder="e.g. Rohan Sharma")
                phone = st.text_input(
                    "Phone Number (optional)",
                    placeholder="Leave blank or enter number",
                    value=""
                )

                slot_options = {}
                for s in slots:
                    t = s['slot_time']
                    label = t.split("T")[1][:5] if isinstance(t, str) else t.strftime("%H:%M")
                    slot_options[s['id']] = label

                selected_slot_id = st.selectbox(
                    "Select Time Slot",
                    options=list(slot_options.keys()),
                    format_func=lambda x: slot_options[x]
                )

                submitted = st.form_submit_button("📋 Book Walk-in", type="primary", use_container_width=True)

                if submitted:
                    if len(name.strip()) < 2:
                        st.error("❌ Please enter a valid patient name.")
                    else:
                        ph = phone.strip()
                        clean_phone = validate_phone(ph) if ph else f"WALKIN-{name[:6].upper()}"

                        booking = book_slot(
                            clinic_id=clinic_id,
                            slot_id=selected_slot_id,
                            patient_name=name.strip(),
                            phone_number=clean_phone or "WALKIN-NO-PHONE",
                            ip_address="RECEPTION_DESK"
                        )

                        if booking["success"]:
                            token = booking["booking_token"]
                            st.success(f"✅ Successfully booked **{name}**!")
                            st.markdown(f"""
                            <div class="dq-token-card" style="padding:1.75rem;">
                                <p class="dq-token-label">Patient Token — show this on screen or print</p>
                                <p class="dq-token-value" style="font-size:3rem;">{token}</p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.error(f"❌ {booking['message']}")

    # ────────────────────────────────────────────────────────────
    # TAB 2: SLOT MANAGEMENT
    # ────────────────────────────────────────────────────────────
    with tab2:
        st.markdown("""
        <p style="font-weight:700; font-size:1rem; color:#0F172A; margin:1rem 0 0.25rem;">Generate Daily Slots</p>
        <p style="color:#94A3B8; font-size:0.875rem; margin-bottom:1.25rem;">
            Create 30-minute appointment slots for a selected day.
        </p>
        """, unsafe_allow_html=True)

        date_to_gen = st.date_input("Select Date", datetime.datetime.now())

        c1, c2 = st.columns(2)
        with c1:
            start_hour = st.number_input("Start Hour (0–23)", min_value=0, max_value=23, value=9)
        with c2:
            end_hour = st.number_input("End Hour (0–23)", min_value=0, max_value=23, value=17)

        if st.button("⚡ Generate Slots", type="primary", use_container_width=True):
            with st.spinner("Generating slots..."):
                inserted = generate_daily_slots(
                    clinic_id=clinic_id,
                    date_str=date_to_gen.strftime("%Y-%m-%d"),
                    start_hour=start_hour,
                    end_hour=end_hour
                )
            if inserted > 0:
                st.success(f"✅ Generated **{inserted} slots** for {date_to_gen.strftime('%d %b %Y')}!")
            else:
                st.warning("ℹ️ No new slots generated — they may already exist for this date.")

    # ────────────────────────────────────────────────────────────
    # TAB 3: MANAGE ARRIVALS
    # ────────────────────────────────────────────────────────────
    with tab3:
        st.markdown("""
        <p style="font-weight:700; font-size:1rem; color:#0F172A; margin:1rem 0 0.25rem;">Manage Patient Arrivals</p>
        <p style="color:#94A3B8; font-size:0.875rem; margin-bottom:1.25rem;">
            Patients listed below have a confirmed booking but have <strong>not yet been marked as arrived</strong>.
        </p>
        """, unsafe_allow_html=True)

        unconfirmed = get_unconfirmed_patients(clinic_id, today)

        if not unconfirmed:
            st.markdown("""
            <div style="text-align:center; padding: 2.5rem 1rem; background:#fff; border-radius:12px; border:1.5px solid #E2E8F0;">
                <div style="font-size:2rem;">✅</div>
                <p style="font-weight:700; font-size:1rem; color:#0F172A; margin:0.5rem 0;">All caught up!</p>
                <p style="color:#94A3B8; font-size:0.875rem; margin:0;">All booked patients have arrived or there are no active bookings.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            for p in unconfirmed:
                dt_obj = p['slot_time']
                time_str = dt_obj.strftime('%I:%M %p')

                st.markdown(f"""
                <div class="dq-admin-patient-row">
                    <p class="dq-admin-patient-name">{p['patient_name']}</p>
                    <p class="dq-admin-patient-meta">🕒 Slot: {time_str} &nbsp;|&nbsp; 📞 {p['phone_number']}</p>
                </div>
                """, unsafe_allow_html=True)

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("✅ Mark Arrived", key=f"arr_{p['id']}", type="primary", use_container_width=True):
                        update_patient_status(p['id'], 'arrived')
                        st.rerun()
                with c2:
                    if st.button("⏳ Running Late", key=f"late_{p['id']}", use_container_width=True):
                        push_patient_back_in_queue(p['id'])
                        st.success(f"Moved {p['patient_name']} down the queue.")
                with c3:
                    if st.button("❌ No-Show", key=f"drop_{p['id']}", use_container_width=True):
                        update_patient_status(p['id'], 'no_show', p['slot_id'])
                        st.warning(f"Marked {p['patient_name']} as No-Show. Slot reopened.")
                        st.rerun()

                st.markdown("<div style='margin-bottom:0.5rem;'></div>", unsafe_allow_html=True)
