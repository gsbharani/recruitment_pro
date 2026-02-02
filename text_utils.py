# text_utils.py
# (Updated slightly for consistency)
import pdfplumber
import docx
from pathlib import Path
import re

def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text

def extract_text(file_path):
    ext = Path(file_path).suffix.lower()
    text = ""
    if ext == ".pdf":
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    elif ext == ".docx":
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    else:
        raise ValueError("Unsupported file type: " + ext)
    return clean_text(text)

# ---------------- Skill Matching ----------------
def match_skills(resume_text: str, required_skills: list) -> tuple[list, list]:
    """
    Returns two lists: matched_skills, missing_skills
    """
    resume_text_lower = resume_text.lower()
    matched = []
    missing = []
    for skill in required_skills:
        if skill.lower() in resume_text_lower:
            matched.append(skill)
        else:
            missing.append(skill)
    return matched, missing
