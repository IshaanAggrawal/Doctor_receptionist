import streamlit as st
import datetime
from src.services.queue_service import get_live_queue


def render_queue_display():
    """
    TV waiting room display. Auto-refreshes. Full-screen, no Streamlit chrome.
    """
    st.markdown("""
    <style>
    #MainMenu, header, footer { display: none !important; }
    .main .block-container { padding: 2rem !important; max-width: 100% !important; }
    .stApp { background-color: #0F172A !important; }
    body { background-color: #0F172A !important; }
    h1, h2, h3, p, span, div { color: #F8FAFC !important; }
    </style>
    """, unsafe_allow_html=True)

    clinic_id = st.query_params.get("clinic", "00000000-0000-0000-0000-000000000000")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    now   = datetime.datetime.now().strftime("%I:%M %p")

    # TV Header
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:space-between;
                padding:1.5rem 0; border-bottom:1px solid rgba(255,255,255,0.1); margin-bottom:2rem;">
        <div>
            <h1 style="font-size:2.25rem; font-weight:900; margin:0; color:#F8FAFC !important;">
                🦷 DentaQ Clinic
            </h1>
            <p style="color:rgba(248,250,252,0.6) !important; font-size:0.9rem; margin:0.25rem 0 0;">
                Patient Queue Display
            </p>
        </div>
        <div style="text-align:right;">
            <p style="font-size:2rem; font-weight:800; margin:0; color:#0EA5E9 !important;">{now}</p>
            <p style="color:rgba(248,250,252,0.6) !important; font-size:0.875rem; margin:0;">{datetime.datetime.now().strftime('%d %B %Y')}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    queue = get_live_queue(clinic_id, today)

    if not queue:
        st.markdown("""
        <div style="text-align:center; padding:6rem 2rem;">
            <p style="font-size:4rem; margin:0;">😊</p>
            <h2 style="color:#F8FAFC !important; font-size:2rem; margin:1rem 0 0.5rem;">No patients waiting</h2>
            <p style="color:rgba(248,250,252,0.5) !important;">The queue is currently empty.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    in_consultation = [p for p in queue if p['status'] == 'in_consultation']
    waiting = [p for p in queue if p['status'] == 'arrived']

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown("""
        <p style="font-size:0.75rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase;
                  color:rgba(248,250,252,0.5) !important; margin-bottom:1rem;">👨‍⚕️ Now With Doctor</p>
        """, unsafe_allow_html=True)

        if in_consultation:
            p = in_consultation[0]
            token = p.get('booking_token', '—')
            name  = p['patient_name']
            st.markdown(f"""
            <div class="dq-tv-now-serving">
                <p style="font-size:0.875rem; font-weight:600; color:rgba(255,255,255,0.8) !important; margin:0 0 0.5rem;">Token</p>
                <p class="dq-tv-token">{token}</p>
                <p class="dq-tv-name">{name}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:rgba(255,255,255,0.05); border:2px dashed rgba(255,255,255,0.15);
                        border-radius:16px; padding:3rem 2rem; text-align:center;">
                <p style="color:rgba(248,250,252,0.4) !important; font-size:1.25rem; margin:0;">Doctor is available</p>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <p style="font-size:0.75rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase;
                  color:rgba(248,250,252,0.5) !important; margin-bottom:1rem;">👥 Next in Line</p>
        """, unsafe_allow_html=True)

        if waiting:
            for i, p in enumerate(waiting[:5]):
                token = p.get('booking_token', '—')
                name  = p['patient_name']
                opacity = 1.0 - (i * 0.12)
                st.markdown(f"""
                <div style="background:rgba(255,255,255,{0.07 if i%2==0 else 0.04});
                            border:1px solid rgba(255,255,255,0.1);
                            border-radius:10px; padding:1.125rem 1.5rem; margin-bottom:0.625rem;
                            opacity:{opacity};
                            display:flex; align-items:center; justify-content:space-between;">
                    <div style="display:flex; align-items:center; gap:1rem;">
                        <span style="font-size:1.75rem; font-weight:900; color:#0EA5E9 !important;">
                            {token}
                        </span>
                    </div>
                    <span style="font-size:1.125rem; font-weight:500; color:rgba(248,250,252,0.8) !important;">
                        {name}
                    </span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1);
                        border-radius:10px; padding:2rem; text-align:center;">
                <p style="color:rgba(248,250,252,0.4) !important; margin:0;">No patients waiting</p>
            </div>
            """, unsafe_allow_html=True)

    # Auto-refresh note at bottom
    st.markdown("""
    <div style="text-align:center; margin-top:3rem; padding-top:1.5rem; border-top:1px solid rgba(255,255,255,0.08);">
        <p style="color:rgba(248,250,252,0.3) !important; font-size:0.75rem; margin:0;">
            Refresh the page to update the queue
        </p>
    </div>
    """, unsafe_allow_html=True)
