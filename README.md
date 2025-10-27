# AI-Powered Resume Screening Application

This project pairs a FastAPI backend with a React frontend to extract text from job descriptions and resumes, then hands that content to a large language model for scoring, ranking, and summarising each candidate. All resume scoring now flows through the LLM; no rule-based heuristics are used for the final score.

## Documentation index
- [Quick Start](docs/quickstart.md) – shortest path to running locally.
- [System Overview](docs/system-overview.md) – architecture, pipeline, and deployment details.

## Quick Start (condensed)

1. **Clone & enter the project**
   `powershell
   git clone <repo-url>
   cd resume_screener
   `
2. **Create/activate the virtual environment**
   `powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
   `
3. **Add your LLM credentials** - create .env in the project root:
   `	ext
   OPENROUTER_API_KEY=sk-...
   # Optional overrides:
   # OPENAI_BASE_URL=https://openrouter.ai/api/v1
   # LLM_HTTP_REFERER=Local
   # LLM_APP_TITLE=Resume Screener
   `
4. **Run the FastAPI server**
   `powershell
   uvicorn api:app --reload
   `
5. **Start the React frontend in another terminal**
   `powershell
   cd frontend
   npm install
   npm start
   `
6. **Visit** http://localhost:3000 and upload a JD plus one or more resumes. The UI shows a “take a break” message while the LLM processes each file; progress is streamed via /progress/<job_id>.

## Complete Setup & Handover Notes

### Backend Stack
- Python 3.10+ (tested on 3.11/3.12)
- FastAPI + Uvicorn
- Text extraction: PyMuPDF (pymupdf), pdfminer.six, python-docx, optional pdf2image/pytesseract for OCR fallbacks
- spaCy en_core_web_sm for JD parsing
- OpenAI-compatible SDK (via OpenRouter) for LLM scoring

### Frontend Stack
- Node 18+ recommended (Create React App)
- npm for dependency management

### Environment Variables
Place these in .env beside pi.py:

| Variable | Required | Purpose |
| --- | --- | --- |
| OPENROUTER_API_KEY | required | API key for OpenRouter-hosted models. |
| OPENAI_API_KEY | optional | Direct OpenAI key if not using OpenRouter. |
| OPENAI_BASE_URL | optional | Override base URL (defaults to OpenRouter). |
| LLM_HTTP_REFERER, LLM_APP_TITLE | optional | Helpful metadata for OpenRouter dashboards. |

Set TESSERACT_CMD and POPPLER_PATH if OCR binaries are installed in non-default locations.

### Running the stack
1. Activate the Python virtual environment.
2. pip install -r requirements.txt and install the spaCy model (python -m spacy download en_core_web_sm).
3. uvicorn api:app --reload (or use a process manager such as gunicorn -k uvicorn.workers.UvicornWorker for production). The backend exposes:
   - POST /analyze/ - accepts a JD and one or more resumes (job_id optional). Each resume is parsed locally, then scored by the LLM.
   - GET /progress/{job_id} - returns {current, processed, total, done} so the UI can show live progress.
4. In rontend/, run 
pm install then 
pm start. For production builds, use 
pm run build and host the uild/ directory on a static host.

### Operational Notes
- Large resume batches will take time; the UI now surfaces an encouragement message while the LLM works.
- If the extractor cannot read a resume, the backend now forwards the base64 PDF to the LLM so it can attempt a direct read before scoring.
- PDF extraction runs a fast PyMuPDF pass, falls back to block-level reconstruction, then pdfminer/OCR to maximise readable output.
- Duplicated resumes are fingerprinted and automatically down-ranked to prevent result clutter.
- Progress updates remain available for a few minutes after completion so polling clients can safely retrieve the final counts.
- The backend cleans up uploaded files after each request. Progress entries are released once the analysis completes (the frontend treats a 404 from /progress/<job_id> as "job finished").  
- Run python -m compileall ai_analyzer.py api.py parser.py to catch syntax errors quickly after edits.

### Deployment Tips
- Provision the OPENROUTER_API_KEY (or OpenAI keys) via your hosting provider's secret manager.
- Ensure system packages required by pdf2image/pytesseract (Poppler, Tesseract) are installed if you expect to process image-only PDFs.
- Serve the FastAPI app behind HTTPS with a reverse proxy (NGINX, Caddy, etc.) and configure the frontend's REACT_APP_API_URL to match the deployed backend URL.

With these steps the next maintainer can get the project running locally in minutes and has a full reference for production setup. Happy screening!
