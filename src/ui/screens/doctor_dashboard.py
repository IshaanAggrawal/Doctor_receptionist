import streamlit as st
import datetime
import os
import base64
from src.services.queue_service import get_live_queue, call_next_patient, update_patient_status, get_daily_stats


def _img_b64(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "public", filename)
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{data}"


def _status_badge(status: str) -> str:
    s = status.lower()
    if s == 'arrived':
        return '<span class="dq-badge dq-badge-arrived">Arrived</span>'
    elif s == 'in_consultation':
        return '<span class="dq-badge dq-badge-consultation">In Consultation</span>'
    else:
        return '<span class="dq-badge dq-badge-confirmed">Confirmed</span>'


def render_doctor_dashboard():
    if st.session_state.get("authenticated_role") != "doctor":
        st.error("Unauthorized access.")
        return

    clinic_id = "00000000-0000-0000-0000-000000000000"
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    doctor_img = _img_b64("icon_doctor.png")
    img_tag = f'<img src="{doctor_img}" style="width:52px;height:52px;object-fit:contain;margin-right:0.75rem;vertical-align:middle;" />' if doctor_img else "👨‍⚕️"

    # ── Page Header ────────────────────────────────────────────────
    st.markdown(f"""
    <div class="dq-page-header">
        <div style="display:flex;align-items:center;">
            {img_tag}
            <div>
                <p class="dq-title">Doctor Dashboard</p>
                <p class="dq-subtitle">Live patient queue — DentaQ Clinic</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Call Next Patient action (above metrics) ───────────────────
    _, btn_col = st.columns([3, 1])
    with btn_col:
        if st.button("📢 Call Next Patient", type="primary", use_container_width=True):
            with st.spinner("Notifying patient..."):
                result = call_next_patient(clinic_id)
                if result["success"]:
                    st.success(f"✅ Called: **{result['patient_name']}** — Token `{result['token']}`")
                    st.balloons()
                else:
                    st.warning(result["message"])

    # ── KPI Metrics ────────────────────────────────────────────────
    stats = get_daily_stats(clinic_id, today)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f"""
        <div class="dq-stat-card">
            <div class="dq-stat-label">Total Patients Today</div>
            <div class="dq-stat-num" style="color:#0EA5E9;">{stats['total']}</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="dq-stat-card">
            <div class="dq-stat-label">Waiting</div>
            <div class="dq-stat-num" style="color:#F59E0B;">{stats['waiting']}</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="dq-stat-card">
            <div class="dq-stat-label">Completed</div>
            <div class="dq-stat-num" style="color:#10B981;">{stats['completed']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<p class="dq-section-title">📋 Live Patient Queue</p>', unsafe_allow_html=True)

    # ── Patient Queue ──────────────────────────────────────────────
    queue = get_live_queue(clinic_id, today)

    if not queue:
        st.markdown("""
        <div style="text-align:center; padding: 3rem 1rem; background:#fff; border-radius:12px; border:1.5px solid #E2E8F0;">
            <div style="font-size:2.5rem;">🎉</div>
            <p style="font-weight:700; font-size:1rem; color:#0F172A; margin:0.5rem 0;">Queue is empty!</p>
            <p style="color:#94A3B8; font-size:0.875rem; margin:0;">No patients currently in the queue for today.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    for i, patient in enumerate(queue):
        status = patient['status'].lower()
        card_class = f"dq-patient-card status-{status.replace('_', '-')}"
        badge = _status_badge(status)
        dt_obj = patient['slot_time']
        time_str = dt_obj.strftime('%I:%M %p')

        # Render card HTML shell
        st.markdown(f"""
        <div class="{card_class}" style="margin-bottom:0;">
            <div style="display:flex; align-items:center; gap:1rem;">
                <div class="dq-queue-num">#{i+1}</div>
                <div style="flex:1;">
                    <p class="dq-patient-name">{patient['patient_name']}</p>
                    <p class="dq-slot-time">🕒 {time_str}</p>
                </div>
                <div>{badge}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Action button below card (native Streamlit so it's functional)
        if status == 'in_consultation':
            btn_cols = st.columns([6, 2])
            with btn_cols[1]:
                if st.button("✅ Mark Completed", key=f"complete_{patient['id']}", use_container_width=True, type="primary"):
                    update_patient_status(patient['id'], 'completed')
                    st.rerun()
        st.markdown("<div style='margin-bottom:0.625rem;'></div>", unsafe_allow_html=True)
