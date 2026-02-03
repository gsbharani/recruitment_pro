# app.py
import streamlit as st
from pathlib import Path
import tempfile
import uuid
import pandas as pd
from resume_parser import parse_resume
from text_utils import extract_text, match_skills
from matcher import semantic_score, skill_score
from db import get_connection, save_candidate  # Updated to use Neon/Postgres
from jd_skill_extractor import extract_skills_from_jd
import bcrypt
import psycopg2

# ---------------- Page Config ----------------
st.set_page_config(
    page_title="Talent Fit Analyzer",
    page_icon="🧑‍💼",
    layout="wide",
    initial_sidebar_state="collapsed"   # hide sidebar until logged in
)

# ---------------- Database Connection ----------------
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Create users table for login/signup
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password BYTEA NOT NULL,
            role VARCHAR(50) DEFAULT 'recruiter'
        );
    """)
    # Updated recruiters table (now linked to users)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recruiters (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id),
            name VARCHAR(255) NOT NULL,
            company_name VARCHAR(255)
        );
    """)
    # Updated job_requirements with new fields
    cur.execute("""
        CREATE TABLE IF NOT EXISTS job_requirements (
            id UUID PRIMARY KEY,
            recruiter_id UUID REFERENCES recruiters(id),
            title VARCHAR(255) NOT NULL,
            jd_text TEXT NOT NULL,
            skills TEXT[] NOT NULL,
            status VARCHAR(50) DEFAULT 'active',
            num_positions INTEGER DEFAULT 1,
            budget DECIMAL(10, 2),
            department VARCHAR(255)
        );
    """)
    # Updated candidates with status
    cur.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id UUID PRIMARY KEY,
            recruiter_id UUID REFERENCES recruiters(id),
            jd_id UUID REFERENCES job_requirements(id),
            resume_name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(255),
            experience INTEGER,
            score DECIMAL(5, 2),
            skills TEXT[],
            matched_skills TEXT[],
            missing_skills TEXT[],
            status VARCHAR(50) DEFAULT 'uploaded'  -- uploaded, shortlisted, interview, selected, rejected
        );
    """)
    # New table for interviewers
    cur.execute("""
        CREATE TABLE IF NOT EXISTS interviewers (
            id UUID PRIMARY KEY,
            recruiter_id UUID REFERENCES recruiters(id),
            name VARCHAR(255) NOT NULL,
            department VARCHAR(255) NOT NULL
        );
    """)
    # New table for interviews
    cur.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            id UUID PRIMARY KEY,
            candidate_id UUID REFERENCES candidates(id),
            interviewer_id UUID REFERENCES interviewers(id),
            status VARCHAR(50) DEFAULT 'pending',  -- pending, scheduled, completed
            scheduled_date TIMESTAMP,
            notes TEXT
        );
    """)
    # New table for companies (for about company)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id UUID PRIMARY KEY,
            recruiter_id UUID REFERENCES recruiters(id),
            name VARCHAR(255) NOT NULL,
            description TEXT
        );
    """)
    conn.commit()
    cur.close()
    return conn

conn = init_db()

# ---------------- Session State ----------------
for key in ["user_id", "recruiter_id", "jd_id", "jd_text", "skills", "uploaded_resumes"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "skills" and key != "uploaded_resumes" else ([] if key=="skills" else set())
# ── 1. Login / Signup ────────────────────────────────────────────
if not st.session_state.user_id:
    st.title("🧑‍💼 Talent Fit Analyzer")
    st.markdown("Please sign in to continue")

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        username = st.text_input("Username", key="login_un")
        password = st.text_input("Password", type="password", key="login_pw")

        if st.button("Sign In", type="primary", use_container_width=True):
            if not username or not password:
                st.error("Please enter username and password")
            else:
                cur = conn.cursor()
                cur.execute("SELECT id, password, role FROM users WHERE username = %s", (username,))
                user = cur.fetchone()
                cur.close()

                if user:
                    stored_hash = bytes(user[1])
                    if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                        st.session_state.user_id = user[0]
                        st.session_state.user_role = user[2] or 'recruiter'
                        st.success("Login successful")
                        st.rerun()
                    else:
                        st.error("Incorrect password")
                else:
                    st.error("User not found")

    with tab_signup:
        new_un = st.text_input("Choose Username", key="signup_un")
        new_pw = st.text_input("New Password", type="password", key="signup_pw")
        confirm_pw = st.text_input("Confirm Password", type="password", key="signup_confirm")

        if st.button("Create Account", type="primary", use_container_width=True):
            if new_pw != confirm_pw:
                st.error("Passwords do not match")
            elif len(new_pw) < 8:
                st.error("Password must be at least 8 characters")
            else:
                hashed = bcrypt.hashpw(new_pw.encode('utf-8'), bcrypt.gensalt())
                cur = conn.cursor()
                try:
                    cur.execute(
                        "INSERT INTO users (id, username, password, role) VALUES (%s, %s, %s, 'recruiter')",
                        (str(uuid.uuid4()), new_un.strip(), hashed)
                    )
                    conn.commit()
                    st.success("Account created. You can now log in.")
                except psycopg2.IntegrityError:
                    st.error("Username already taken")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                finally:
                    cur.close()

    st.stop()  # ← Critical: stop here until logged in

# ── 2. Recruiter Profile Setup (only first time) ─────────────────
if not st.session_state.recruiter_id:
    cur = conn.cursor()
    cur.execute("SELECT id FROM recruiters WHERE user_id = %s", (st.session_state.user_id,))
    rec = cur.fetchone()
    cur.close()

    if not rec:
        st.header("👤 Complete your recruiter profile")
        full_name = st.text_input("Your Full Name", key="rec_name")
        company = st.text_input("Company / Organization Name", key="rec_company")

        if st.button("Create Profile", type="primary"):
            if not full_name.strip() or not company.strip():
                st.error("All fields are required")
            else:
                rid = str(uuid.uuid4())
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO recruiters (id, user_id, name, company_name) VALUES (%s, %s, %s, %s)",
                    (rid, st.session_state.user_id, full_name.strip(), company.strip())
                )
                conn.commit()
                cur.close()
                st.session_state.recruiter_id = rid
                st.success("Profile created")
                st.rerun()

        st.stop()  # ← stop until profile exists

# ── 3. Only reach here when fully authenticated ──────────────────
# Show sidebar navigation only now


# ---------------- About Company Dashboard ----------------
st.header("🏢 Company Snapshot")
cur = conn.cursor()
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE status = 'selected') AS selected,
        COUNT(*) FILTER (WHERE status = 'interview') AS in_interview,
        COUNT(*) FILTER (WHERE status = 'rejected') AS rejected,
        COUNT(*) FILTER (WHERE status = 'uploaded' OR status = 'shortlisted') AS in_pipeline_count
        
    FROM candidates WHERE recruiter_id = %s
""", (st.session_state["recruiter_id"],))
stats = cur.fetchone()
cur.close()
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Employees (Selected)", stats[0] or 0)
col2.metric("In Interview", stats[1] or 0)
col3.metric("Rejected", stats[2] or 0)
col4.metric("In Pipeline", stats[3] or 0)

