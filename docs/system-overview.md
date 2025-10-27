# System Overview

This document explains the architecture and data flow of the resume screener so new contributors can make informed changes.

## High-level pipeline

1. **Upload** – The React frontend posts a job description (`jd`) and one or more `resumes` to `POST /analyze/`.
2. **Staging** – `api.py` stores the uploads in `temp_uploads/` and registers a progress token so the UI can poll `/progress/<job_id>`.
3. **JD processing**
   - `parser.extract_text_from_file` reads the JD (PDF/DOCX/TXT) using PyMuPDF → pdfminer → OCR fallbacks.
   - `analyzer.summarize_jd` converts the JD into must-have skills, nice-to-have skills, and domain keywords.
   - Sections are captured via `parse_jd_sections` for presentation on the frontend.
4. **Resume processing (per file)**
   - Text extraction mirrors the JD pipeline. If extraction fails, the raw PDF is base64 encoded and passed to the LLM.
   - A duplicate fingerprint (SHA-1 of cleaned text) prevents the same resume from dominating rankings.
   - `ai_analyzer.analyze_one_resume` builds the LLM prompt with:
     - JD summary data (must-have/nice-to-have/domain terms).
     - Trimmed resume text (most relevant sections first).
     - Optional base64 PDF payload.
   - The LLM (via OpenRouter’s minimax/minimax-m2:free) returns JSON that is normalised and then post-processed:
     - Deterministic keyword hits merge back into the response.
     - Scores are clamped when core requirements are missing or no experience is detected.
5. **Response**
   - Results are sorted by score, ranked, and returned with JD metadata.
   - Progress entry is marked done and kept for a short TTL for the frontend to read a final state.

## Key modules

| File | Responsibility |
| ---- | -------------- |
| `api.py` | FastAPI endpoints, progress tracking, duplicate handling, LLM orchestration. |
| `ai_analyzer.py` | Prompt template, OpenRouter client, JSON normalisation, score guardrails. |
| `parser.py` | File extraction helpers (PDF/DOCX/TXT) with ligature and bullet normalisation. |
| `analyzer.py` | JD summarisation (skill detection, domain terms). |
| `skills.py` | Master skill list + aliases for JD analysis. |
| `frontend/src/*` | React SPA for uploads, progress UI, and candidate cards. |

## External dependencies

- **PyMuPDF (`pymupdf`)** – fast text extraction.
- **pdfminer.six** and **pdf2image + pytesseract** – fallbacks for tricky PDFs.
- **spaCy** – JD parsing, noun phrase extraction.
- **OpenRouter / OpenAI SDK** – access to minimax model.
- **scikit-learn** – retained for potential scoring enhancements (present in requirements).

System packages required for full PDF coverage:

| Package | Purpose | Notes |
| ------- | ------- | ----- |
| Poppler | PDF → image conversions (`pdf2image`) | Set `POPPLER_PATH` on Windows if installed in a non-standard path. |
| Tesseract OCR | OCR for scanned PDFs | Set `TESSERACT_CMD` if not on PATH. |

## Environment variables

Primary keys live in `.env` (loaded by `python-dotenv`):

- `OPENROUTER_API_KEY` (required) – token for OpenRouter.
- `OPENAI_BASE_URL` (optional) – defaults to `https://openrouter.ai/api/v1`.
- `LLM_HTTP_REFERER` / `LLM_APP_TITLE` (optional) – metadata OpenRouter uses for analytics.

Optional extraction variables:

- `TESSERACT_CMD` – path to `tesseract.exe`.
- `POPPLER_PATH` – directory containing `pdftoppm`/`pdftocairo`.

## Frontend notes

- Upload UI lives in `frontend/src/components/FileUpload.js`.
- Progress bar text is intentionally static (“take a break”) while `/progress/<job_id>` ensures polling stays alive until results are ready.
- Candidate cards highlight only relevant experience metrics; duplicates are tagged in `engine_used`.

## Testing & validation

- Run `python -m compileall ai_analyzer.py api.py parser.py` to catch syntax errors quickly.
- Manual regression: use the provided JD (`JDs/`) plus the sample resumes to verify:
  - Full-stack profiles outrank HR/social-sector resumes.
  - Duplicate resumes are detected and reduced in score.
  - PDF extraction handles Vinod’s CV (ligatures and table data).

## Deployment considerations

- Use `uvicorn` or `gunicorn` + `uvicorn.workers.UvicornWorker` behind a reverse proxy (NGINX, Caddy).
- Configure `.env` secrets via the hosting platform.
- Ensure Poppler/Tesseract binaries are installed on the server if OCR fallback is required.
- Build the frontend with `npm run build` and serve the static files (Render / Netlify / S3 + CloudFront).
