# Developer Guide

This document is intentionally long. Read it sequentially the first time so you understand every moving part before attempting changes. Each section builds on the previous one: start with the runtime/dependency expectations, then dive into backend orchestration, LLM integration, parsing, frontend flows, heuristics, and finally operational practices.

---

## 0. Bird’s-eye view

**Goal:** Accept a JD + several resumes, parse them, invoke an LLM to compare resumes to the JD, enrich the response with deterministic checks (skills, experience, duplicates), and serve ranked results with detailed explanations.

**High-level pipeline**

```
React UI ──► POST /analyze/ ──► FastAPI orchestrator ──► Parser & JD summariser
                                         │
                                         └─► For each resume:
                                             ├─ text extraction (fallback to PDF base64)
                                             ├─ duplicate fingerprint detection
                                             └─ analyze_one_resume (LLM + guardrails)
                                        ◄── ranked response + JD metadata
```

All long-running work happens inside the POST handler; no database or queue is used. The in-memory `PROGRESS_REGISTRY` allows the frontend to poll a simple endpoint while the LLM runs.

---

## 1. Environment & Dependencies

### 1.1 System packages

| Dependency | Why we need it | Installation tips |
|------------|----------------|-------------------|
| Python 3.10+ | Backend runtime (tested 3.11/3.12). | On Windows, use the official installer and tick "Add to PATH". |
| Node 18+ | CRA dev server and build tooling. | `nvm install 18 && nvm use 18` keeps versions tidy. |
| Poppler | PDF rasterization for OCR fallback (`pdf2image`). | Download binaries, set `POPPLER_PATH` if not in PATH. |
| Tesseract | OCR engine used by `pytesseract`. | Install UB Mannheim build, set `TESSERACT_CMD` if necessary. |

Without Poppler/Tesseract the code still works, but scanned PDFs may yield poor text.

### 1.2 Python packages (see `requirements.txt`)

Pinned versions guarantee reproducibility. Categories:

- **Web**: `fastapi`, `uvicorn[standard]`, `python-multipart`.
- **NLP**: `spacy`, `scikit-learn`. You must run `python -m spacy download en_core_web_sm` once.
- **Parsing**: `pymupdf`, `pdfminer.six`, `pdf2image`, `pytesseract`, `python-docx`, `pillow`.
- **Config**: `python-dotenv` to load `.env` at startup.
- **LLM**: `openrouter`, `openai`. We call OpenRouter’s minimax model through the OpenAI SDK by overriding `base_url`.

Virtual environment workflow:

```powershell
python -m venv venv
.\venvinsutil.exe  # (activate via .\venv\Scripts\activate on Windows)
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 1.3 Node packages

Under `frontend/`, run `npm install`. It’s a standard Create-React-App stack; no custom webpack config.

---

## 2. Backend Code Walkthrough

The backend consists of five core modules. Read them in this order: `api.py`, `ai_analyzer.py`, `parser.py`, `analyzer.py`, `skills.py`.

### 2.1 `api.py` – FastAPI Orchestrator

```python
import copy, hashlib, os, shutil, base64, time, uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from analyzer import summarize_jd
from parser import extract_text_from_file, parse_jd_sections
from skills import MASTER_SKILL_LIST
from ai_analyzer import ResumeLLMInput, analyze_one_resume
```

Key globals:

- `PROGRESS_REGISTRY: Dict[job_id, dict]` – holds current file name, processed count, totals, error, status timestamps for the polling endpoint.
- `PROGRESS_TTL_SECONDS` – default 300 seconds; old entries are purged to prevent memory leaks.

Helper functions:

1. `_purge_stale_progress()` – run at the top of each request to remove entries whose `updated_at` has exceeded the TTL.
2. `_clean_extracted_text(text)` – filters out parser errors (strings beginning with "Error:"); returns `""` so the fallback PDF path triggers.
3. `_fingerprint_text(text)` – SHA1 hash of cleaned resume text to detect duplicates.

#### `POST /analyze/`

Pseudo-flow with important details inline:

1. **Initial state**
   ```python
   job_token = job_id or str(uuid.uuid4())
   progress_entry = PROGRESS_REGISTRY[job_token] = {
       'current': '', 'processed': 0, 'total': len(resumes),
       'done': False, 'error': None, 'started_at': time.time(),
       'updated_at': time.time()
   }
   ```
   - The frontend includes `job_id` in the form data; if not provided, the backend creates one.
   - Progress entry is immediately available so the UI doesn’t see a 404.

2. **Read JD**
   - Store JD to `temp_uploads/` (directory created if missing).
   - Pass path to `extract_text_from_file`; result may be error text but never `None`.
   - `summarize_jd(jd_text, MASTER_SKILL_LIST)` returns a dataclass with `must_have_skills`, `nice_to_have_skills`, `domain_keywords`, `role_titles`, `min_years_experience`, etc.
   - `parse_jd_sections(jd_text)` splits the JD into sections keyed by headings (UPPERCASE heuristics).

3. **Resume loop**
   - For each resume: update `progress_entry['current'] = filename` and `processed = len(all_results)` before heavy work so the poll endpoint displays something immediately.
   - Extract text:
     ```python
     extracted_text_raw = extract_text_from_file(resume_path)
     clean_text = _clean_extracted_text(extracted_text_raw)
     if not clean_text:
         clean_text = "No text could be extracted..."
         resume_pdf_encoded = base64.b64encode(open(resume_path, "rb").read()).decode("ascii")[:120000]
     else:
         resume_pdf_encoded = ""
     ```
   - Duplicate detection: compute fingerprint of `clean_text`. If already seen, clone base result, subtract 10 points (capped at >=1), annotate `duplicate_of`, append to results, and skip LLM call.
   - Construct `ResumeLLMInput` with JD summary info, resume text, optional PDF, etc.
   - Call `analyze_one_resume` and handle fallback results (if dict missing, create default failure summary).
   - Append result to `all_results` and store in `seen_fingerprints` for future duplicates.

4. **Return**
   - Sort results descending by `final_score`, assign `rank = index + 1`.
   - Mark progress entry `done=True` and update `updated_at`.
   - Response includes `jd_profile` (must/nice/domain) for the frontend to display or for future use.

5. **Exception handling**
   - Any exception triggers `progress_entry['error'] = str(exc)` so the frontend can show the failure reason; the exception is re-raised so FastAPI returns HTTP 500.

#### `GET /progress/{job_id}`

This endpoint is intentionally simple. It returns the progress entry if present; otherwise a stub object representing “pending”. Once TTL hits, the entry disappears and clients can treat that as completion.

### 2.2 `ai_analyzer.py` – LLM Client and Guardrails

#### Environment & Model setup

- Loads `.env` at import time (`load_dotenv()`).
- `_default_client()` tries to instantiate the OpenAI client using `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`). Base URL defaults to `https://openrouter.ai/api/v1`.
- The default model is `minimax/minimax-m2:free`. Change it via `RESUME_LLM_MODEL` env var.

