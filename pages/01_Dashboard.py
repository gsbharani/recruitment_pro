# pages/01_Dashboard.py
import streamlit as st
from db import conn  # adjust import path as needed
import pandas as pd

st.title("Dashboard")

if not st.session_state.get("recruiter_id"):
    st.warning("Please complete your profile first.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)

with conn.cursor() as cur:
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE status = 'selected')     AS selected,
            COUNT(*) FILTER (WHERE status = 'interview')    AS interviewing,
            COUNT(*) FILTER (WHERE status = 'rejected')     AS rejected,
            COUNT(DISTINCT jd_id)                           AS open_jobs
        FROM candidates 
        WHERE recruiter_id = %s
    """, (st.session_state.recruiter_id,))
    stats = cur.fetchone() or (0, 0, 0, 0)

col1.metric("Total Selected", stats[0])
col2.metric("In Interview", stats[1])
col3.metric("Rejected", stats[2])
col4.metric("Open Positions", stats[3])

st.subheader("Recent Activity")
# Example: last 5 candidates or interviews
with conn.cursor() as cur:
    cur.execute("""
        SELECT resume_name, status, score 
        FROM candidates 
        WHERE recruiter_id = %s 
        ORDER BY created_at DESC LIMIT 5
    """, (st.session_state.recruiter_id,))
    recent = pd.DataFrame(cur.fetchall(), columns=["Name", "Status", "Score"])

st.dataframe(recent, use_container_width=True)
