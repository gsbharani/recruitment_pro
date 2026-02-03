# pages/04_Pipeline.py
import streamlit as st
from streamlit_kanban_board_goviceversa import kanban_board  # main import
import uuid
from db import conn  # your psycopg2 connection

st.title("Recruitment Pipeline")

# ── Define your stages (customize as needed) ─────────────────────
columns = [
    {"id": "applied",     "title": "Applied",     "color": "#E8F0FE"},
    {"id": "screened",    "title": "Screened",    "color": "#FFF3E0"},
    {"id": "interview",   "title": "Interview",   "color": "#E8F5E9"},
    {"id": "offer",       "title": "Offer",       "color": "#E3F2FD"},
    {"id": "hired",       "title": "Hired",       "color": "#C8E6C9"},
    {"id": "rejected",    "title": "Rejected",    "color": "#FFEBEE"},
]

# ── Load candidates grouped by status ────────────────────────────
def load_pipeline_data():
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                id,
                resume_name AS title,
                status AS column_id,
                score,
                email,
                matched_skills
            FROM candidates
            WHERE recruiter_id = %s
            ORDER BY score DESC
        """, (st.session_state.recruiter_id,))
        rows = cur.fetchall()

    # Group into dict for kanban format: {column_id: [card, ...]}
    board_data = {col["id"]: [] for col in columns}
    
    for row in rows:
        card = {
            "id": row[0],
            "title": row[1],
            "subtitle": f"Score: {row[3]} | {row[4] or 'No email'}",
            "description": f"Skills: {', '.join(row[5][:3]) if row[5] else 'None'} ...",
            # You can add more fields: tags, avatar, due_date, etc.
        }
        status = row[2] if row[2] in board_data else "applied"  # fallback
        board_data[status].append(card)
    
    return board_data

# ── Render Kanban ────────────────────────────────────────────────
board_state = load_pipeline_data()

updated_board = kanban_board(
    columns=columns,
    items=board_state,
    key="recruitment_kanban",
    height=800,
    # Optional props – check docs for more
    allow_drag=True,
    allow_add_card=False,          # or True if you want manual add
    card_max_width=320,
    enable_search=True,
    enable_filter=True,
)

# ── Handle drag & drop changes ───────────────────────────────────
if updated_board != board_state:
    st.write("Board updated! Saving new statuses...")

    # Example: detect moved cards and update DB
    for col_id, cards in updated_board.items():
        for card in cards:
            candidate_id = card["id"]
            new_status = col_id
            
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE candidates 
                    SET status = %s 
                    WHERE id = %s AND recruiter_id = %s
                """, (new_status, candidate_id, st.session_state.recruiter_id))
            conn.commit()
    
    st.success("Pipeline updated!")
    st.rerun()

# ── Optional extras ──────────────────────────────────────────────
st.subheader("Quick Filters")
filter_job = st.selectbox("Filter by Job", ["All"] + ["Job A", "Job B"])  # populate from DB