#### Prompt Template

```text
You are an expert technical recruiter...
Objectives (in priority order): quantify experience, align skills, summarise fit.
Must-have focus areas: {must_have_bullets}
Supporting focus areas: {nice_to_have_bullets}
Key domain terms: {domain_terms}
If resume text appears truncated AND a PDF payload is provided, decode it.
Return strict JSON, populate all keys.
JD text...
Resume text...
Base64 PDF payload...
```

Important properties:

- Provides both textual and binary (base64) representations of the resume when extraction failed.
- Emphasises must-have skills to force the LLM to reward/penalise accurately.
- JSON schema expected by the frontend includes `final_score`, `details` (various metrics and insight arrays).

#### `_prepare_resume_excerpt`

- Splits resume text on double newlines, categorises sections by the first line.
- Prioritises sections matching keywords (`experience`, `project`, `technical`, `skills`, etc.).
- Combines prioritised sections first, then remaining sections, truncated to 6000 characters to keep token usage manageable.

#### `_call_llm_with_retries`

- Makes the API call using `llm_client.chat.completions.create(**request_kwargs)`.
- If `_extract_json_from_response` fails (e.g., the model added commentary), logs a warning and retries once with an appended system message reminding it to respond with JSON only.
- After two attempts, re-raises the ValueError; this propagates back to the API, which stores the error in the candidate card.

#### `_normalise_llm_payload`

- Ensures the returned dict has every field expected by the UI.
- `defaults` dictionary includes nested structures for score breakdown, lists for skills/insights, etc.
- Coerces values to expected types (e.g., `int(round(float(value)))` for numbers, list-of-strings sanitisation, etc.).

#### `_apply_score_guards`

- Calculates keyword hits by scanning the resume text for each must-have/nice-to-have skill.
- Updates `core_skill_matches` and `support_skill_matches` with deterministic hits even if the LLM missed them.
- Computes `coverage_ratio = len(must_hits) / len(must_have_skills)` (safe when denominator 0).
- Adjusts final score: if `coverage_ratio == 0` or `calculated_years <= 0` or the summary contains alarming phrases ("insufficient data", etc.), clamps the final score to at most 5.
- Returns augmented payload ready for the UI.

### 2.3 `parser.py` – Document Extraction

- Conditional imports handle optional dependencies at runtime (PyMuPDF, pdfminer, pdf2image, pytesseract, python-docx). Missing libraries trigger clear error messages.
- `_configure_ocr_backends` tries multiple Windows paths for Tesseract/Poppler if env vars aren’t set.
- `_extract_pdf_text` tries PyMuPDF (text mode + block mode), pdfminer, and OCR sequentially. Logs warnings when extraction yields short output.
- `_normalize_text` handles bullet glyphs & ligatures, normalises line endings, collapses multi-blank lines, trims whitespace.
- `_extract_docx_text` just uses python-docx.
- `_extract_txt_text` reads as UTF-8.