# ---------------- Load Existing JDs ----------------
st.header("📄 Job Description")
cur = conn.cursor()
cur.execute("""
    SELECT id, title, jd_text, skills, num_positions, budget, department 
    FROM job_requirements WHERE recruiter_id = %s
""", (st.session_state["recruiter_id"],))
jds = cur.fetchall()
cur.close()
jd_map = {jd[1]: jd for jd in jds} if jds else {}
selected_jd = st.selectbox("Select JD", ["Create New JD"] + list(jd_map.keys()))
if selected_jd != "Create New JD":
    jd = jd_map[selected_jd]
    st.session_state["jd_text"] = jd[2]
    st.session_state["skills"] = jd[3]
    st.session_state["jd_id"] = jd[0]
    st.success(f"Loaded JD: {selected_jd} ✅")

# ---------------- JD Upload/Create ----------------
st.header("Create / Update Job Description")

jd_title = st.text_input(
    "Job Title",
    placeholder="e.g. Senior Python Developer",
    key="jd_title"
)

jd_text_input = st.text_area(
    "Full Job Description",
    height=200,
    placeholder="Paste the complete JD here or upload a file below...",
    key="jd_text_input"
)

num_positions = st.number_input(
    "Number of Open Positions",
    min_value=1,
    max_value=100,
    value=1,
    step=1,
    key="num_positions"
)

