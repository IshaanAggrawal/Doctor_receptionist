import streamlit as st

import os

# Must be the very first Streamlit command
st.set_page_config(
    page_title="DentaQ - Smart Clinic",
    page_icon="🦷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

from src.screens.booking_page import render_booking_page
from src.screens.doctor_dashboard import render_doctor_dashboard
from src.screens.queue_display import render_queue_display
from src.screens.admin_panel import render_admin_panel

# Fetch passwords from environment (fallback to defaults for testing)
DOCTOR_PASSWORD = os.environ.get("DOCTOR_PASSWORD", "doctor123")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

def render_landing_page():
    st.title("🦷 Welcome to DentaQ")
    st.write("Please select your role to continue:")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🧑‍🤝‍🧑 Patient", use_container_width=True):
            st.session_state["role_selection"] = "patient"
            st.rerun()
            
    with col2:
        if st.button("👨‍⚕️ Doctor", use_container_width=True):
            st.session_state["role_selection"] = "doctor_login"
            st.rerun()
            
    with col3:
        if st.button("⚙️ Reception / Admin", use_container_width=True):
            st.session_state["role_selection"] = "admin_login"
            st.rerun()

def render_login(role_name, correct_password, authenticated_state):
    """Generic login screen for protected roles."""
    st.subheader(f"{role_name} Login")
    
    with st.form(f"{role_name}_login_form"):
        pwd = st.text_input("Enter Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if pwd == correct_password:
                st.session_state["authenticated_role"] = authenticated_state
                st.session_state["role_selection"] = authenticated_state
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")
                
    if st.button("← Back to Home"):
        st.session_state["role_selection"] = None
        st.rerun()

def main():
    """
    Main router for the Streamlit app.
    Supports both direct URL routing (for QR codes) and an interactive Landing Portal.
    """
    # 1. Direct URL Routing (e.g. scanning a QR code skips the portal)
    query_params = st.query_params
    direct_page = query_params.get("page")
    
    if direct_page == "booking":
        render_booking_page()
        return
    elif direct_page == "queue":
        render_queue_display()
        return

    # 2. Interactive Landing Portal (State Machine)
    if "role_selection" not in st.session_state:
        st.session_state["role_selection"] = None
        
    current_view = st.session_state["role_selection"]
    
    if current_view is None:
        render_landing_page()
        
    elif current_view == "patient":
        render_booking_page()
        st.markdown("---")
        if st.button("← Back to Home"):
            st.session_state["role_selection"] = None
            st.rerun()
            
    elif current_view == "doctor_login":
        render_login("Doctor", DOCTOR_PASSWORD, "doctor")
            
    elif current_view == "admin_login":
        render_login("Receptionist / Admin", ADMIN_PASSWORD, "admin")
            
    elif current_view == "doctor":
        # Enforce security: must have authenticated_role
        if st.session_state.get("authenticated_role") == "doctor":
            render_doctor_dashboard()
            st.markdown("---")
            if st.button("Log Out"):
                st.session_state["authenticated_role"] = None
                st.session_state["role_selection"] = None
                st.rerun()
        else:
            st.session_state["role_selection"] = "doctor_login"
            st.rerun()
            
    elif current_view == "admin":
        if st.session_state.get("authenticated_role") == "admin":
            render_admin_panel()
            st.markdown("---")
            if st.button("Log Out"):
                st.session_state["authenticated_role"] = None
                st.session_state["role_selection"] = None
                st.rerun()
        else:
            st.session_state["role_selection"] = "admin_login"
            st.rerun()

if __name__ == "__main__":
    main()
