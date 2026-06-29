import streamlit as st
import datetime
from src.services.queue_service import get_live_queue

def render_queue_display():
    """
    Designed to be displayed on a large TV screen in the clinic waiting room.
    Auto-refreshes using Streamlit's st_autorefresh (if installed) or manual refresh.
    """
    # Hide the Streamlit sidebar and top menu for a clean TV display
    hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
    # We use a dummy clinic_id for the boilerplate
    clinic_id = st.query_params.get("clinic", "00000000-0000-0000-0000-000000000000")
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # Layout for TV
    st.markdown("<h1 style='text-align: center; font-size: 3rem;'>📺 Live Waiting Room</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    queue = get_live_queue(clinic_id, today)
    
    if not queue:
        st.markdown("<h2 style='text-align: center; color: gray;'>No patients waiting.</h2>", unsafe_allow_html=True)
        return
        
    # Find who is currently in consultation
    in_consultation = [p for p in queue if p['status'] == 'in_consultation']
    waiting = [p for p in queue if p['status'] == 'arrived']
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 👨‍⚕️ Now Serving")
        if in_consultation:
            patient = in_consultation[0]
            st.markdown(
                f"""
                <div style='background-color: #e8f5e9; padding: 20px; border-radius: 15px; border: 2px solid #4caf50;'>
                    <h1 style='color: #2e7d32; text-align: center; font-size: 4rem; margin: 0;'>{patient['booking_token']}</h1>
                    <h3 style='color: #2e7d32; text-align: center; margin: 0;'>{patient['patient_name']}</h3>
                </div>
                """, 
                unsafe_allow_html=True
            )
        else:
            st.info("Doctor is available.")

    with col2:
        st.markdown("### 👥 Next in Line")
        if waiting:
            for i, p in enumerate(waiting[:5]): # Show next 5
                bg_color = "#f3f4f6" if i % 2 == 0 else "#ffffff"
                st.markdown(
                    f"""
                    <div style='background-color: {bg_color}; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #e5e7eb;'>
                        <span style='font-size: 1.5rem; font-weight: bold;'>#{i+1} &nbsp;&nbsp; {p['booking_token']}</span>
                        <span style='float: right; font-size: 1.2rem; color: #6b7280;'>{p['patient_name']}</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        else:
            st.write("Queue is empty.")

    st.markdown("---")
    st.caption("Refresh the page to update (or implement st_autorefresh for real-time updates).")
