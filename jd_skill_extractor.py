# jd_skill_extractor.py
# (Unchanged)
import re
from collections import Counter

STOPWORDS = {
    "and", "or", "the", "to", "of", "in", "for", "with", "on",
    "a", "an", "is", "are", "will", "be", "as", "by", "from",
    "years", "experience", "knowledge", "skills", "ability", "you"
}

def extract_skills_from_jd(jd_text, top_n=15):
    text = jd_text.lower()
    # remove special characters
    text = re.sub(r"[^a-z\s]", " ", text)
    words = text.split()
    # filter words
    keywords = [
        w for w in words
        if len(w) > 2 and w not in STOPWORDS
    ]
    freq = Counter(keywords)
    # return most common meaningful words
    return [word for word, _ in freq.most_common(top_n)]
