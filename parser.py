# parser.py
import os
import re
import fitz  # The pymupdf library
import docx

def extract_text_from_file(file_path):
    """Extracts text from PDF, DOCX, or TXT files."""
    text = ""
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"
        
    if file_path.endswith(".pdf"):
        with fitz.open(file_path) as doc:
            for page in doc: text += page.get_text()
    elif file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        for para in doc.paragraphs: text += para.text + "\n"
    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    #cleaned_text = re.sub(r'[^a-zA-Z0-9-+.,\s]', '', text)
    return text # Print first 100 characters for debugging