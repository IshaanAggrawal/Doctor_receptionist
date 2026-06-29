import streamlit as st
import datetime
from src.services.queue_service import get_live_queue, call_next_patient

def render_doctor_dashboard():
    # Enforce Security - handled by app.py, but good for redundancy
    if st.session_state.get("authenticated_role") != "doctor":
        st.error("Unauthorized access.")
        return

    st.title("👨‍⚕️ Doctor Dashboard")
    
    # In a real app, this comes from the authenticated doctor's profile
    clinic_id = "00000000-0000-0000-0000-000000000000"
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # The massive Call Next Button
    st.markdown("### Actions")
    if st.button("📢 CALL NEXT PATIENT", type="primary", use_container_width=True):
        with st.spinner("Updating queue and notifying patient..."):
            result = call_next_patient(clinic_id)
            if result["success"]:
                st.success(f"Called {result['patient_name']} (Token: {result['token']})")
                st.balloons()
            else:
                st.warning(result["message"])

    st.markdown("---")
    st.markdown("### 📋 Live Patient Queue")
    
    # Fetch the live queue
    queue = get_live_queue(clinic_id, today)
    
    if not queue:
        st.info("No patients currently in the queue for today.")
        return
        
    # Display the queue in a clean table or list
    for index, patient in enumerate(queue):
        # Format the display
        status_color = "🟢" if patient['status'] == 'arrived' else "🔵" if patient['status'] == 'in_consultation' else "🟡"
        
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
            
            with col1:
                st.subheader(f"#{index + 1}")
            with col2:
                st.write(f"**{patient['patient_name']}**")
                
                # Parse the time
                raw_time = patient['slot_time'].split("T")[1][:5]
                dt_obj = datetime.datetime.strptime(raw_time, "%H:%M")
                st.caption(f"Slot: {dt_obj.strftime('%I:%M %p')}")
                
            with col3:
                st.write(f"{status_color} {patient['status'].upper()}")
                
            with col4:
                if patient['status'] == 'in_consultation':
                    if st.button("Mark Completed", key=f"complete_{patient['id']}"):
                        # We would call a service function to update the DB status to 'completed'
                        # e.g., mark_patient_completed(patient['id'])
                        st.success("Patient marked as completed.")
                        st.rerun()
            
            st.divider()
