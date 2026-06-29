import streamlit as st
import os
import base64
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="DentaQ — Smart Dental Clinic",
    page_icon="🦷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

from src.ui.screens.booking_page import render_booking_page
from src.ui.screens.doctor_dashboard import render_doctor_dashboard
from src.ui.screens.queue_display import render_queue_display
from src.ui.screens.admin_panel import render_admin_panel

# ── Inject global design system CSS ───────────────────────────────────────────
def inject_css():
    css_path = os.path.join(os.path.dirname(__file__), "src", "ui", "static", "css", "theme.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def _img_b64(filename: str) -> str:
    """Load an image from src/ui/public/ and return as base64 data URI."""
    path = os.path.join(os.path.dirname(__file__), "src", "ui", "public", filename)
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = filename.rsplit(".", 1)[-1]
    return f"data:image/{ext};base64,{data}"

inject_css()

DOCTOR_PASSWORD = os.environ.get("DOCTOR_PASSWORD", "doctor123")
ADMIN_PASSWORD  = os.environ.get("ADMIN_PASSWORD",  "admin123")


# ── LANDING PAGE ───────────────────────────────────────────────────────────────
def render_landing_page():
    tooth_src = _img_b64("icon_tooth.png")
    patient_src = _img_b64("icon_patient.png")
    doctor_src  = _img_b64("icon_doctor.png")
    recep_src   = _img_b64("icon_reception.png")

    tooth_html = f'<img src="{tooth_src}" style="width:64px;height:64px;object-fit:contain;" />' if tooth_src else "🦷"

    st.markdown(f"""
    <div style="text-align:center; padding: 2rem 1rem 1.5rem;">
        <div style="margin-bottom:0.75rem;">{tooth_html}</div>
        <h1 style="font-size:2.25rem; font-weight:900; color:#0F172A !important; margin:0;">Welcome to DentaQ</h1>
        <p style="color:#64748B !important; font-size:1rem; margin-top:0.5rem;">
            Smart dental clinic management — please select your role to continue.
        </p>
    </div>
    """, unsafe_allow_html=True)

    def role_card(img_src, title, desc):
        img_html = f'<img src="{img_src}" style="width:80px;height:80px;object-fit:contain;margin-bottom:0.75rem;" />' if img_src else ""
        return f"""
        <div class="dq-role-card">
            {img_html}
            <p class="dq-role-title">{title}</p>
            <p class="dq-role-desc">{desc}</p>
        </div>
        """

    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        st.markdown(role_card(patient_src, "Patient", "Book an appointment online"), unsafe_allow_html=True)
        if st.button("Enter as Patient", key="role_patient", use_container_width=True, type="primary"):
            st.session_state["role_selection"] = "patient"
            st.rerun()
    with c2:
        st.markdown(role_card(doctor_src, "Doctor", "View live patient queue"), unsafe_allow_html=True)
        if st.button("Enter as Doctor", key="role_doctor", use_container_width=True):
            st.session_state["role_selection"] = "doctor_login"
            st.rerun()
    with c3:
        st.markdown(role_card(recep_src, "Reception", "Manage walk-ins & slots"), unsafe_allow_html=True)
        if st.button("Enter as Reception", key="role_admin", use_container_width=True):
            st.session_state["role_selection"] = "admin_login"
            st.rerun()


# ── LOGIN SCREEN ───────────────────────────────────────────────────────────────
def render_login(role_name: str, icon: str, correct_password: str, authenticated_state: str):
    # Centered login card
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom:1.5rem;">
            <div style="font-size:2.5rem;">{icon}</div>
            <h2 style="font-weight:800; color:#0F172A !important; margin:0.5rem 0 0.25rem;">{role_name} Login</h2>
            <p style="color:#94A3B8 !important; font-size:0.875rem;">Enter your password to continue</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form(f"{authenticated_state}_login_form"):
            pwd = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Login →", type="primary", use_container_width=True)

            if submitted:
                if pwd == correct_password:
                    st.session_state["authenticated_role"] = authenticated_state
                    st.session_state["role_selection"] = authenticated_state
                    st.rerun()
                else:
                    st.error("❌ Incorrect password. Please try again.")

    st.markdown("<div style='margin-top:1rem; text-align:center;'></div>", unsafe_allow_html=True)
    _, mid2, _ = st.columns([1, 2, 1])
    with mid2:
        if st.button("← Back to Home", use_container_width=True):
            st.session_state["role_selection"] = None
            st.rerun()


# ── LOGOUT FOOTER ──────────────────────────────────────────────────────────────
def render_logout_bar():
    st.markdown("<div style='margin-top:2rem; padding-top:1.5rem; border-top:1.5px solid #E2E8F0;'></div>",
                unsafe_allow_html=True)
    _, right = st.columns([4, 1])
    with right:
        if st.button("🔒 Log Out", use_container_width=True):
            st.session_state["authenticated_role"] = None
            st.session_state["role_selection"] = None
            st.rerun()


# ── MAIN ROUTER ────────────────────────────────────────────────────────────────
def main():
    # Direct URL routing (QR codes bypass the portal)
    direct_page = st.query_params.get("page")
    if direct_page == "booking":
        render_booking_page()
        return
    elif direct_page == "queue":
        render_queue_display()
        return

    # State machine
    if "role_selection" not in st.session_state:
        st.session_state["role_selection"] = None

    view = st.session_state["role_selection"]

    if view is None:
        render_landing_page()

    elif view == "patient":
        render_booking_page()
        st.markdown("<div style='margin-top:2rem; padding-top:1.5rem; border-top:1.5px solid #E2E8F0;'></div>",
                    unsafe_allow_html=True)
        _, mid = st.columns([4, 1])
        with mid:
            if st.button("← Home", use_container_width=True):
                st.session_state["role_selection"] = None
                st.rerun()

    elif view == "doctor_login":
        render_login("Doctor", "👨‍⚕️", DOCTOR_PASSWORD, "doctor")

    elif view == "admin_login":
        render_login("Receptionist", "⚙️", ADMIN_PASSWORD, "admin")

    elif view == "doctor":
        if st.session_state.get("authenticated_role") == "doctor":
            render_doctor_dashboard()
            render_logout_bar()
        else:
            st.session_state["role_selection"] = "doctor_login"
            st.rerun()

    elif view == "admin":
        if st.session_state.get("authenticated_role") == "admin":
            render_admin_panel()
            render_logout_bar()
        else:
            st.session_state["role_selection"] = "admin_login"
            st.rerun()


if __name__ == "__main__":
    main()