budget_lpa = st.number_input(
    "Budget per Position (in LPA)",
    min_value=0.0,
    max_value=200.0,
    value=0.0,
    step=0.5,
    format="%.2f",
    help="LPA = Lakhs Per Annum",
    key="budget_lpa"
)

department = st.text_input(
    "Department / Team",
    placeholder="e.g. Engineering, Marketing, Data Science",
    key="department"
)

st.markdown("**OR** upload a JD file (PDF or DOCX):")
jd_file = st.file_uploader(
    label="",
    type=["pdf", "docx"],
    accept_multiple_files=False,
    key="jd_file_uploader"
)

if (jd_file or jd_text_input) and st.button("Save JD"):
    if jd_file:
        ext = Path(jd_file.name).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(jd_file.read())
            tmp.flush()
            file_path = tmp.name
        jd_text = extract_text(file_path)
    else:
        jd_text = jd_text_input
    auto_skills = extract_skills_from_jd(jd_text)
    
    jd_id = st.session_state.get("jd_id") or str(uuid.uuid4())
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO job_requirements (id, recruiter_id, title, jd_text, skills, num_positions, budget, department)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET 
            title = EXCLUDED.title, jd_text = EXCLUDED.jd_text, skills = EXCLUDED.skills,
            num_positions = EXCLUDED.num_positions, budget = EXCLUDED.budget, department = EXCLUDED.department
    """, (jd_id, st.session_state["recruiter_id"], jd_title or (jd_file.name if jd_file else "Untitled"), jd_text, auto_skills, num_positions, budget, department))
    conn.commit()
    cur.close()
    st.session_state["jd_text"] = jd_text
    st.session_state["skills"] = auto_skills
    st.session_state["jd_id"] = jd_id
    st.info("💡 Suggested skills from JD (editable): " + ", ".join(auto_skills))
    st.success("JD saved ✅")

# ---------------- Skills ----------------
if st.session_state.get("jd_text"):
    st.subheader("🎯 Skills detected from JD")
    st.caption("Auto-extracted from the job description. Edit only if needed.")
    skills_input = st.text_input(
        label="",
        value=", ".join(st.session_state["skills"]),
        placeholder="Add or remove skills if required"
    )
    if st.button("Save Skills"):
        new_skills = [s.strip().lower() for s in skills_input.split(",")]
        st.session_state["skills"] = new_skills
        cur = conn.cursor()
        cur.execute("UPDATE job_requirements SET skills = %s WHERE id = %s", (new_skills, st.session_state["jd_id"]))
        conn.commit()
        cur.close()
        st.success("Skills saved ✅")

def normalize_skills(skills):
    return set(s.strip().lower() for s in skills if s)

# ---------------- Resume Upload ----------------
st.header("📂 Upload Resumes")
resume_files = st.file_uploader(
    "Upload Resume (PDF/DOCX)",
    type=["pdf", "docx"],
    accept_multiple_files=True
)
if resume_files and st.session_state["jd_id"]:
    for resume_file in resume_files:
        # ---- Duplicate check first ----
        cur = conn.cursor()
        cur.execute("SELECT id FROM candidates WHERE jd_id = %s AND resume_name = %s",
                    (st.session_state["jd_id"], resume_file.name))
        existing = cur.fetchone()
        cur.close()
        if existing:
            st.warning(f"⚠️ {resume_file.name} already uploaded for this JD")
            continue
        # ---- Parse resume and calculate scores ----
        ext = Path(resume_file.name).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(resume_file.read())
            tmp.flush()
            resume_path = tmp.name
        resume_text = extract_text(resume_path)
        parsed = parse_resume(resume_path, st.session_state.get("skills", []))
        jd_score = semantic_score(st.session_state["jd_text"], resume_text)
        skill_match = skill_score(resume_text, st.session_state.get("skills", []))
        final_score = round((jd_score * 0.7) + (skill_match * 0.3), 2)
        jd_skills = normalize_skills(st.session_state["skills"])
        candidate_skills = normalize_skills(parsed["skills_found"])
        matched_skills = list(jd_skills & candidate_skills)
        missing_skills = list(jd_skills - candidate_skills)
        data = {
            "id": str(uuid.uuid4()),
            "recruiter_id": st.session_state["recruiter_id"],
            "jd_id": st.session_state["jd_id"],
            "resume_name": resume_file.name,
            "email": parsed["email"],
            "phone": parsed["mobile"],
            "experience": parsed["experience"],
            "score": final_score,
            "skills": parsed["skills_found"],
            "matched_skills": matched_skills,
            "missing_skills": missing_skills
        }
        save_candidate(data)  # Uses db.py
        st.session_state["uploaded_resumes"].add(resume_file.name)
        # ---- Display resume scoring ----
        st.markdown(f"""
        **📄 {resume_file.name}**
        - 🧠 JD Match: **{jd_score}%**
        - 🛠 Skill Match: **{skill_match}%**
        - 🎯 Final Score: **{final_score}%**
        - ✅ Matched Skills ({len(matched_skills)}): {", ".join(matched_skills) or "None"}
        - ❌ Missing Skills ({len(missing_skills)}): {", ".join(missing_skills) or "None"}
        """)

# ---------------- Ranking ----------------
st.header("📊 Ranked Candidates")
if st.session_state["jd_id"]:
    cur = conn.cursor()
    cur.execute("""
        SELECT resume_name, score, status 
        FROM candidates 
        WHERE recruiter_id = %s AND jd_id = %s 
        ORDER BY score DESC
    """, (st.session_state["recruiter_id"], st.session_state["jd_id"]))
    results = cur.fetchall()
    cur.close()
    if not results:
        st.info("No candidates uploaded yet.")
    else:
        df = pd.DataFrame(results, columns=["resume_name", "score", "status"])
        st.dataframe(df)
        shortlisted = df[df["score"] >= 70]
        st.download_button(
            "Download Shortlisted (CSV)",
            shortlisted.to_csv(index=False),
            file_name="shortlisted_resumes.csv"
        )

# ---------------- Interview Panel ----------------
st.header("👥 Interview Panel")
cur = conn.cursor()
cur.execute("SELECT id, name, department FROM interviewers WHERE recruiter_id = %s", (st.session_state["recruiter_id"],))
interviewers = cur.fetchall()
cur.close()
interviewer_map = {i[1]: i for i in interviewers} if interviewers else {}
selected_interviewer = st.selectbox(
    "Select Interviewer",
    ["Add New"] + list(interviewer_map.keys()),
    key="select_interviewer"                      # ← good practice
)

if selected_interviewer == "Add New":
    new_name = st.text_input(
        "Interviewer Name",
        key="new_interviewer_name"                # ← critical
    )
    new_dept = st.text_input(
        "Department",
        key="new_interviewer_dept"                # ← this fixes your error
    )
    if st.button("Add Interviewer", key="add_interviewer_btn"):
        if new_name and new_dept:
            # your insert logic here
            interviewer_id = str(uuid.uuid4())
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO interviewers (id, recruiter_id, name, department) VALUES (%s, %s, %s, %s)",
                (interviewer_id, st.session_state["recruiter_id"], new_name, new_dept)
            )
            conn.commit()
            cur.close()
            st.success("Interviewer added ✅")
            st.rerun()                          # optional: refresh
        else:
            st.warning("Please fill both name and department")

# Dashboard for interviews
st.subheader("Interview Stats")
cur = conn.cursor()
cur.execute("""
    SELECT i.name, i.department, 
           COUNT(int.id) FILTER (WHERE int.status = 'scheduled') AS scheduled,
           COUNT(int.id) FILTER (WHERE int.status = 'pending') AS pending
    FROM interviewers i
    LEFT JOIN interviews int ON i.id = int.interviewer_id
    WHERE i.recruiter_id = %s
    GROUP BY i.id
