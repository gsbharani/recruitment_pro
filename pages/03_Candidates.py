# pages/03_Candidates.py
import streamlit as st
import pandas as pd
from db import conn

st.title("Candidates")

if st.session_state.get("jd_id"):
    jd_filter = st.checkbox("Filter by current selected JD only", value=True)
else:
    jd_filter = False

query = """
    SELECT resume_name, email, phone, experience, score, status, jd_id 
    FROM candidates 
    WHERE recruiter_id = %s
"""
params = [st.session_state.recruiter_id]

if jd_filter and st.session_state.get("jd_id"):
    query += " AND jd_id = %s"
    params.append(st.session_state.jd_id)

query += " ORDER BY score DESC"

with conn.cursor() as cur:
    cur.execute(query, params)
    data = cur.fetchall()

if data:
    df = pd.DataFrame(data, columns=["Name", "Email", "Phone", "Exp (yrs)", "Score", "Status", "JD ID"])
    st.dataframe(df, use_container_width=True)
else:
    st.info("No candidates found.")
