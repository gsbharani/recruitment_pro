# app.py
import streamlit as st
import uuid
import bcrypt
import psycopg2
from db import get_connection

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Talent Fit Analyzer",
    page_icon="🧑‍💼",
    layout="wide"
)

# ── Database init (only once) ────────────────────────────────────────
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Your CREATE TABLE statements (keep them as-is)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password BYTEA NOT NULL,
            role VARCHAR(50) DEFAULT 'recruiter'
        );
    """)
    # ... (all other CREATE TABLE statements for recruiters, job_requirements, etc.)
    conn.commit()
    cur.close()
    return conn

conn = init_db()

# ── Session state defaults ───────────────────────────────────────────
for key in ["user_id", "recruiter_id", "user_role"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ── 1. Login / Signup ────────────────────────────────────────────────
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

    st.stop()

# ── 2. Recruiter Profile Setup ───────────────────────────────────────
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

        st.stop()

# ── 3. Authenticated → Big Button Dashboard ──────────────────────────
st.title("Welcome to Talent Fit Analyzer")
st.markdown("Choose what you'd like to do next:")

# Center the buttons using columns
col1, col2, col3 = st.columns([1, 3, 1])


with col2:
    st.markdown("### Quick Actions")
    
    if st.button("🏢 **Dashboard** – View key metrics & recent activity", use_container_width=True):
        st.switch_page("pages/01_Dashboard.py")

    if st.button("📋 **Jobs** – Manage open positions & requisitions", use_container_width=True):
        st.switch_page("pages/02_Jobs.py")

    if st.button("👤 **Candidates** – Upload, rank & review talent", use_container_width=True):
        st.switch_page("pages/03_Candidates.py")

    if st.button("🔄 **Pipeline** – Track candidates through stages", use_container_width=True):
        st.switch_page("pages/04_Pipeline.py")

    if st.button("🗓️ **Interviews** – Schedule & update outcomes", use_container_width=True):
        st.switch_page("pages/05_Interviews.py")

    if st.button("👥 **Panel** – Manage interviewers & availability", use_container_width=True):
        st.switch_page("pages/06_Panel_Members.py")
        
# Logout at the bottom
st.markdown("---")
if st.button("Sign Out", type="secondary"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()
