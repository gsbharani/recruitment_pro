# pages/02_Jobs.py
import streamlit as st
from db import conn
import uuid

st.title("Jobs / Open Positions")

tab_list, tab_new = st.tabs(["All Jobs", "Create New Job"])

with tab_list:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT title, department, num_positions, status, created_at 
            FROM job_requirements 
            WHERE recruiter_id = %s 
            ORDER BY created_at DESC
        """, (st.session_state.recruiter_id,))
        jobs = cur.fetchall()
    
    if jobs:
        st.dataframe(jobs, column_config={
            0: "Title",
            1: "Department",
            2: "Positions",
            3: "Status",
            4: "Posted"
        }, use_container_width=True)
    else:
        st.info("No jobs posted yet.")

with tab_new:
    st.subheader("Create New Job Requirement")
    title = st.text_input("Job Title")
    dept = st.text_input("Department")
    positions = st.number_input("Number of Positions", min_value=1, value=1)
    budget = st.number_input("Budget (LPA)", min_value=0.0, value=0.0)
    jd_text = st.text_area("Job Description", height=200)

    if st.button("Create Job", type="primary"):
        job_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO job_requirements 
                (id, recruiter_id, title, department, num_positions, budget, jd_text, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'open')
            """, (job_id, st.session_state.recruiter_id, title, dept, positions, budget, jd_text))
            conn.commit()
        st.success("Job created!")
        st.rerun()
