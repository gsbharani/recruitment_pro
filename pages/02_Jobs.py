# pages/02_Jobs.py
import streamlit as st
import uuid
import pandas as pd
from pathlib import Path
import tempfile
from db import get_connection
from text_utils import extract_text                # ← needed
from jd_skill_extractor import extract_skills_from_jd  # ← needed

st.title("Jobs / Open Positions")

tab_list, tab_new = st.tabs(["All Jobs", "Create / Edit Job"])

# ── Tab 1: List all jobs ───────────────────────────────────────────────
with tab_list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, department, num_positions, budget, status, created_at
                FROM job_requirements
                WHERE recruiter_id = %s
                ORDER BY created_at DESC
            """, (st.session_state.recruiter_id,))
            jobs = cur.fetchall()
    finally:
        conn.close()

    if jobs:
        df = pd.DataFrame(jobs, columns=["ID", "Title", "Dept", "Positions", "Budget (LPA)", "Status", "Posted"])
        st.dataframe(
            df,
            column_config={
                "ID": st.column_config.TextColumn("ID", width="small"),
                "Title": st.column_config.TextColumn("Title"),
                "Dept": "Department",
                "Positions": st.column_config.NumberColumn("Positions"),
                "Budget (LPA)": st.column_config.NumberColumn("Budget (LPA)", format="%.2f"),
                "Status": "Status",
                "Posted": st.column_config.DateColumn("Posted")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No jobs posted yet.")

# ── Tab 2: Create / Edit Job ───────────────────────────────────────────
with tab_new:
    st.subheader("Create or Edit Job Requirement")

    # Load existing jobs for edit selection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title FROM job_requirements WHERE recruiter_id = %s", (st.session_state.recruiter_id,))
            existing = cur.fetchall()
    finally:
        conn.close()

    edit_options = ["Create New"] + [f"{row[1]} (ID: {row[0]})" for row in existing]
    selected = st.selectbox("Action", edit_options, key="job_action_select")

    jd_id = None
    defaults = {
        "title": "",
        "dept": "",
        "positions": 1,
        "budget": 0.0,
        "text": "",
        "skills": []
    }

    if selected != "Create New":
        jd_id = selected.split("ID: ")[-1].strip(")")
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT title, department, num_positions, budget, jd_text, skills
                    FROM job_requirements WHERE id = %s
                """, (jd_id,))
                job = cur.fetchone()
            if job:
                defaults["title"] = job[0] or ""
                defaults["dept"] = job[1] or ""
                defaults["positions"] = job[2] or 1
                defaults["budget"] = float(job[3] or 0.0)
                defaults["text"] = job[4] or ""
                defaults["skills"] = job[5] or []
        finally:
            conn.close()

    # Form fields
    jd_title = st.text_input("Job Title", value=defaults["title"], key="jd_title")
    department = st.text_input("Department / Team", value=defaults["dept"], key="department")
    num_positions = st.number_input("Number of Open Positions", min_value=1, max_value=100, value=defaults["positions"], step=1, key="num_positions")
    budget_lpa = st.number_input("Budget per Position (in LPA)", min_value=0.0, max_value=200.0, value=defaults["budget"], step=0.5, format="%.2f", key="budget_lpa")
    jd_text_input = st.text_area("Full Job Description", value=defaults["text"], height=200, key="jd_text_input")

    st.markdown("**OR** upload a JD file (PDF or DOCX):")
    jd_file = st.file_uploader("", type=["pdf", "docx"], accept_multiple_files=False, key="jd_file_uploader")

    if st.button("Save Job", type="primary"):
        if not jd_title.strip():
            st.error("Job Title is required")
            st.stop()

        # Determine final JD text
        if jd_file is not None:
            ext = Path(jd_file.name).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(jd_file.read())
                tmp.flush()
                file_path = tmp.name
            jd_text = extract_text(file_path)
            fallback_title = jd_file.name
        else:
            jd_text = jd_text_input
            fallback_title = "Untitled"

        auto_skills = extract_skills_from_jd(jd_text)
        final_id = jd_id or str(uuid.uuid4())
        final_title = jd_title or fallback_title

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO job_requirements 
                    (id, recruiter_id, title, jd_text, skills, num_positions, budget, department)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        jd_text = EXCLUDED.jd_text,
                        skills = EXCLUDED.skills,
                        num_positions = EXCLUDED.num_positions,
                        budget = EXCLUDED.budget,
                        department = EXCLUDED.department
                """, (final_id, st.session_state["recruiter_id"], final_title, jd_text, auto_skills, num_positions, budget_lpa, department))
                conn.commit()
        finally:
            conn.close()

        # Update session state
        st.session_state["jd_id"] = final_id
        st.session_state["jd_text"] = jd_text
        st.session_state["skills"] = auto_skills

        st.success(f"Job '{final_title}' saved successfully!")
        # Optional: reset for next creation
        # for k in ["jd_id", "jd_text", "skills"]:
        #     st.session_state.pop(k, None)
        st.rerun()

    # Skills editing
    if st.session_state.get("jd_id"):
        st.subheader("🎯 Skills detected from JD")
        st.caption("Auto-extracted. Edit if needed.")
        skills_input = st.text_input(
            "",
            value=", ".join(st.session_state.get("skills", [])),
            placeholder="Add or remove skills (comma separated)",
            key="skills_edit"
        )
        if st.button("Save Skills", key="save_skills_btn"):
            new_skills = [s.strip().lower() for s in skills_input.split(",") if s.strip()]
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE job_requirements SET skills = %s WHERE id = %s",
                                (new_skills, st.session_state["jd_id"]))
                    conn.commit()
            finally:
                conn.close()
            st.session_state["skills"] = new_skills
            st.success("Skills updated!")
            st.rerun()
