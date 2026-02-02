# resume_parser.py
# (Unchanged)
import re
import pdfplumber

def extract_text(path):
    with pdfplumber.open(path) as pdf:
        return " ".join(page.extract_text() or "" for page in pdf.pages)

def parse_resume(path, skills_list=None):
    text = extract_text(path).lower()
    email = re.search(r"[\w.-]+@[\w.-]+\.\w+", text)
    phone = re.search(r"(\+91)?[6-9]\d{9}", text)
    found_skills = []
    if skills_list:
        found_skills = [s for s in skills_list if s.lower() in text]
    exp_match = re.search(r"(\d+)\+?\s*years", text)
    experience = int(exp_match.group(1)) if exp_match else 0
    return {
        "email": email.group(0) if email else None,
        "mobile": phone.group(0) if phone else None,
        "skills_found": found_skills,
        "experience": experience
    }
