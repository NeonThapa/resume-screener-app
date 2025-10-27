# api.py (LLM-centric backend)
import copy
import hashlib
import os
import shutil
import base64
import time
import uuid
from typing import Dict, List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from analyzer import summarize_jd
from parser import extract_text_from_file, parse_jd_sections
from skills import MASTER_SKILL_LIST

try:
    from ai_analyzer import ResumeLLMInput, analyze_one_resume as ai_analyzer

    AI_ANALYZER_AVAILABLE = True
    print("--- AI Analyzer module imported successfully ---")
except Exception as exc:  # pragma: no cover - optional dependency
    ai_analyzer = None  # type: ignore
    ResumeLLMInput = None  # type: ignore
    AI_ANALYZER_AVAILABLE = False
    print(f"--- AI Analyzer unavailable: {exc} ---")


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # For local development
        "https://resume-screener-ui.onrender.com",  # For your live website
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROGRESS_REGISTRY: Dict[str, Dict[str, object]] = {}
PROGRESS_TTL_SECONDS = int(os.getenv("PROGRESS_TTL_SECONDS", "300"))


def _purge_stale_progress() -> None:
    if not PROGRESS_REGISTRY:
        return
    now = time.time()
    stale_ids = [
        key
        for key, meta in PROGRESS_REGISTRY.items()
        if now - float(meta.get("updated_at", now)) > PROGRESS_TTL_SECONDS
    ]
    for key in stale_ids:
        PROGRESS_REGISTRY.pop(key, None)


def _clean_extracted_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    if raw_text.startswith("Error:"):
        return ""
    return raw_text


def _fingerprint_text(text: str) -> str:
    normalized = text.encode("utf-8", "ignore")
    return hashlib.sha1(normalized).hexdigest()


