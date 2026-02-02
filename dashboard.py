# dashboard.py
import streamlit as st
import pandas as pd
from db import get_connection

st.title("Dashboard")

conn = get_connection()
if st.session_state.get("recruiter_id"):
    cur = conn.cursor()
    cur.execute("SELECT * FROM candidates WHERE recruiter_id = %s", (st.session_state["recruiter_id"],))
    results = cur.fetchall()
    cur.close()
    if results:
        df = pd.DataFrame(results, columns=["id", "recruiter_id", "jd_id", "resume_name", "email", "phone", "experience", "score", "skills", "matched_skills", "missing_skills", "status"])
        st.dataframe(df)
    else:
        st.info("No data yet.")
else:
    st.info("Login and set recruiter first.")
