# AI-Powered Resume Screening Application

This is a full-stack web application that leverages a rule-based NLP engine and an optional Generative AI backend to analyze and rank resumes against a given job description.

## Features

- **Dynamic JD Parsing:** Upload any job description (.pdf, .docx) to dynamically extract a list of required skills.
- **Multi-Resume Analysis:** Upload multiple resumes at once for batch processing.
- **Weighted Scoring Model:** Ranks candidates based on a sophisticated, multi-factor scoring model.
- **Interactive UI:** A clean, modern React frontend for uploading files and viewing ranked results.
- **Detailed Breakdown:** Click on any candidate to see a detailed analysis, including matched skills, missing skills, and a score breakdown.
- **Dual Analyzer Backend:** Features both a fast, cost-effective rule-based engine and a powerful Generative AI engine using Hugging Face APIs.

## Tech Stack

- **Backend:** Python, FastAPI, spaCy (for NLP), PyMuPDF (for parsing).
- **Frontend:** React, JavaScript, CSS.
- **Deployment:** Designed for Render (Web Service + Static Site).

## How to Run Locally

### 1. Backend Setup

```bash
# Navigate to the project root
cd resume_screener

# Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download the spaCy model
python -m spacy download en_core_web_sm

# Add your API keys to a .env file
# (Create a .env file and add HUGGING_FACE_HUB_TOKEN="hf_...")

# Start the server
uvicorn api:app --reload