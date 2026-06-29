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

    st.title("⚙️ Reception & Admin Panel")
    
    clinic_id = "00000000-0000-0000-0000-000000000000"
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    tab1, tab2, tab3 = st.tabs(["🚶 Walk-in Booking", "📅 Manage Slots", "📞 Manage Arrivals"])

    # --- TAB 1: WALK-IN BOOKING (Bypass OTP) ---
    with tab1:
        st.header("Book Walk-in Patient")
        st.write("Receptionists can use this to book patients standing at the desk without sending an OTP.")
        
        slots = fetch_slots(clinic_id, today)
        
        if not slots:
            st.warning("No available slots.")
        else:
            with st.form("walkin_form"):
                name = st.text_input("Patient Name")
                phone = st.text_input("Phone Number (Optional - Leave blank to print token on paper)", value="00000000000")
                
                # Format slots for a dropdown
                slot_options = {s['id']: s['slot_time'].split("T")[1][:5] for s in slots}
                selected_slot_id = st.selectbox("Select Slot", options=list(slot_options.keys()), format_func=lambda x: slot_options[x])
                
                submitted = st.form_submit_button("Book Walk-in", type="primary")
                
                if submitted:
                    if len(name.strip()) < 2:
                        st.error("Enter a valid name.")
                    else:
                        clean_phone = validate_phone(phone) if phone != "00000000000" else "WALKIN-" + name[:4]
                        
                        booking = book_slot(
                            clinic_id=clinic_id,
                            slot_id=selected_slot_id,
                            patient_name=name,
                            phone_number=clean_phone or "WALKIN-NO-PHONE",
                            ip_address="RECEPTION_DESK"
                        )
                        
                        if booking["success"]:
                            st.success(f"Successfully booked {name}!")
                            st.markdown(f"### Token: {booking['booking_token']}")
                            st.info("Write this token on a sticky note for the patient.")
                        else:
                            st.error(booking["message"])


    # --- TAB 2: SLOT MANAGEMENT ---
    with tab2:
        st.header("Generate Daily Slots")
        st.write("Generate 30-minute intervals for a specific day.")
        
        date_to_gen = st.date_input("Select Date", datetime.datetime.now())
        
        col1, col2 = st.columns(2)
        with col1:
            start_hour = st.number_input("Start Hour (e.g. 9 for 9AM)", min_value=0, max_value=23, value=9)
        with col2:
            end_hour = st.number_input("End Hour (e.g. 17 for 5PM)", min_value=0, max_value=23, value=17)
            
        if st.button("Generate Slots"):
            with st.spinner("Generating..."):
                inserted = generate_daily_slots(
                    clinic_id=clinic_id,
                    date_str=date_to_gen.strftime("%Y-%m-%d"),
                    start_hour=start_hour,
                    end_hour=end_hour
                )
                if inserted > 0:
                    st.success(f"Successfully generated {inserted} slots for {date_to_gen}!")
                else:
                    st.warning("No slots generated (they might already exist).")
                    
    # --- TAB 3: MANAGE ARRIVALS (Calling late patients) ---
    with tab3:
        st.header("Manage Patient Arrivals")
        st.write("Patients below have booked a slot but have **not yet arrived** at the clinic.")
        
        unconfirmed = get_unconfirmed_patients(clinic_id, today)
        
        if not unconfirmed:
            st.info("All booked patients have either arrived or there are no active bookings.")
        else:
            for p in unconfirmed:
                raw_time = p['slot_time'].split("T")[1][:5]
                dt_obj = datetime.datetime.strptime(raw_time, "%H:%M")
                
                st.markdown(f"**{p['patient_name']}** (Slot: {dt_obj.strftime('%I:%M %p')})")
                st.write(f"📞 {p['phone_number']}")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("✅ Mark Arrived", key=f"arr_{p['id']}", type="primary"):
                        update_patient_status(p['id'], 'arrived')
                        st.rerun()
                        
                with col2:
                    if st.button("⏳ Running Late (Push Back)", key=f"late_{p['id']}"):
                        # They called and said they are late. We push them down the queue.
                        push_patient_back_in_queue(p['id'])
                        st.success(f"Pushed {p['patient_name']} down the queue by 5 spots.")
                        
                with col3:
                    if st.button("❌ No-Show (Drop)", key=f"drop_{p['id']}"):
                        # Didn't answer the phone. Drop them and reopen the slot.
                        update_patient_status(p['id'], 'no_show', p['slot_id'])
                        st.error(f"Marked {p['patient_name']} as No-Show. Slot reopened.")
                        st.rerun()
                        
                st.divider()
