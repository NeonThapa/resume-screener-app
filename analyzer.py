# analyzer.py
# This module contains the complete, rule-based analysis engine.
# It is fast, efficient, and has no external API dependencies.

import re
from datetime import datetime
import spacy
from spacy.matcher import PhraseMatcher

# --- Helper Functions ---

def extract_skills_from_jd(jd_text, skill_map):
    """
    Extracts required skills from the JD text using a skill dictionary (map).
    It looks for all aliases and returns the official skill name.
    """
    # Use a smaller, faster model for this specific task
    nlp = spacy.load("en_core_web_sm")
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    
    alias_to_official_map = {}
    for official_name, aliases in skill_map.items():
        # Create patterns for each alias
        skill_patterns = [nlp(alias) for alias in aliases]
        matcher.add(official_name, skill_patterns)
        # Map each alias back to its official name
        for alias in aliases:
            alias_to_official_map[alias.lower()] = official_name

    doc = nlp(jd_text)
    matches = matcher(doc)
    
    found_skills = set()
    for match_id, start, end in matches:
        # Get the matched text
        matched_text = doc[start:end].text.lower()
        # Find the official skill name from our reverse map
        official_name = alias_to_official_map.get(matched_text, nlp.vocab.strings[match_id])
        found_skills.add(official_name)
        
    return list(found_skills)

def split_resume_into_sections(resume_text):
    """Splits the resume text into a dictionary of sections."""
    sections = {}
    resume_text_lower = resume_text.lower()
    SECTION_KEYWORDS = {
        'experience': ['professional experience', 'work experience', 'employment history', 'job history', 'career'],
        'education': ['education', 'academic background', 'academic qualifications'],
        'skills': ['skills', 'technical skills', 'proficiencies'],
        'projects': ['projects', 'personal projects', 'academic projects', 'kaggle competition'],
    }
    found_sections_indices = []
    for clean_name, keywords in SECTION_KEYWORDS.items():
        for keyword in keywords:
            # Look for the keyword at the beginning of a line, allowing for whitespace
            for match in re.finditer(r'^\s*' + re.escape(keyword), resume_text_lower, re.MULTILINE):
                found_sections_indices.append((match.start(), clean_name))
                break # Move to the next section type once one keyword is found
    
    found_sections_indices.sort()
    
    for i, (start_index, section_name) in enumerate(found_sections_indices):
        # The section ends where the next one begins, or at the end of the document
        end_index = found_sections_indices[i+1][0] if i + 1 < len(found_sections_indices) else len(resume_text)
        section_text = resume_text[start_index:end_index].strip()
        # Append content if a section type (like 'projects') appears multiple times
        sections[section_name] = sections.get(section_name, "") + "\n\n" + section_text
        
    return sections

def calculate_experience_years(section_text):
    """Calculates total years of experience from a text block."""
    if not section_text:
        return 0.0
    total_months = 0
    today = datetime.now()
    # This robust regex handles "Month YYYY", "YYYY", and separators like '-', '–', or 'to'
    date_pattern = r'(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(\d{4})\s*[-–to]+\s*(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(\d{4}|Present)'
    matches = re.finditer(date_pattern, section_text, re.IGNORECASE)
    for match in matches:
        start_month_str, start_year_str, end_month_str, end_year_str = match.groups()
        start_year = int(start_year_str)
        # Default to January if no month is found
        start_month = datetime.strptime(start_month_str, '%b').month if start_month_str else 1
        start_date = datetime(start_year, start_month, 1)
        
        if 'present' in end_year_str.lower():
            end_date = today
        else:
            end_year = int(end_year_str)
            # Default to December if no month is found
            end_month = datetime.strptime(end_month_str, '%b').month if end_month_str else 12
            end_date = datetime(end_year, end_month, 1)
            
        # Calculate the duration in months, adding 1 to be inclusive
        duration_in_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1
        total_months += duration_in_months
        
    return round(total_months / 12, 1)

