import streamlit as st
import datetime
from src.services.slot_service import fetch_slots
from src.services.otp_service import generate_and_send_otp, verify_otp
from src.services.booking_service import book_slot
from src.utils.validators import validate_phone

def render_booking_page():
    st.title("🦷 Patient Booking")
    st.write("Book your appointment quickly and securely.")
    
    # We need a clinic ID. In a real app, this comes from the QR Code URL (?clinic_id=123)
    # For boilerplate, we'll hardcode a dummy UUID or fetch from query params
    clinic_id = st.query_params.get("clinic", "00000000-0000-0000-0000-000000000000")
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # Initialize Session State for the booking wizard
    if "booking_step" not in st.session_state:
        st.session_state["booking_step"] = 1
    if "selected_slot" not in st.session_state:
        st.session_state["selected_slot"] = None
    if "patient_phone" not in st.session_state:
        st.session_state["patient_phone"] = None
    if "patient_name" not in st.session_state:
        st.session_state["patient_name"] = None

    # --- STEP 1: SELECT A SLOT ---
    if st.session_state["booking_step"] == 1:
        st.subheader("Step 1: Select an Available Slot")
        
        # Fetch slots (Hits Redis first, then Supabase)
        slots = fetch_slots(clinic_id, today)
        
        if not slots:
            st.warning("No slots available for today. Please try again tomorrow.")
        else:
            # Create a nice grid of buttons for the slots
            cols = st.columns(4)
            for index, slot in enumerate(slots):
                # Parse the ISO time string to a readable format
                # e.g., "2026-06-29T14:30:00" -> "02:30 PM"
                raw_time = slot['slot_time'].split("T")[1][:5] # Get HH:MM
                dt_obj = datetime.datetime.strptime(raw_time, "%H:%M")
                formatted_time = dt_obj.strftime("%I:%M %p")
                
                with cols[index % 4]:
                    if st.button(formatted_time, key=slot['id']):
                        st.session_state["selected_slot"] = slot['id']
                        st.session_state["booking_step"] = 2
                        st.rerun()

    # --- STEP 2: ENTER DETAILS ---
    elif st.session_state["booking_step"] == 2:
        st.subheader("Step 2: Your Details")
        st.write("We need your phone number to prevent spam and send you SMS updates.")
        
        with st.form("details_form"):
            name = st.text_input("Full Name")
            phone = st.text_input("Phone Number (e.g. 03001234567)")
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Send OTP", type="primary")
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state["booking_step"] = 1
                    st.rerun()
                    
            if submitted:
                clean_phone = validate_phone(phone)
                if not clean_phone:
                    st.error("Invalid phone number format.")
                elif len(name.strip()) < 2:
                    st.error("Please enter a valid name.")
                else:
                    # Send OTP via Twilio
                    success = generate_and_send_otp(clean_phone)
                    if success:
                        st.session_state["patient_phone"] = clean_phone
                        st.session_state["patient_name"] = name
                        st.session_state["booking_step"] = 3
                        st.rerun()
                    else:
                        st.error("Failed to send OTP. Please check your number or try later.")

    # --- STEP 3: OTP VERIFICATION ---
    elif st.session_state["booking_step"] == 3:
        st.subheader("Step 3: Verify Phone")
        st.info(f"An SMS with a 6-digit code was sent to {st.session_state['patient_phone']}.")
        
        with st.form("otp_form"):
            otp_input = st.text_input("Enter 6-digit OTP", max_chars=6)
            
            col1, col2 = st.columns(2)
            with col1:
                verified = st.form_submit_button("Confirm Booking", type="primary")
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state["booking_step"] = 1
                    st.rerun()
                    
            if verified:
                # 1. Verify OTP
                otp_result = verify_otp(st.session_state["patient_phone"], otp_input)
                
                if not otp_result["success"]:
                    st.error(otp_result["message"])
                else:
                    # 2. OTP is valid! Execute the Atomic Booking Transaction
                    with st.spinner("Securing your slot..."):
                        # We use a dummy IP for boilerplate
                        booking = book_slot(
                            clinic_id=clinic_id,
                            slot_id=st.session_state["selected_slot"],
                            patient_name=st.session_state["patient_name"],
                            phone_number=st.session_state["patient_phone"],
                            ip_address="127.0.0.1" 
                        )
                        
                        if booking["success"]:
                            st.session_state["booking_step"] = 4
                            st.session_state["final_booking"] = booking
                            st.rerun()
                        else:
                            st.error(booking["message"])
                            # If slot was taken by someone else, send them back to Step 1
                            if booking["error"] in ["RACE_CONDITION", "TAKEN"]:
                                if st.button("Browse Other Slots"):
                                    st.session_state["booking_step"] = 1
                                    st.rerun()

    # --- STEP 4: SUCCESS! ---
    elif st.session_state["booking_step"] == 4:
        st.success("🎉 Booking Confirmed!")
        b = st.session_state["final_booking"]
        
        st.write("### Your Token:")
        # Display the token nice and big
        st.markdown(f"<h1 style='text-align: center; color: #1E88E5;'>{b['booking_token']}</h1>", unsafe_allow_html=True)
        
        st.write(f"**Time:** {b['slot_time']}")
        st.write(f"**Queue Position:** {b['queue_position']}")
        
        st.info("We have sent these details to your phone via SMS. Please show this token at the reception when you arrive.")
        
        if st.button("Book Another (Different Patient)"):
            # Reset state
            for key in ["booking_step", "selected_slot", "patient_phone", "patient_name", "final_booking"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