""", (st.session_state["recruiter_id"],))
stats = cur.fetchall()
cur.close()
if stats:
    df_stats = pd.DataFrame(stats, columns=["Name", "Department", "Scheduled", "Pending"])
    st.dataframe(df_stats)
else:
    st.info("No interviewers or interviews yet.")

# ---------------- Interview Process ----------------
st.header("🗓️ Interview Process")
if st.session_state["jd_id"]:
    cur = conn.cursor()
    cur.execute("""
        SELECT id, resume_name FROM candidates WHERE jd_id = %s AND status NOT IN ('selected', 'rejected')          
        ORDER BY score DESC 
    """, (st.session_state["jd_id"],))
    candidates = cur.fetchall()
    cur.close()
    if not candidates:
        st.info("No candidates available to schedule interviews (all selected or rejected).")
    else:
        # Safe mapping (though we already checked candidates exists)
        candidate_map = {row[1]: row[0] for row in candidates}

        selected_candidate_name = st.selectbox(
            "Select Candidate to Schedule Interview",
            options=list(candidate_map.keys()),
            key="schedule_candidate_select"
        )

        selected_interviewer_name = st.selectbox(
            "Select Interviewer",
            options=list(interviewer_map.keys()),
            key="schedule_interviewer_select"
        )

        schedule_date = st.date_input(
            "Preferred Interview Date",
            key="schedule_date_input"
        )

        if st.button("Schedule Interview", type="primary", key="schedule_confirm_btn"):
            if not selected_candidate_name or not selected_interviewer_name:
                st.warning("Please select both a candidate and an interviewer.")
            else:
                candidate_id = candidate_map[selected_candidate_name]
                interviewer_id = interviewer_map[selected_interviewer_name][0]  # assuming tuple (id, name, dept)

                # Insert into interviews table
                interview_id = str(uuid.uuid4())
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO interviews (id, candidate_id, interviewer_id, status, scheduled_date)
                    VALUES (%s, %s, %s, 'scheduled', %s)
                """, (interview_id, candidate_id, interviewer_id, schedule_date))
                
                # Update candidate status
                cur.execute("UPDATE candidates SET status = 'interview' WHERE id = %s", (candidate_id,))
                conn.commit()
                cur.close()

                st.success(f"Interview scheduled for **{selected_candidate_name}** with **{selected_interviewer_name}** on **{schedule_date}**")
                st.rerun()  # refresh page to update lists
