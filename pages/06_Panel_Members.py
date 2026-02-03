# pages/06_Panel_Members.py
import streamlit as st
from db import conn
import uuid

st.title("Panel Members / Interviewers")

with conn.cursor() as cur:
    cur.execute("""
        SELECT name, department, email 
        FROM interviewers 
        WHERE recruiter_id = %s
    """, (st.session_state.recruiter_id,))
    panels = cur.fetchall()

st.subheader("Current Interview Panel")
if panels:
    st.dataframe(panels, column_config={
        0: "Name",
        1: "Department",
        2: "Email"
    })
else:
    st.info("No interviewers added yet.")

st.subheader("Add New Interviewer")
name = st.text_input("Name")
dept = st.text_input("Department")
email = st.text_input("Email (optional)")

if st.button("Add Panel Member"):
    if not name or not dept:
        st.error("Name and department are required")
    else:
        iid = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO interviewers (id, recruiter_id, name, department, email)
                VALUES (%s, %s, %s, %s, %s)
            """, (iid, st.session_state.recruiter_id, name, dept, email or None))
            conn.commit()
        st.success("Interviewer added")
        st.rerun()