@app.post("/analyze/")
async def analyze_resumes_endpoint(
    jd: UploadFile = File(...),
    resumes: List[UploadFile] = File(...),
    mode: str = Form("standard"),
    engine: str = Form("ai"),
    job_id: str = Form(None),
):
    if engine.lower() != "ai":
        print(f"Ignoring engine='{engine}'. LLM-only engine will be used.")

    _purge_stale_progress()

    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)

    job_token = job_id or str(uuid.uuid4())
    started_at = time.time()
    PROGRESS_REGISTRY[job_token] = {
        "current": "",
        "processed": 0,
        "total": len(resumes),
        "done": False,
        "error": None,
        "started_at": started_at,
        "updated_at": started_at,
    }

    try:
        jd_path = os.path.join(temp_dir, jd.filename)
        with open(jd_path, "wb") as buffer:
            shutil.copyfileobj(jd.file, buffer)

        resume_paths: List[str] = []
        for resume in resumes:
            path = os.path.join(temp_dir, resume.filename)
            with open(path, "wb") as buffer:
                shutil.copyfileobj(resume.file, buffer)
            resume_paths.append(path)

        jd_text_raw = extract_text_from_file(jd_path)
        jd_text = _clean_extracted_text(jd_text_raw) or "Job description text was unavailable."
        jd_sections = parse_jd_sections(jd_text)
        jd_summary = summarize_jd(jd_text, MASTER_SKILL_LIST)
        jd_profile = {
            "must_have_skills": jd_summary.must_have_skills,
            "nice_to_have_skills": jd_summary.nice_to_have_skills,
            "domain_keywords": jd_summary.domain_keywords,
        }

        all_results = []
        seen_fingerprints: Dict[str, Dict[str, object]] = {}
        progress_entry = PROGRESS_REGISTRY[job_token]
        progress_entry["total"] = len(resume_paths)
        progress_entry["updated_at"] = time.time()

        for resume_path in resume_paths:
            filename = os.path.basename(resume_path)
            print(f"Processing {filename} with LLM pipeline...")
            progress_entry["current"] = filename
            progress_entry["processed"] = len(all_results)
            progress_entry["updated_at"] = time.time()

            extracted_text_raw = extract_text_from_file(resume_path)
            clean_text = _clean_extracted_text(extracted_text_raw)
            if not clean_text:
                clean_text = (
                    "No text could be extracted from this resume file. "
                    "Provide a cautious summary noting the lack of readable content."
                )

            fingerprint = _fingerprint_text(clean_text)
            if fingerprint in seen_fingerprints:
                base = seen_fingerprints[fingerprint]
                duplicate_details = copy.deepcopy(base.get("details", {}))
                summary = duplicate_details.get("ai_summary", "") or "Duplicate resume detected."
                duplicate_details["ai_summary"] = summary + " Duplicate file detected; score reduced."
                duplicate_result = {
                    "filename": filename,
                    "final_score": max(1.0, float(base.get("final_score", 0)) - 10.0),
                    "details": duplicate_details,
                    "engine_used": "ai-duplicate",
                    "duplicate_of": base.get("filename"),
                }
                all_results.append(duplicate_result)
                progress_entry["processed"] = len(all_results)
                progress_entry["current"] = ""
                progress_entry["updated_at"] = time.time()
                continue

            if not AI_ANALYZER_AVAILABLE:
                fallback_details = {
                    "ai_summary": "AI analyzer module not available on the server.",
                }
                fallback_result = {
                    "filename": filename,
                    "final_score": 0,
                    "details": fallback_details,
                    "engine_used": "ai",
                }
                all_results.append(fallback_result)
                seen_fingerprints[fingerprint] = fallback_result
                progress_entry["processed"] = len(all_results)
                progress_entry["current"] = ""
                progress_entry["updated_at"] = time.time()
                continue

            resume_pdf_encoded = ""
            if clean_text.startswith("No text could be extracted"):
                try:
                    with open(resume_path, "rb") as pdf_handle:
                        raw_bytes = pdf_handle.read()
                    encoded = base64.b64encode(raw_bytes).decode("ascii")
                    resume_pdf_encoded = encoded[:120000]
                except Exception:
                    resume_pdf_encoded = ""

            resume_input = ResumeLLMInput(
                filename=filename,
                jd_text=jd_text,
                resume_text=clean_text,
                resume_pdf_base64=resume_pdf_encoded,
                must_have_skills=jd_summary.must_have_skills,
                nice_to_have_skills=jd_summary.nice_to_have_skills,
                jd_keywords=jd_summary.domain_keywords,
            )

            llm_result = ai_analyzer(resume_input=resume_input)

            if not isinstance(llm_result, dict):
                llm_result = {
                    "final_score": 0,
                    "details": {
                        "ai_summary": "Unexpected response from AI analyzer.",
                    },
                }

            final_score = llm_result.get("final_score", 0)
            try:
                final_score = float(final_score)
            except (TypeError, ValueError):
                final_score = 0.0

            details = llm_result.get("details") or {}

            result_entry = {
                "filename": filename,
                "final_score": final_score,
                "details": details,
                "engine_used": "ai",
            }
            all_results.append(result_entry)
            seen_fingerprints[fingerprint] = result_entry

            progress_entry["processed"] = len(all_results)
            progress_entry["current"] = ""
            progress_entry["updated_at"] = time.time()

        all_results.sort(key=lambda x: x["final_score"], reverse=True)
        for idx, result in enumerate(all_results, start=1):
            result["rank"] = idx

        progress_entry["current"] = ""
        progress_entry["processed"] = len(all_results)
        progress_entry["done"] = True
        progress_entry["updated_at"] = time.time()

        return {
            "results": all_results,
            "jd_sections": jd_sections,
            "jd_profile": jd_profile,
            "analysis_mode": "llm",
            "job_id": job_token,
        }
    except Exception as exc:
        entry = PROGRESS_REGISTRY.get(job_token)
        if entry is not None:
            entry["current"] = ""
            entry["error"] = str(exc)
            entry["done"] = True
            entry["updated_at"] = time.time()
        raise
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@app.get("/progress/{job_id}")
async def get_progress(job_id: str):
    _purge_stale_progress()
    progress = PROGRESS_REGISTRY.get(job_id)
    if not progress:
        return {
            "current": "",
            "processed": 0,
            "total": 0,
            "done": False,
            "error": None,
            "status": "pending",
        }
    return progress