else:
    st.info("Select a JD first.")

# ---------------- Update Interview Outcome ----------------
st.header("🔔 Update Interview Result")

if st.session_state.get("jd_id"):
    # Show only candidates who are in 'interview' status
    cur = conn.cursor()
    cur.execute("""
        SELECT id, resume_name, email, score, status
        FROM candidates 
        WHERE jd_id = %s AND status = 'interview'
        ORDER BY score DESC
    """, (st.session_state["jd_id"],))
    interviewing_candidates = cur.fetchall()
    cur.close()

    if not interviewing_candidates:
        st.info("No candidates currently in interview stage for this JD.")
    else:
        candidate_options = {f"{row[1]} ({row[2] or 'no email'})": row[0] for row in interviewing_candidates}
        
        selected_candidate_name = st.selectbox(
            "Select Candidate to Update",
            list(candidate_options.keys()),
            key="outcome_candidate_select"
        )
        
        if selected_candidate_name:
            candidate_id = candidate_options[selected_candidate_name]
            
            outcome = st.radio(
                "Interview Outcome",
                options=["Selected", "Rejected", "On Hold", "No Show"],
                key="outcome_radio"
            )
            
            remarks = st.text_area(
                "Remarks / Feedback (optional)",
                height=120,
                key="outcome_remarks"
            )
            
            if st.button("Submit Outcome", key="submit_outcome_btn", type="primary"):
                new_status = {
                    "Selected": "selected",
                    "Rejected": "rejected",
                    "On Hold": "on_hold",
                    "No Show": "rejected"   # or 'no_show' if you want to distinguish
                }.get(outcome, "interview")
                
                cur = conn.cursor()
                cur.execute("""
                    UPDATE candidates 
                    SET status = %s,
                        final_remarks = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (new_status, remarks or None, candidate_id))
                
                conn.commit()
                cur.close()
                
                st.success(f"Outcome updated: **{outcome}** for {selected_candidate_name}")
                st.rerun()   # refresh dashboard & stats
else:
    st.info("Select a Job Description first.")
