# storage.py
# Since Neon doesn't have storage, use local file system or AWS S3.
# For simplicity, here's local storage example.
# Assume a 'resumes' folder exists.

import os
from pathlib import Path

def upload_resume(file, filename):
    os.makedirs("resumes", exist_ok=True)
    file_path = Path("resumes") / filename
    with open(file_path, "wb") as f:
        f.write(file)
    return str(file_path)
