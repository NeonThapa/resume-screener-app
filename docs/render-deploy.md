# Render Deployment Guide

Render is already wired to your Git repository, so every push triggers a fresh build. This guide walks through the exact settings and commands you should use, plus covers the common `blis` build failure you just encountered.

---

## 1. Prerequisites

- Render “Web Service” connected to your repo.
- Plan type: starter/free works, but make sure you have enough build minutes for spaCy downloads.
- Runtime: **set Python to 3.12**. Render currently defaults to 3.13, which doesn’t have prebuilt wheels for the `blis` dependency (spaCy requires it), leading to compilation errors like:
  ```
  error: subprocess-exited-with-error
  × pip subprocess to install build dependencies did not run successfully.
  ...
  Failed building wheel for blis
  ```

### How to pin Python 3.12 on Render

Render respects the environment variable `PYTHON_VERSION`. In the Render dashboard:
1. Open your service → **Environment** tab.
2. Add `PYTHON_VERSION` with value `3.12.6` (or any 3.12.x you prefer).
3. Save changes.

Alternatively, you can commit a `.python-version` file with `3.12.6`, but the env var is explicit and overrides defaults.

---

## 2. Build & Start Commands

Configure these under **Settings → Build & Deploy**:

- **Build Command**
  ```bash
  pip install --upgrade pip setuptools wheel
  pip install --prefer-binary -r requirements.txt
  python -m spacy download en_core_web_sm
  npm install --prefix frontend
  npm run build --prefix frontend
  ```
  Notes:
  - `--prefer-binary` encourages pip to use prebuilt wheels (useful for `blis`).
  - The spaCy model download happens during build so it’s present at runtime.
  - `npm run build` creates the production React bundle in `frontend/build/`.

- **Start Command**
  ```bash
  uvicorn api:app --host 0.0.0.0 --port 10000
  ```
  Render injects `PORT`, but for Web Services it defaults to 10000; you can use `$PORT` if you prefer dynamic binding:
  ```bash
  uvicorn api:app --host 0.0.0.0 --port $PORT
  ```

---

## 3. Static Frontend Delivery (Optional)

If you prefer a separate static site service:
1. Create another Render “Static Site”.
2. Point it to the same repository.
3. Set build command `npm install && npm run build --prefix frontend`.
4. Publish directory: `frontend/build`.
5. Configure CORS in `api.py` to include the static site’s domain.

Otherwise, keep the backend as a single Web Service and serve the React build via another CDN or host of your choice.

---

## 4. Environment Variables Recap

| Variable | Required | Purpose |
|----------|----------|---------|
| `PYTHON_VERSION` | ✅ | Force Python 3.12 to avoid compiling spaCy dependencies. |
| `OPENROUTER_API_KEY` | ✅ | Token for the minimax LLM on OpenRouter. |
| `OPENAI_BASE_URL` | optional | Override base URL if not using OpenRouter (default is already set). |
| `LLM_HTTP_REFERER`, `LLM_APP_TITLE` | optional | Metadata that OpenRouter displays on usage dashboards. |
| `TESSERACT_CMD`, `POPPLER_PATH` | optional | Paths to OCR binaries if you enable OCR fallbacks. |

Remember to mark secrets as “Private” in Render so they don’t show up in logs.

---

## 5. Handling the `blis` Build Failure

If you see the verbose gcc warnings ending with `Failed building wheel for blis`, it means Render attempted to compile `blis` from source against Python 3.13 (or without the necessary C toolchain).

**Fix:** ensure `PYTHON_VERSION=3.12.x`. After setting the env var, redeploy. Render will download the prebuilt `blis` wheel and the build will succeed.

If you *must* stay on 3.13 in the future, wait until `blis` publishes wheels for that version or pre-install system packages (render doesn’t currently expose `apt-get` in build environments).

---

## 6. Suggested Deployment Workflow

1. `git status` → ensure clean working tree.
2. `git add` changed files; commit with a descriptive message.
3. `git push origin <branch>` (Render watches your main/deploy branch).
4. Render automatically detects the new commit and runs the build/start commands.
5. Monitor deployment logs (especially around the spaCy/blis install step).
6. Once live, run the regression pack (sample JD + resumes) to confirm behaviour.

---

## 7. Troubleshooting Checklist

| Symptom | Likely cause | Remedy |
|---------|--------------|--------|
| Build fails on `blis` | Python 3.13 or missing C toolchain | Set `PYTHON_VERSION=3.12.x`, redeploy. |
| Build timeouts | Large spaCy download or OCR dependencies | Ensure build command downloads the model; consider using Render Pro plan for longer timeouts. |
| Runtime 500 errors for all requests | Missing `.env` or incorrect API key | Check Render environment variables, restart service. |
| Frontend 404 for static assets | Static site not deployed / wrong publish directory | Confirm `frontend/build` exists and CORS allows the domain. |
| OCR fallback not working | Poppler/Tesseract missing | Install binaries locally, or disable OCR until you bundle them. |

---

## 8. Post-deployment Validation

After every successful deploy:
1. Upload the regression JD (`JDs/JD- Sr. Full stack Developer.pdf`) and sample resumes.  
2. Verify duplicates are down-ranked, misaligned HR resume gets near-zero score, correct candidate ranks highest.  
3. Check the Render logs for any “AI analysis failed” messages and address them if they recur.

---

With these settings Render deployments should become push-button simple. Adjust the build command if you add new dependencies (e.g., additional spaCy models) and keep the Python version pinned until the spaCy ecosystem ships wheels for newer interpreters. Happy deploying!