### 2.4 `analyzer.py` & `skills.py`

- `skills.py` exports `MASTER_SKILL_LIST`, mapping canonical names to alias lists. Update this file to recognise new skills/technologies.
- `analyzer.py` builds spaCy `PhraseMatcher`s lazily (memoised). `summarize_jd` iterates line-by-line through the JD, classifying mentions as must-have or nice-to-have based on hints ("must", "preferred", etc.). Remaining nouns become domain keywords.

---

## 3. Frontend Code Walkthrough

The frontend lives under `frontend/src/`. Core files:

```
frontend/src/
├── App.js                         # Root component (state + API calls)
├── components/
│   ├── FileUpload.js              # JD/resume pickers
│   ├── ProgressBar.js             # Animated progress indicator
│   ├── ResultsList.js             # Maps results to cards
│   └── CandidateCard.js           # Per-candidate insight display
├── assets/                        # Logos/images
└── index.css, App.css             # Stylesheets
```

### 3.1 `App.js`

State variables:

- `jdFile`, `resumeFiles` – raw File objects.
- `resumeFileObjects` – mapping of filename → object URL for the “View Resume” button.
- `isLoading`, `statusMessage` – general loading state and rotating messages.
- `results`, `jdSections`, `progressInfo` – backend responses.
- `statusIntervalRef`, `progressIntervalRef` – timers used for rotating messages & polling.

Key functions:

- `handleAnalyze`:
  1. Validates both JD and at least one resume.
  2. Clears old results and sets initial message (“We’re priming the job description…”).
  3. Generates `job_id` (`crypto.randomUUID()` when available) and starts polling `/progress/job_id`.
  4. Builds `FormData` with `jd`, `resumes`, `job_id`, `mode`, and `engine`.
  5. `fetch`es the FastAPI endpoint, handles errors, updates results + sections, and stops polling.

- `handleReset`: clears state, aborts intervals.

Rendering summary:

1. Header with branding.
2. Upload panel with instructions, file inputs, CTA buttons, reminder about supported formats.
3. JD overview grid (max 6 sections) if available.
4. Results area:
   - If `isLoading`, render `<ProgressBar message={statusMessage} detail={progressDetail} />` (friendly text now static).
   - Else if `results` empty, show empty state message.
   - Else map to `<ResultsList>`.

### 3.2 `CandidateCard.js`

Props: `candidate` (result from backend) and `fileUrl` (object URL). Shows:

- Rank, filename, final score.
- AI summary, calculated experience (overall + recent <5 yrs), matched/missing skills.
- Duplicates show `engine_used === 'ai-duplicate'` and the duplicate message.
- Strengths, risks, recommendations, experience timeline, gaps, education, certifications, insights, etc. Most sections gracefully handle empty arrays.

---

## 4. Data Flow Recap

1. **Frontend** collects JD + resume files, posts to `/analyze/` with `job_id`.
2. **`api.py`** saves files, parses JD, summarises skills, iterates resumes.
3. For each resume: extract text → duplicate detection → build `ResumeLLMInput` → call `analyze_one_resume` → append result.
4. **`ai_analyzer.py`** prepares prompt (with fallback PDF), calls OpenRouter (retry if invalid JSON), normalises payload, applies guardrails.
5. Results returned, sorted, ranked. Frontend renders cards.
6. Progress polling stops automatically when `done=True`.

---

## 5. Heuristics & Guardrails in Detail

- **Must-have coverage**: deterministic substring search. If zero must-have skills detected → cap score at 5. The LLM still returns insights summarising why ("insufficient match").
- **Experience**: If the LLM’s `calculated_years` <= 0, clamp the score. Encourages the prompt to fill this number accurately.
- **Duplicate detection**: Candidate receives `engine_used='ai-duplicate'`, `duplicate_of` field, and score reduced by 10 (minimum 1) so duplicates sink in the ranking but remain visible.
- **PDF fallback**: When text extraction fails, the warning text plus base64 PDF ensures the LLM still has raw data. Prompt explicitly tells it to decode the payload when present.
- **Retry logic**: Minimmax occasionally wraps JSON in prose; `_call_llm_with_retries` restates the constraint and retries once before surfacing an error.

---

## 6. Extending the System

### 6.1 Add skill aliases

Update `skills.py`:

```python
MASTER_SKILL_LIST.setdefault("TypeScript", []).extend(["typescript", "ts"])
```

Restarting the backend rebuilds the spaCy `PhraseMatcher` with new aliases.

