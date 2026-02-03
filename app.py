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

pages = {
    "Dashboard": st.Page("pages/01_dashboard.py", icon=":material/dashboard:"),
    "Jobs": st.Page("pages/02_jobs.py", icon=":material/work:"),
    "Candidates": st.Page("pages/03_candidates.py", icon=":material/people:"),
    "Pipeline": st.Page("pages/04_pipeline.py", icon=":material/linear_scale:"),
    "Interviews": st.Page("pages/05_interviews.py", icon=":material/event:"),
    "Panel Members": st.Page("pages/06_panel.py", icon=":material/groups:"),
}

# Optional: small user info + logout in sidebar
with st.sidebar:
    st.markdown(f"**Welcome** — {st.session_state.get('user_name', 'User')}")
    if st.button("Sign Out", type="secondary", key="logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

pg = st.navigation(pages)
pg.run()