def calculate_skill_relevance(text, required_skills, skill_map):
    """Calculates a holistic skill match score from a given block of text."""
    if not required_skills or not text: return 0.0, []
    
    # This function is self-contained to ensure it has its own NLP objects
    nlp = spacy.load("en_core_web_sm")
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    alias_to_official_map = {alias.lower(): official for official, aliases in skill_map.items() for alias in aliases}
    
    for official_name, aliases in skill_map.items():
        skill_patterns = [nlp(alias) for alias in aliases]
        matcher.add(official_name, skill_patterns)

    doc = nlp(text)
    matches = matcher(doc)
    
    found_skills = {alias_to_official_map.get(doc[start:end].text.lower(), nlp.vocab.strings[match_id]) for match_id, start, end in matches}
    matched_official_skills = found_skills.intersection(set(required_skills))
    
    relevance_score = len(matched_official_skills) / len(required_skills)
    return relevance_score, list(matched_official_skills)

def calculate_project_impact(text, required_skills, skill_map):
    """Finds and scores project-like sentences within a block of text."""
    if not text: return 0.0
    
    # A more comprehensive list of action verbs suggesting a project
    project_keywords = ['developed', 'created', 'led', 'managed', 'architected', 'implemented', 'designed', 'built', 'deployed', 'optimized', 'engineered', 'launched']
    
    # Split the text into sentences for more granular analysis
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    project_sentences = [s for s in sentences if any(keyword in s.lower() for keyword in project_keywords)]
    
    if not project_sentences: return 0.0
    
    total_relevance = 0
    for sentence in project_sentences:
        # Calculate the relevance of each project-like sentence
        relevance, _ = calculate_skill_relevance(sentence, required_skills, skill_map)
        total_relevance += relevance
        
    # Return the average relevance across all found project sentences
    return total_relevance / len(project_sentences)


# --- Main Pipeline Function (FINAL HIERARCHICAL MODEL) ---
def analyze_one_resume(resume_text, jd_text, job_required_skills, skill_map):
    """
    Runs the full rule-based analysis pipeline on a single resume and returns a detailed dictionary.
    Note: The jd_text is passed for potential future use (like TF-IDF) but is not used in the final score.
    """
    extracted_sections = split_resume_into_sections(resume_text)
    
    # Score A: Overall Skill Match (40% weight)
    overall_skill_score, matched_skills = calculate_skill_relevance(resume_text, job_required_skills, skill_map)
    
    # Score B: Work Experience Duration (40% weight)
    experience_section_text = extracted_sections.get('experience', '')
    experience_years = calculate_experience_years(experience_section_text)
    duration_score = min(experience_years / 5.0, 1.0) # Normalize to a 0-1 scale, capped at 5 years
    
    # Score C: Hierarchical Project Impact (20% weight)
    project_score_exp = calculate_project_impact(experience_section_text, job_required_skills, skill_map)
    project_section_text = extracted_sections.get('projects', '')
    project_score_proj = calculate_project_impact(project_section_text, job_required_skills, skill_map)
    education_section_text = extracted_sections.get('education', '')
    project_score_edu = calculate_project_impact(education_section_text, job_required_skills, skill_map)
    
    # Apply weights to each project score based on its importance
    weighted_project_score = (project_score_exp * 1.0) + (project_score_proj * 0.75) + (project_score_edu * 0.5)
    # Cap the total project score at 100% to keep it normalized
    final_project_score = min(weighted_project_score, 1.0)

    # Final Weighted Score Calculation
    final_score = (overall_skill_score * 0.4) + \
                  (duration_score * 0.4) + \
                  (final_project_score * 0.2)
                  
    missing_skills = [skill for skill in job_required_skills if skill not in matched_skills]
    
    # Return the final, detailed dictionary for the frontend
    return {
        "final_score": round(final_score * 100, 2),
        "details": {
            "overall_skill_score": round(overall_skill_score * 100, 1),
            "experience_score": round(duration_score * 100, 1),
            "project_score": round(final_project_score * 100, 1),
            "calculated_years": experience_years,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills
        }
    }