### 6.2 Tune heuristics

`_apply_score_guards` contains the clamps and keyword merges. Examples of modifications:

- Reward extra optional skills: `final_score += min(len(nice_hits) * 2, 10)`.
- Aggressively penalise duplicate resumes by subtracting more points or hiding them altogether.

### 6.3 Swap the LLM model

Set `RESUME_LLM_MODEL` in `.env` (e.g., `gpt-4o-mini`). Ensure the provider supports JSON responses; adjust `_call_llm_with_retries` if the new model requires more attempts or a different prompt structure.

### 6.4 Optimise parser

- Add more unicode replacements in `_normalize_text`. Vinod’s resume needed replacements for glyphs like `` and `
`.
- Introduce caching (dictionary keyed by `fingerprint`) if you anticipate repeated runs on the same resumes.
- Consider parallel extraction using `asyncio` or background tasks if batches become large.

---

## 7. Testing & Validation

1. **Smoke test**: run `uvicorn api:app --reload`, `npm start`, upload the regression pack (`JDs/JD- Sr. Full stack Developer.pdf` + sample resumes). Validate rankings match expectation.
2. **CLI checks**: `python -m compileall ai_analyzer.py api.py parser.py` catches syntax errors quickly.
3. **Manual diff**: Inspect backend logs. Each resume prints `Processing <filename> with LLM pipeline...`. Duplicates print `Duplicate resume detected`. Failing LLM responses log JSON extraction warnings.
4. **Performance**: Monitor LLM latency. Minimmax free tier is slower than paid models; keep prompts lean by pruning resume text (`_prepare_resume_excerpt`).

---

## 8. Troubleshooting Table

| Symptom | Diagnosis | Remedy |
|---------|-----------|--------|
| Score = 0 despite relevant experience | Must-have keywords missing or `calculated_years` <= 0 | Update `MASTER_SKILL_LIST`, refine prompt, or inspect resume text for extraction issues. |
| Progress endpoint returns 404 immediately | Job not yet registered or TTL expired | Wait a second and re-poll; increase `PROGRESS_TTL_SECONDS` if needed. |
| "LLM response did not contain a valid JSON object" | Model returned Markdown or commentary | `_call_llm_with_retries` already retries once; if persistent, shorten prompt or try a different model. |
| OCR extremely slow | pdf2image + pytesseract on multi-page docs | Install native Poppler, reduce DPI, or disable OCR for known text-based PDFs. |
| Render deployment fails | System packages missing | Add steps to install Poppler/Tesseract or choose a base image that already includes them. |

---

## 9. Deployment Checklist

1. **Environment variables**: `OPENROUTER_API_KEY`, optionally `OPENAI_BASE_URL`, `LLM_HTTP_REFERER`, `LLM_APP_TITLE`, `TESSERACT_CMD`, `POPPLER_PATH`.
2. **Server command**: `gunicorn -k uvicorn.workers.UvicornWorker api:app --timeout 120 --log-level info`.
3. **Static frontend**: `npm run build` and either ship via Render’s static site service or any CDN.
4. **Monitoring**: watch logs for LLM errors/duplicates; consider adding Sentry for exception tracking.
5. **Regression data**: keep anonymised JD/resume samples in the repo. Always run them before pushing to main.

---

## 10. FAQ & Design Choices

- **Why LLM + heuristics instead of pure rules?** Semantic understanding is crucial for nuanced JD/resume comparisons; heuristics provide safety nets.
- **Why pass the PDF base64?** Some Canva/Canva-like resumes defeat text extraction. Allowing the model to read the raw PDF avoids false negatives.
- **Can we run offline?** Yes, swap `analyze_one_resume` with a local model or a rule-based engine; the rest of the pipeline remains the same.
- **Can I extend progress polling?** `PROGRESS_REGISTRY` is in-memory; for multi-instance scaling replace it with Redis or a database.

---

## 11. Roadmap Ideas

1. Automated regression harness that runs a batch of JD/resume pairs and compares results to stored expectations.
2. Blend deterministic scores (coverage ratio, penalty weights) with LLM output for more consistent ranking.
3. Multi-tenant support: namespace `PROGRESS_REGISTRY` by user/session.
4. Caching layer keyed by `(JD fingerprint, resume fingerprint)` to skip repeated analysis.
5. Rich analytics dashboard summarising average coverage per JD, time to analyse, duplicate rates.
6. Optional on-prem model swap (Azure OpenAI, self-hosted Llama) for privacy-conscious deployments.

---

With this guide you should be able to:

- Explain exactly how a JD and resume move through the system.
- Trace any bug to the relevant module quickly (extraction, LLM, heuristics, frontend rendering).
- Onboard new teammates by pointing them to specific sections.
- Confidently modify prompts, heuristics, or UI knowing the downstream effects.

Happy hacking!
