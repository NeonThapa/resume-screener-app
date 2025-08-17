import os
import json
from dotenv import load_dotenv
# --- CHANGE: Use the OpenAI SDK import ---
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# --- 1. Configure the OpenRouter Client using OpenAI SDK ---
try:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    # --- CHANGE: Initialize with OpenAI class, base_url for OpenRouter, and optional headers ---
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        # Optional: Add these headers to identify your app (helps with rankings on OpenRouter site)
        default_headers={
            "HTTP-Referer": "Local",  # e.g., your website or app URL
            "X-Title": "Resume Screener"        # e.g., "Resume Screener"
        }
    )
    
    # We will use a powerful free model available on OpenRouter
    MODEL_NAME = "tngtech/deepseek-r1t2-chimera:free" 
    print(f"AI Analyzer: OpenRouter client initialized successfully for model {MODEL_NAME}.")
except Exception as e:
    print(f"AI Analyzer: FAILED to initialize OpenRouter client: {e}")
    client = None

# --- 2. The Main AI Analysis Function ---
def analyze_one_resume(resume_text, jd_text, job_required_skills, skill_map):
    if not client:
        return {"error": "OpenRouter AI Client not initialized. Check API Key."}

    # --- 3. Prompt Engineering ---
    # CHANGE: Include jd_text in the prompt, instruct to consider experience, skills, education.
    # Also specify output types to ensure numbers are integers (not strings).
    prompt = f"""
You are an expert HR AI assistant. Analyze the full resume text against the job description and required skills. 
Focus on:
- Calculating years of relevant experience based on job roles, dates, and relevance to the JD.
- Matching skills (exact and inferred) from the required skills list.
- Evaluating education qualifications for fit with the JD.

Return a JSON object with exactly these keys (no extras, no additional text, no explanations outside the JSON):
- "overall_summary": A concise string summary of the candidate's fit (2-3 sentences).
- "calculated_years": An integer for total years of relevant experience (0 if none).
- "matched_skills": A list of strings for skills from the required list that match the resume.
- "missing_skills": A list of strings for skills from the required list missing from the resume.
- "suitability_score": An integer score from 0 to 100 based on experience, skills, and education match.

Ensure the output is valid JSON: Use double quotes for strings, no trailing commas, escape any special characters like backslashes or quotes if they appear in strings, and output numbers as unquoted integers. Start and end with curly braces {{ }}.

**Job Description:**
{jd_text}

**Required Skills:**
{', '.join(job_required_skills)}

**Full Resume Text:**
---
{resume_text}
---
"""
    
    messages = [{"role": "user", "content": prompt}]
    
    print(f"Querying OpenRouter with full resume text...")
    try:
        # --- 4. Call the API using the standard OpenAI format ---
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            response_format={"type": "json_object"},
        )
        
        generated_text = response.choices[0].message.content
        print(f"Raw model output for debugging: {generated_text}")
        ai_analysis = json.loads(generated_text)

        # --- 5. Structure the response for the frontend ---
        # CHANGE: Explicitly convert to int to handle any string outputs safely.
        final_score = int(ai_analysis.get("suitability_score", 0))
        details = {
            "overall_skill_score": final_score,
            "experience_score": final_score,  # You could split this into separate scores if you enhance the prompt further.
            "project_score": final_score,     # Same here—currently using suitability as proxy.
            "calculated_years": int(ai_analysis.get("calculated_years", 0)),
            "matched_skills": ai_analysis.get("matched_skills", []),
            "missing_skills": ai_analysis.get("missing_skills", []),
            "ai_summary": ai_analysis.get("overall_summary", "No summary generated.")
        }

        return {
            "final_score": final_score,
            "details": details
        }

    except Exception as e:
        print(f"An error occurred during the OpenRouter AI analysis: {e}")
        return {
            "final_score": 0,
            "details": { "ai_summary": f"AI API call failed: {e}" }
        }