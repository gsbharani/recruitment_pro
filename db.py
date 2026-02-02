# db.py
import psycopg2
import os

# Neon connection (replace with your Neon creds)
NEON_DSN = "postgresql://neondb_owner:npg_fSPgq8AVUd1v@ep-lucky-river-a1tltpq5-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"  # Update with actual DSN

def get_connection():
    return psycopg2.connect(NEON_DSN)

def save_candidate(data):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO candidates (
            id, recruiter_id, jd_id, resume_name, email, phone, experience, score, skills, 
            matched_skills, missing_skills, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data["id"], data["recruiter_id"], data["jd_id"], data["resume_name"], data["email"], 
        data["phone"], data["experience"], data["score"], data["skills"], data["matched_skills"], 
        data["missing_skills"], data.get("status", "uploaded")
    ))
    conn.commit()
    cur.close()
    return {"data": [data]}  # Mimic supabase response if needed
