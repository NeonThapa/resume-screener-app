# Quick Start

Follow these steps to get the resume screener running locally in less than ten minutes.

## 1. Clone and enter the project

```powershell
git clone <repo-url>
cd resume_screener
```

## 2. Set up Python

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## 3. Configure environment variables

Create a `.env` file beside `api.py`:

```text
OPENROUTER_API_KEY=sk-your-key
# Optional:
# OPENAI_BASE_URL=https://openrouter.ai/api/v1
# LLM_HTTP_REFERER=Local
# LLM_APP_TITLE=Resume Screener
```

If you plan to process image-only PDFs install Tesseract + Poppler and expose them via `TESSERACT_CMD` / `POPPLER_PATH`.

## 4. Launch the backend

```powershell
uvicorn api:app --reload
```

The API listens on `http://127.0.0.1:8000`.

## 5. Launch the frontend

```powershell
cd frontend
npm install
npm start
```

Open `http://localhost:3000` in your browser.

## 6. Upload

1. Upload the target job description (PDF/DOCX/TXT).
2. Upload resumes (PDF/DOCX). Large batches are handled sequentially; the banner will remind you to take a break while the LLM works.
3. Inspect the ranked list. Duplicates are automatically detected and down-ranked.

## 7. Stopping

Use `Ctrl+C` in each terminal to stop the dev servers. Deactivate the virtual environment with `deactivate`.
