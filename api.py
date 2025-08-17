# api.py (Final Corrected Version)
import os, shutil
from typing import List
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from parser import extract_text_from_file
from skills import MASTER_SKILL_LIST

# --- CHOOSE YOUR ANALYZER ---
# Set USE_AI_ANALYZER to True to use the Hugging Face API,
# or False to use the fast, local, rule-based engine.
USE_AI_ANALYZER = True # <-- Let's start by testing the fast, free one first.

# --- THIS IS THE CRITICAL FIX ---
# The import logic is now corrected to look in the right files.
if USE_AI_ANALYZER:
    from ai_analyzer import analyze_one_resume # <-- Imports from ai_analyzer.py
    print("--- AI Analyzer is ACTIVE ---")
else:
    from analyzer import analyze_one_resume # <-- Imports from analyzer.py
    print("--- Rule-Based Analyzer is ACTIVE ---")
# --- END OF FIX ---

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", # For local development
        "https://resume-screener-ui.onrender.com" # For your live website
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyze/")
async def analyze_resumes_endpoint(jd: UploadFile = File(...), resumes: List[UploadFile] = File(...)):
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    try:
        jd_path = os.path.join(temp_dir, jd.filename)
        with open(jd_path, "wb") as buffer: shutil.copyfileobj(jd.file, buffer)
        
        resume_paths = []
        for resume in resumes:
            path = os.path.join(temp_dir, resume.filename)
            with open(path, "wb") as buffer: shutil.copyfileobj(resume.file, buffer)
            resume_paths.append(path)
        
        print("--- Starting Backend Analysis ---")
        # We need to import the JD skill extractor from the correct module
        from analyzer import extract_skills_from_jd
        jd_text = extract_text_from_file(jd_path)
        job_required_skills = extract_skills_from_jd(jd_text, MASTER_SKILL_LIST)
        
        all_results = []
        for path in resume_paths:
            print(f"Processing {os.path.basename(path)}...")
            resume_text = extract_text_from_file(path)
            if resume_text:
                # This will now correctly call either the AI or the rule-based function
                analysis_dict = analyze_one_resume(resume_text, jd_text, job_required_skills, MASTER_SKILL_LIST)
                analysis_dict['filename'] = os.path.basename(path)
                all_results.append(analysis_dict)
        
        all_results.sort(key=lambda x: x["final_score"], reverse=True)
        for i, result in enumerate(all_results): result['rank'] = i + 1
        
        return {"results": all_results}
    finally:
        shutil.rmtree(temp_dir)