# matcher.py
# (Unchanged)
from sentence_transformers import SentenceTransformer, util
model = SentenceTransformer("all-MiniLM-L6-v2")

def semantic_score(jd_text: str, resume_text: str) -> float:
    jd_emb = model.encode(jd_text, convert_to_tensor=True)
    resume_emb = model.encode(resume_text, convert_to_tensor=True)
    similarity = util.cos_sim(jd_emb, resume_emb).item()
    return round(similarity * 100, 2)

def skill_score(resume_text: str, required_skills: list) -> int:
    if not required_skills:
        return 0
    resume_text = resume_text.lower()
    matched = sum(1 for skill in required_skills if skill in resume_text)
    return int((matched / len(required_skills)) * 100)
