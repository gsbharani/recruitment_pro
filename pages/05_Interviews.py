# pages/05_Interviews.py
import streamlit as st
from datetime import date
from db import conn

st.title("Interviews")

tab_schedule, tab_upcoming, tab_past = st.tabs(["Schedule New", "Upcoming", "Past"])

with tab_schedule:
    st.subheader("Schedule Interview")
    # Your existing scheduling code here...

with tab_upcoming:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.resume_name, i.scheduled_date, int.name as interviewer
            FROM interviews i
            JOIN candidates c ON i.candidate_id = c.id
            JOIN interviewers int ON i.interviewer_id = int.id
            WHERE c.recruiter_id = %s AND i.scheduled_date >= %s
            ORDER BY i.scheduled_date
        """, (st.session_state.recruiter_id, date.today()))
        upcoming = cur.fetchall()
    
    if upcoming:
        st.dataframe(upcoming, column_config={
            0: "Candidate",
            1: "Date",
            2: "Interviewer"
        })
    else:
        st.info("No upcoming interviews.")
