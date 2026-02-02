# pages/01_Company_Snapshot.py
import streamlit as st
from db import conn  # adjust import as needed

st.title("🏢 Company Snapshot")

# Your existing metrics code here
cur = conn.cursor()
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE status = 'selected')     AS selected_count,
        COUNT(*) FILTER (WHERE status = 'interview')    AS interviewing_count,
        COUNT(*) FILTER (WHERE status = 'rejected')     AS rejected_count,
        COUNT(*) FILTER (WHERE status IN ('uploaded', 'shortlisted')) 
                                                        AS in_pipeline_count
    FROM candidates 
    WHERE recruiter_id = %s
""", (st.session_state["recruiter_id"],))
row = cur.fetchone()
cur.close()
stats = row if row else (0, 0, 0, 0)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Employees", stats[0])
col2.metric("In Interview", stats[1])
col3.metric("Rejected", stats[2])
col4.metric("In Pipeline", stats[3])
