"""Rule-based resume analysis engine with enriched insights."""

import re
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Set

import spacy
from spacy.matcher import PhraseMatcher

# --- Constants & Regex helpers -------------------------------------------------

MONTH_LOOKUP: Dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

PRESENT_TERMS = {
    "present",
    "current",
    "now",
    "today",
    "tilldate",
    "tillnow",
    "tilltoday",
    "till-date",
    "till-now",
    "till-today",
}

MONTH_PATTERN = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
SEPARATOR_PATTERN = r"\s*(?:[-\u2010-\u2015\u2212]+|to|through|till|until|&|~)\s*"
PRESENT_PATTERN = r"(?:Present|Current|Now|Today|Till\s*Date|Till\s*Now|Till\s*Today)"

NUMERIC_RANGE_RE = re.compile(
    rf"(?P<start_month_num>\d{{1,2}})\s*[/\.\-]\s*(?P<start_year>\d{{2,4}}){SEPARATOR_PATTERN}"
    rf"(?:(?P<end_month_num>\d{{1,2}})\s*[/\.\-]\s*(?P<end_year>\d{{2,4}})|(?P<end_marker>{PRESENT_PATTERN}))",
    re.IGNORECASE,
)

MONTH_YEAR_RANGE_RE = re.compile(
    rf"(?P<start_month>{MONTH_PATTERN})[\s\.,'\u2010-\u2015-]*(?P<start_year>\d{{2,4}}){SEPARATOR_PATTERN}"
    rf"(?:(?P<end_month>{MONTH_PATTERN})[\s\.,'\u2010-\u2015-]*(?P<end_year>\d{{2,4}})|(?P<end_marker>{PRESENT_PATTERN}))",
    re.IGNORECASE,
)

YEAR_ONLY_RANGE_RE = re.compile(
    rf"\b(?P<start_year>(?:19|20)\d{{2}})\b{SEPARATOR_PATTERN}"
    rf"(?:(?P<end_year>(?:19|20)\d{{2}})|(?P<end_marker>{PRESENT_PATTERN}))",
    re.IGNORECASE,
)

COMPANY_HINT_REGEX = re.compile(
    r"\b(technolog(?:y|ies)|solutions?|labs?|systems?|limited|ltd|inc|corp(?:oration)?|consult(?:ing|ants)?|software|services|company|co\.?|global|digital|studio|group|pvt|private|llc|llp|enterprises?|industries|networks|partners|associates|holdings?)\b",
    re.IGNORECASE,
)
JOB_TITLE_HINT_REGEX = re.compile(
    r"\b(engineer|developer|manager|lead|consultant|intern|architect|analyst|officer|executive|specialist|associate|director|programmer|designer|scientist|administrator|supervisor|coordinator|trainer|advisor|technician|support|assistant)\b",
    re.IGNORECASE,
)
LINE_SPLIT_REGEX = re.compile(r"[|??\u2022]+")
SECTION_TRIM_CHARS = " -\t\u2022\u2023\u25cf\u25e6"

EDUCATION_KEYWORDS = {
    "university",
    "college",
    "institute",
    "school",
    "academy",
    "polytechnic",
    "faculty",
    "curriculum",
    "bachelor",
    "master",
    "degree",
    "psychology",
    "psy",
    "biology",
    "chemistry",
    "biochemistry",
    "major",
    "bechelors",
    "b.sc",
    "b.s.",
    "b.e",
    "mba",
    "pgdm",
    "diploma",
    "cum laude",
    "student",
    "semester",
    "gpa",
    "grade",
    "course",
}

CERTIFICATION_KEYWORDS = {
    "cert",
    "license",
    "credential",
    "foundation",
    "practitioner",
    "exam",
    "accredit",
    "pmp",
    "scrum",
    "safe",
    "azure",
    "aws",
    "gcp",
    "oracle",
    "sap",
    "microsoft",
    "google",
    "cisco",
    "salesforce",
    "itil",
    "six sigma",
    "black belt",
    "green belt",
    "eligibility",
}

CONTACT_PATTERN = re.compile(
    r"(@|https?://|www\.|linkedin\.com|github\.com|\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b)",
    re.IGNORECASE,
)

NON_COMPANY_TERMS = {
    "contact",
    "skills",
    "skill",
    "development",
    "initiative",
    "community",
    "india",
    "youth",
    "entrepreneurship",
    "skill",
    "development",
    "initiative",
    "community",
    "india",
    "youth",
    "entrepreneurship",
    "skill",
    "development",
    "initiative",
    "community",
    "india",
    "youth",
    "entrepreneurship",
    "skill",
    "development",
    "initiative",
    "community",
    "india",
    "youth",
    "entrepreneurship",
    "education",
    "summary",
    "profile",
    "objective",
    "goal",
    "courses",
    "course",
    "curriculum",
    "module",
    "semester",
    "term",
    "gpa",
    "grade",
    "linkedin",
    "email",
    "gmail",
    "hotmail",
    "phone",
    "mobile",
    "address",
    "website",
    "portfolio",
    "university",
    "college",
    "school",
    "academy",
    "institute",
    "foundation",
    "chapter",
    "organization",
    "volunteer",
    "honors",
    "awards",
    "award",
    "activities",
    "seminar",
    "seminars",
    "psu",
    "psy",
    "biochemistry",
    "eligibility",
}

NON_EXPERIENCE_KEYWORDS = {
    "curriculum vitae",
    "course syllabus",
    "course outline",
    "gpa",
    "semester",
    "term",
    "module",
    "lab",
    "laboratory",
    "assignment",
    "hobby",
    "hobbies",
    "interest",
    "interests",
    "award",
    "awards",
    "honor",
    "honors",
    "honour",
    "honours",
}
CAREER_KEYWORDS = {
    "manager",
    "developer",
    "engineer",
    "consultant",
    "intern",
    "assistant",
    "specialist",
    "lead",
    "supervisor",
    "coordinator",
    "director",
    "officer",
    "analyst",
    "advisor",
    "recruiter",
    "human resources",
    "hr",
    "administrator",
    "trainer",
    "associate",
    "executive",
    "agent",
    "technician",
}

JD_MUST_HAVE_HINTS = ("must", "mandatory", "require", "should have", "need to have", "minimum")
JD_NICE_HINTS = ("preferred", "nice to have", "plus", "bonus", "advantage", "good to have")

DOMAIN_STOPWORDS = {
    "the",
    "and",
    "with",
    "for",
    "in",
    "of",
    "to",
    "on",
    "a",
    "an",
    "by",
    "or",
    "as",
    "per",
    "across",
    "using",
    "ability",
    "experience",
    "including",
    "responsible",
    "responsibilities",
    "skills",
    "skill",
    "development",
    "initiative",
    "community",
    "india",
    "youth",
    "entrepreneurship",
    "requirements",
    "manager",
    "management",
    "team",
    "teams",
    "stakeholder",
    "stakeholders",
    "lead",
    "leading",
    "deliver",
    "delivery",
    "ensure",
    "ensuring",
    "work",
    "working",
    "drive",
    "driving",
    "support",
    "supporting",
}

ROLE_KEYWORDS = {"manager", "lead", "head", "director", "specialist", "consultant", "program", "project"}


@dataclass
class JDSummary:
    must_have_skills: List[str] = field(default_factory=list)
    nice_to_have_skills: List[str] = field(default_factory=list)
    domain_keywords: List[str] = field(default_factory=list)
    role_titles: List[str] = field(default_factory=list)
    min_years_experience: Optional[float] = None


@dataclass
class ResumeSignals:
    matched_must_have: List[str] = field(default_factory=list)
    matched_nice_to_have: List[str] = field(default_factory=list)
    matched_extra_skills: List[str] = field(default_factory=list)
    domain_hits: List[str] = field(default_factory=list)
    role_hits: List[str] = field(default_factory=list)
    experience_years: float = 0.0
    recent_years: float = 0.0
    segments: List[Dict[str, object]] = field(default_factory=list)
    gaps: List[Dict[str, object]] = field(default_factory=list)
    used_fallback: bool = False


@dataclass
class ScoreBreakdown:
    overall: float
    skill_component: float
    experience_component: float
    domain_component: float
    role_component: float
    bonus_component: float
    penalties: List[str] = field(default_factory=list)
    must_have_ratio: float = 0.0
    nice_to_have_ratio: float = 0.0
    domain_ratio: float = 0.0
    role_ratio: float = 0.0
    experience_ratio: float = 0.0


_SKILL_MATCHER = None
_SKILL_MATCHER_NLP = None
_SKILL_ALIAS_MAP: Optional[Dict[str, str]] = None


def _ensure_skill_matcher(skill_map: Dict[str, List[str]]):
    global _SKILL_MATCHER, _SKILL_MATCHER_NLP, _SKILL_ALIAS_MAP
    if _SKILL_MATCHER is not None and _SKILL_MATCHER_NLP is not None and _SKILL_ALIAS_MAP is not None:
        return _SKILL_MATCHER_NLP, _SKILL_MATCHER, _SKILL_ALIAS_MAP

    nlp = _load_spacy_model()
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    alias_map: Dict[str, str] = {}
    for official_name, aliases in skill_map.items():
        patterns = [nlp.make_doc(alias) for alias in aliases]
        if patterns:
            matcher.add(official_name, patterns)
        for alias in aliases:
            alias_map[alias.lower()] = official_name
    _SKILL_MATCHER = matcher
    _SKILL_MATCHER_NLP = nlp
    _SKILL_ALIAS_MAP = alias_map
    return nlp, matcher, alias_map


def _match_skill_mentions(text: str, skill_map: Dict[str, List[str]]):
    if not text:
        return []
    nlp, matcher, alias_map = _ensure_skill_matcher(skill_map)
    doc = nlp(text)
    matches = matcher(doc)
    mentions = []
    seen_spans = set()
    for match_id, start, end in matches:
        span = doc[start:end]
        key = (span.start_char, span.end_char)
        if key in seen_spans:
            continue
        seen_spans.add(key)
        matched_text = span.text
        official_name = alias_map.get(matched_text.lower(), nlp.vocab.strings[match_id])
        mentions.append((official_name, matched_text, span.start_char, span.end_char))
    return mentions


# --- Skill extraction helpers --------------------------------------------------

def extract_skills_from_jd(jd_text: str, skill_map: Dict[str, List[str]]) -> List[str]:
    """Extract required skills from the JD using alias matching."""
    if not jd_text:
        return []

    mentions = _match_skill_mentions(jd_text, skill_map)
    found_skills = {official_name for official_name, _, _, _ in mentions}
    return list(found_skills)


def summarize_jd(jd_text: str, skill_map: Dict[str, List[str]]) -> JDSummary:
    summary = JDSummary()
    if not jd_text:
        return summary

    lines = [line.strip() for line in jd_text.splitlines() if line.strip()]
    must_have: Set[str] = set()
    nice_to_have: Set[str] = set()
    general: Set[str] = set()

    for line in lines:
        mentions = {official for official, _, _, _ in _match_skill_mentions(line, skill_map)}
        if not mentions:
            continue
        lowered = line.lower()
        if any(hint in lowered for hint in JD_MUST_HAVE_HINTS):
            must_have.update(mentions)
        elif any(hint in lowered for hint in JD_NICE_HINTS):
            nice_to_have.update(mentions)
        else:
            general.update(mentions)

    if not must_have and general:
        for skill in list(general)[: min(5, len(general))]:
            must_have.add(skill)
            general.discard(skill)

    if not nice_to_have and general:
        nice_to_have.update(list(general)[: min(5, len(general))])

    summary.must_have_skills = sorted(must_have)
    summary.nice_to_have_skills = sorted(nice_to_have)

    doc = _load_spacy_model()(jd_text)
    domain_terms: List[str] = []
    seen_terms = set()
    skill_lower = {skill.lower() for skill in summary.must_have_skills + summary.nice_to_have_skills}
    for token in doc:
        lemma = token.lemma_.lower()
        if token.pos_ not in {"NOUN", "PROPN"}:
            continue
        if len(lemma) < 4 or lemma in DOMAIN_STOPWORDS or lemma in skill_lower:
            continue
        if lemma not in seen_terms:
            seen_terms.add(lemma)
            domain_terms.append(token.text.strip())
        if len(domain_terms) >= 15:
            break
    summary.domain_keywords = domain_terms

    role_titles = set()
    for chunk in doc.noun_chunks:
        text = chunk.text.strip()
        lowered = text.lower()
        if any(keyword in lowered.split() for keyword in ROLE_KEYWORDS):
            role_titles.add(text)
    if not role_titles:
        # fall back to skill names containing role keywords
        for skill in summary.must_have_skills + summary.nice_to_have_skills:
            lower_skill = skill.lower()
            if any(keyword in lower_skill for keyword in ROLE_KEYWORDS):
                role_titles.add(skill)
    summary.role_titles = sorted(role_titles)

    jd_lower = jd_text.lower()
    experience_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:years?|yrs?)\s+(?:of\s+)?experience", jd_lower)
    if experience_matches:
        summary.min_years_experience = max(float(value) for value in experience_matches)

    return summary


def split_resume_into_sections(resume_text: str) -> Dict[str, str]:
    """Split resume text into sections keyed by common headings."""
    sections: Dict[str, str] = {}
    if not resume_text:
        return sections

    resume_text_lower = resume_text.lower()
    SECTION_KEYWORDS = {
        "experience": [
            "professional experience",
            "work experience",
            "employment history",
            "job history",
            "career history",
            "experience summary",
            "experience overview",
            "relevant experience",
        ],
        "education": [
            "education",
            "academic background",
            "academic qualifications",
            "education history",
        ],
        "skills": [
            "skills",
            "technical skills",
            "core skills",
            "competencies",
            "proficiencies",
        ],
        "projects": [
            "projects",
            "personal projects",
            "academic projects",
            "project highlights",
            "selected projects",
        ],
        "certifications": [
            "certifications",
            "certification",
            "licenses",
            "professional certifications",
        ],
        "summary": [
            "summary",
            "professional summary",
            "profile",
            "professional profile",
            "career summary",
            "executive summary",
        ],
        "achievements": [
            "achievements",
            "accomplishments",
            "key achievements",
            "awards",
        ],
    }

    found_sections_indices: List[Tuple[int, str]] = []
    for clean_name, keywords in SECTION_KEYWORDS.items():
        for keyword in keywords:
            pattern = re.compile(rf"^\s*{re.escape(keyword)}\b", re.IGNORECASE | re.MULTILINE)
            match = pattern.search(resume_text_lower)
            if match:
                found_sections_indices.append((match.start(), clean_name))
                break

    if not found_sections_indices:
        return sections

    found_sections_indices.sort()

    for idx, (start_index, section_name) in enumerate(found_sections_indices):
        end_index = (
            found_sections_indices[idx + 1][0]
            if idx + 1 < len(found_sections_indices)
            else len(resume_text)
        )
        section_text = resume_text[start_index:end_index].strip()
        sections[section_name] = sections.get(section_name, "") + "\n\n" + section_text

    return sections


# --- Experience parsing helpers ------------------------------------------------

def _month_token_to_int(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    token_clean = token.strip().lower()
    token_clean = token_clean.replace("\uFFFD", "")
    token_clean = token_clean.replace("'", "")
    token_clean = token_clean.replace(".", "")
    token_clean = token_clean.replace("sept", "sep")
    if token_clean.isdigit():
        month_val = int(token_clean)
        if 1 <= month_val <= 12:
            return month_val
    return MONTH_LOOKUP.get(token_clean)


def _normalize_year(year_token: Optional[str]) -> Optional[int]:
    if not year_token:
        return None
    year_token = year_token.strip()
    if not year_token:
        return None
    try:
        year_value = int(year_token)
    except ValueError:
        return None
    if year_value < 100:
        current_year = datetime.now().year
        base_century = (current_year // 100) * 100
        candidate = base_century + year_value
        if candidate > current_year + 1:
            candidate -= 100
        year_value = candidate
    if 1950 <= year_value <= datetime.now().year + 1:
        return year_value
    return None


def _compose_date(
    year_token: Optional[str],
    month_token: Optional[str],
    is_end: bool,
    marker: Optional[str],
) -> Tuple[Optional[date], bool]:
    if marker:
        marker_compact = re.sub(r"\s+", "", marker.lower())
        if marker_compact in PRESENT_TERMS:
            today = datetime.now().date()
            return today.replace(day=1), True

    year_value = _normalize_year(year_token)
    if year_value is None:
        return None, False

    month_value = _month_token_to_int(month_token)
    if month_value is None:
        month_value = 12 if is_end else 1

    try:
        return date(year_value, month_value, 1), False
    except ValueError:
        return None, False


def _month_index(dt_value: date) -> int:
    return dt_value.year * 12 + dt_value.month


def _months_span(start: date, end: date) -> int:
    return _month_index(end) - _month_index(start) + 1


def _index_to_date(index: int) -> date:
    year = index // 12
    month = index % 12
    if month == 0:
        year -= 1
        month = 12
    return date(year, month, 1)


def _extract_experience_segments(text: str) -> List[Dict[str, object]]:
    if not text:
        return []

    sanitized = (
        text.replace("\r", "")
                        .replace("–", "-")
        .replace("—", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2012", "-")
        .replace("\u2010", "-")
        .replace("\u2212", "-")
        .replace("\u00a0", " ")
    )
    sanitized = re.sub(r"[\uFFFD']", " ", sanitized)

    lines = sanitized.splitlines()
    line_starts: List[int] = []
    position = 0
    for line in lines:
        line_starts.append(position)
        position += len(line) + 1  # account for the newline we stripped

    segments: List[Dict[str, object]] = []
    seen_keys = set()

    def _line_index_for_offset(offset: int) -> int:
        if not line_starts:
            return 0
        idx = bisect_right(line_starts, offset) - 1
        return max(0, min(idx, len(lines) - 1))

    for pattern, source in (
        (NUMERIC_RANGE_RE, "numeric"),
        (MONTH_YEAR_RANGE_RE, "month_year"),
        (YEAR_ONLY_RANGE_RE, "year_only"),
    ):
        for match in pattern.finditer(sanitized):
            groups = match.groupdict()
            start_month_token = groups.get("start_month") or groups.get("start_month_num")
            end_month_token = groups.get("end_month") or groups.get("end_month_num")
            start_year_token = groups.get("start_year")
            end_year_token = groups.get("end_year")
            end_marker = groups.get("end_marker")

            start_date, _ = _compose_date(
                start_year_token, start_month_token, is_end=False, marker=None
            )
            end_date, end_is_present = _compose_date(
                end_year_token, end_month_token, is_end=True, marker=end_marker
            )

            if not start_date or not end_date or end_date < start_date:
                continue

            key = (_month_index(start_date), _month_index(end_date))
            if key in seen_keys:
                continue
            seen_keys.add(key)

            months = _months_span(start_date, end_date)
            if months <= 0:
                continue

            line_idx = _line_index_for_offset(match.start())
            prev_line = lines[line_idx - 1] if line_idx > 0 else ""
            prev_line_2 = lines[line_idx - 2] if line_idx > 1 else ""
            current_line = lines[line_idx] if 0 <= line_idx < len(lines) else ""
            next_line = lines[line_idx + 1] if line_idx + 1 < len(lines) else ""
            next_line_2 = lines[line_idx + 2] if line_idx + 2 < len(lines) else ""

            segments.append(
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "end_is_present": end_is_present,
                    "source": source,
                    "raw_text": match.group(0).strip(),
                    "months": months,
                    "match_text": match.group(0),
                    "context": {
                        "previous2": prev_line_2,
                        "previous": prev_line,
                        "current": current_line,
                        "next": next_line,
                        "next2": next_line_2,
                    },
                }
            )

    _assign_company_names(segments)

    filtered_segments = [seg for seg in segments if not _segment_is_non_experience(seg)]
    if filtered_segments:
        return filtered_segments
    return segments


def _clean_company_candidate(candidate: str) -> str:
    candidate = candidate.strip(" -\u2013\u2014|\u2022\u00b7,:;()[]{}")
    candidate = re.sub(r"\s{2,}", " ", candidate)
    return candidate.strip()

def _score_company_candidate(candidate: str) -> float:
    if not candidate or len(candidate) < 3:
        return float("-inf")
    words = candidate.split()
    if not words:
        return float("-inf")

    score = 0.0
    if COMPANY_HINT_REGEX.search(candidate):
        score += 2.0
    if JOB_TITLE_HINT_REGEX.search(candidate):
        score -= 3.0

    lowered = candidate.lower()
    if any(term in lowered for term in NON_COMPANY_TERMS):
        score -= 4.0
    if any(keyword in lowered for keyword in ("technologies used", "technology stack", "tech stack", "responsibilities", "summary", "skills")):
        score -= 3.0
    if any(keyword in lowered for keyword in EDUCATION_KEYWORDS):
        score -= 2.5
    if ":" in candidate and not candidate.strip().endswith(":"):
        score -= 0.6
    if CONTACT_PATTERN.search(candidate) or "@" in candidate or "http" in lowered or "/" in candidate:
        score -= 5.0

    uppercase_letters = sum(1 for c in candidate if c.isupper())
    alpha_letters = sum(1 for c in candidate if c.isalpha())
    if alpha_letters:
        uppercase_ratio = uppercase_letters / alpha_letters
        if uppercase_ratio >= 0.4:
            score += 0.8
    else:
        score -= 1.0

    letters = sum(c.isalpha() for c in candidate)
    non_alnum = sum(not c.isalnum() and not c.isspace() for c in candidate)
    if letters and (non_alnum / max(1, len(candidate))) > 0.25:
        score -= 1.0

    if words[0][0].isupper() and words[0].isalpha():
        score += 0.6

    if len(words) <= 5:
        score += 0.4

    if any(char.isdigit() for char in candidate):
        score -= 0.2

    score += min(len(words), 6) * 0.1
    return score


def _select_company_candidate(text: str) -> Tuple[Optional[str], float]:
    if not text:
        return (None, float("-inf"))

    best_candidate: Optional[str] = None
    best_score = float("-inf")

    text = re.sub(r"^\(?\d{1,2}\)?\.\s*", "", text).strip()

    fragments = LINE_SPLIT_REGEX.split(text)
    if not fragments:
        fragments = [text]

    for fragment in fragments:
        fragment = fragment.strip()
        if not fragment:
            continue

        for chunk in re.split(r"\b(?:at|@|for)\b", fragment, flags=re.IGNORECASE):
            chunk = chunk.strip()
            if not chunk:
                continue

            sub_parts = re.split(r"[-\u2010-\u2015\u2212]{1,2}", chunk)
            if not sub_parts:
                sub_parts = [chunk]

            for part in sub_parts:
                cleaned = _clean_company_candidate(part)
                if not cleaned:
                    continue
                score = _score_company_candidate(cleaned)
                if score > best_score:
                    best_candidate = cleaned
                    best_score = score

    return best_candidate, best_score


def _guess_company_from_context(context: Dict[str, str], match_text: str) -> str:
    search_order = ["current", "previous", "next"]
    best_candidate = ""
    best_score = float("-inf")

    for idx, key in enumerate(search_order):
        line = context.get(key, "") if context else ""
        if not line or not line.strip():
            continue

        candidate_text = line
        if key == "current" and match_text:
            candidate_text = re.sub(re.escape(match_text), " ", candidate_text, flags=re.IGNORECASE)

        candidate, score = _select_company_candidate(candidate_text)
        if not candidate:
            continue

        score_adjusted = score - (0.15 * idx)
        if key == "current":
            score_adjusted += 0.3
        elif key == "previous":
            score_adjusted += 0.15
        else:  # next
            score_adjusted -= 0.05

        if score_adjusted > best_score:
            best_score = score_adjusted
            best_candidate = candidate

    if best_score > 0:
        return best_candidate
    return ""


def _assign_company_names(segments: List[Dict[str, object]]) -> None:
    for segment in segments:
        context = segment.get("context", {})
        match_text = segment.get("match_text", "")
        company = _guess_company_from_context(context, match_text)
        segment["company"] = company or ""


def _segment_text_blob(segment: Dict[str, object]) -> str:
    context = segment.get("context", {}) or {}
    parts = [
        segment.get("raw_text", ""),
        segment.get("match_text", ""),
        segment.get("company", ""),
        context.get("previous", ""),
        context.get("previous2", ""),
        context.get("current", ""),
        context.get("next", ""),
        context.get("next2", ""),
    ]
    return " ".join(part for part in parts if part).lower()


def _segment_is_non_experience(segment: Dict[str, object]) -> bool:
    blob = _segment_text_blob(segment)
    if not blob:
        return True

    company = (segment.get("company") or "").lower()

    for keyword in NON_EXPERIENCE_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', blob):
            return True
    if company and any(term in company for term in NON_COMPANY_TERMS):
        return True

    if not company:
        if not any(term in blob for term in CAREER_KEYWORDS):
            return True

    if "honor roll" in blob or ("dean" in blob and "list" in blob):
        return True

    return False


def _total_months_from_segments(segments: List[Dict[str, object]]) -> int:
    if not segments:
        return 0

    sorted_segments = sorted(
        segments, key=lambda seg: (_month_index(seg["start_date"]), _month_index(seg["end_date"]))
    )
    total = 0
    current_start = sorted_segments[0]["start_date"]
    current_end = sorted_segments[0]["end_date"]

    for seg in sorted_segments[1:]:
        seg_start = seg["start_date"]
        seg_end = seg["end_date"]
        if _month_index(seg_start) <= _month_index(current_end) + 1:
            if seg_end > current_end:
                current_end = seg_end
        else:
            total += _months_span(current_start, current_end)
            current_start = seg_start
            current_end = seg_end

    total += _months_span(current_start, current_end)
    return total


def _calculate_gaps(segments: List[Dict[str, object]]) -> List[Dict[str, object]]:
    if len(segments) < 2:
        return []

    sorted_segments = sorted(
        segments, key=lambda seg: (_month_index(seg["start_date"]), _month_index(seg["end_date"]))
    )
    gaps: List[Dict[str, object]] = []

    for prev, nxt in zip(sorted_segments, sorted_segments[1:]):
        gap_months = _month_index(nxt["start_date"]) - _month_index(prev["end_date"]) - 1
        if gap_months >= 2:
            gap_start_date = _index_to_date(_month_index(prev["end_date"]) + 1)
            gap_end_date = _index_to_date(_month_index(nxt["start_date"]) - 1)
            gaps.append(
                {
                    "months": gap_months,
                    "start": gap_start_date.strftime("%Y-%m"),
                    "end": gap_end_date.strftime("%Y-%m"),
                }
            )

    return gaps


def _year_month_to_index(value: str) -> Optional[int]:
    if not value:
        return None
    if value.lower() == "present":
        today = datetime.now().date()
        return today.year * 12 + today.month
    try:
        year_str, month_str = value.split("-", 1)
        return int(year_str) * 12 + int(month_str)
    except Exception:
        return None


def _calculate_recent_years(segments: List[Dict[str, object]], window_years: int = 5) -> float:
    if not segments:
        return 0.0
    today = datetime.now().date()
    cutoff_index = (today.year - window_years) * 12 + today.month
    total_recent_months = 0
    for segment in segments:
        start_index = _year_month_to_index(segment.get("start"))
        end_index = _year_month_to_index(segment.get("end")) or (today.year * 12 + today.month)
        if start_index is None or end_index is None:
            continue
        if end_index < cutoff_index:
            continue
        adjusted_start = max(start_index, cutoff_index)
        total_recent_months += max(0, end_index - adjusted_start + 1)
    return round(total_recent_months / 12.0, 1)


def calculate_experience_metrics(section_text: str, fallback_text: str = "") -> Dict[str, object]:
    primary_segments = _extract_experience_segments(section_text)
    used_fallback = False

    if not primary_segments and fallback_text:
        fallback_segments = _extract_experience_segments(fallback_text)
        if fallback_segments:
            primary_segments = fallback_segments
            used_fallback = True

    if not primary_segments:
        return {
            "years": 0.0,
            "total_months": 0,
            "segments": [],
            "gaps": [],
            "used_fallback": used_fallback,
        }

    total_months = _total_months_from_segments(primary_segments)
    years = round(total_months / 12.0, 1)

    sorted_segments = sorted(
        primary_segments, key=lambda seg: (_month_index(seg["start_date"]), _month_index(seg["end_date"]))
    )
    segments_payload: List[Dict[str, object]] = []
    for seg in sorted_segments:
        segments_payload.append(
            {
                "label": seg["raw_text"],
                "start": seg["start_date"].strftime("%Y-%m"),
                "end": "Present" if seg["end_is_present"] else seg["end_date"].strftime("%Y-%m"),
                "duration_months": seg["months"],
                "duration_years": round(seg["months"] / 12.0, 2),
                "source": seg["source"],
                "company": seg.get("company", ""),
            }
        )

    gaps = _calculate_gaps(sorted_segments)

    return {
        "years": years,
        "total_months": total_months,
        "segments": segments_payload,
        "gaps": gaps,
        "used_fallback": used_fallback,
    }


def calculate_experience_years(section_text: str) -> float:
    return calculate_experience_metrics(section_text)["years"]


# --- Skill coverage helpers ----------------------------------------------------

def _extract_resume_signals(
    resume_text: str,
    extracted_sections: Dict[str, str],
    jd_summary: JDSummary,
    skill_map: Dict[str, List[str]],
) -> ResumeSignals:
    signals = ResumeSignals()
    if not resume_text:
        return signals

    resume_lower = resume_text.lower()
    must_have_set = set(jd_summary.must_have_skills)
    nice_to_have_set = set(jd_summary.nice_to_have_skills)

    mentions = _match_skill_mentions(resume_text, skill_map)
    for official_name, _, _, _ in mentions:
        if official_name in must_have_set:
            if official_name not in signals.matched_must_have:
                signals.matched_must_have.append(official_name)
        elif official_name in nice_to_have_set:
            if official_name not in signals.matched_nice_to_have:
                signals.matched_nice_to_have.append(official_name)
        else:
            if official_name not in signals.matched_extra_skills:
                signals.matched_extra_skills.append(official_name)

    domain_hits = []
    seen_domains = set()
    for keyword in jd_summary.domain_keywords:
        key_lower = keyword.lower()
        if key_lower and key_lower in resume_lower and key_lower not in seen_domains:
            seen_domains.add(key_lower)
            domain_hits.append(keyword)
    signals.domain_hits = domain_hits

    role_hits = []
    seen_roles = set()
    for role in jd_summary.role_titles:
        role_lower = role.lower()
        if role_lower and role_lower in resume_lower and role_lower not in seen_roles:
            seen_roles.add(role_lower)
            role_hits.append(role)
    signals.role_hits = role_hits

    experience_section_text = extracted_sections.get("experience", "")
    metrics = calculate_experience_metrics(experience_section_text, resume_text)
    signals.experience_years = metrics["years"]
    signals.segments = metrics["segments"]
    signals.gaps = metrics["gaps"]
    signals.recent_years = _calculate_recent_years(metrics["segments"])
    signals.used_fallback = metrics.get("used_fallback", False)

    return signals


def calculate_skill_relevance(
    text: str,
    required_skills: List[str],
    skill_map: Dict[str, List[str]],
) -> Tuple[float, List[str]]:
    if not required_skills or not text:
        return 0.0, []

    nlp = _load_spacy_model()
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    alias_to_official_map = {
        alias.lower(): official for official, aliases in skill_map.items() for alias in aliases
    }

    for official_name, aliases in skill_map.items():
        skill_patterns = [nlp(alias) for alias in aliases]
        matcher.add(official_name, skill_patterns)

    doc = nlp(text)
    matches = matcher(doc)

    found_skills = {
        alias_to_official_map.get(doc[start:end].text.lower(), nlp.vocab.strings[match_id])
        for match_id, start, end in matches
    }
    matched_official_skills = found_skills.intersection(set(required_skills))

    if not required_skills:
        return 0.0, list(matched_official_skills)

    relevance_score = len(matched_official_skills) / len(required_skills)
    return relevance_score, list(matched_official_skills)


def calculate_project_impact(
    text: str, required_skills: List[str], skill_map: Dict[str, List[str]]
) -> float:
    if not text:
        return 0.0

    project_keywords = [
        "developed",
        "created",
        "led",
        "managed",
        "architected",
        "implemented",
        "designed",
        "built",
        "deployed",
        "optimized",
        "engineered",
        "launched",
    ]

    sentences = [s.strip() for s in re.split(r"[.\n]", text) if s.strip()]
    project_sentences = [
        s for s in sentences if any(keyword in s.lower() for keyword in project_keywords)
    ]

    if not project_sentences:
        return 0.0

    total_relevance = 0.0
    for sentence in project_sentences:
        relevance, _ = calculate_skill_relevance(sentence, required_skills, skill_map)
        total_relevance += relevance

    return total_relevance / len(project_sentences)


# --- Insight builders ----------------------------------------------------------

def _compute_section_skill_breakdown(
    extracted_sections: Dict[str, str],
    job_required_skills: List[str],
    skill_map: Dict[str, List[str]],
) -> Dict[str, Dict[str, object]]:
    breakdown: Dict[str, Dict[str, object]] = {}
    for section_name, text in extracted_sections.items():
        if not text.strip():
            continue
        score, matches = calculate_skill_relevance(text, job_required_skills, skill_map)
        if score <= 0 and not matches:
            continue
        breakdown[section_name] = {
            "score": round(score * 100, 1),
            "matched_skills": matches,
        }
    return breakdown


def _extract_notable_sentences(
    resume_text: str, matched_skills: List[str], limit: int = 5
) -> List[str]:
    if not resume_text or not matched_skills:
        return []

    sentences = re.split(r"(?<=[.!?])\s+|\n+", resume_text)
    matched_lower = [skill.lower() for skill in matched_skills]
    highlights: List[str] = []

    for sentence in sentences:
        candidate = sentence.strip()
        if len(candidate) < 40:
            continue
        lower_sentence = candidate.lower()
        if any(skill in lower_sentence for skill in matched_lower) or re.search(
            r"\b(designed|built|developed|implemented|led|architected|deployed|optimized|mentored)\b",
            lower_sentence,
        ):
            highlights.append(candidate)
        if len(highlights) >= limit:
            break

    return highlights


def _extract_section_bullets(section_text: str, limit: int = 5) -> List[str]:
    if not section_text:
        return []
    lines = [
        line.strip(SECTION_TRIM_CHARS)
        for line in section_text.splitlines()
        if line.strip()
    ]
    unique: List[str] = []
    seen = set()
    for line in lines:
        if len(line) < 4:
            continue
        normalized = line.strip(SECTION_TRIM_CHARS)
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(normalized)
        if len(unique) >= limit:
            break
    return unique


def _extract_education_highlights(education_text: str) -> List[str]:
    if not education_text:
        return []
    degree_pattern = re.compile(
        r"(b\.tech|bachelor|b\.e|bsc|b\.sc|master|m\.tech|m\.s|msc|mba|ph\.d|diploma)",
        re.IGNORECASE,
    )
    highlights: List[str] = []
    for line in education_text.splitlines():
        cleaned = line.strip(SECTION_TRIM_CHARS)
        if not cleaned:
            continue
        if degree_pattern.search(cleaned):
            highlights.append(cleaned)
        if len(highlights) >= 3:
            break
    return highlights


def _extract_certification_highlights(certification_text: str, limit: int = 3) -> List[str]:
    if not certification_text:
        return []

    candidates = _extract_section_bullets(certification_text, limit=limit * 3)
    filtered: List[str] = []
    for line in candidates:
        normalized = line.strip(":- ")
        if not normalized or CONTACT_PATTERN.search(normalized):
            continue
        lowered = normalized.lower()
        if "certificate" in lowered or "certification" in lowered or "certified" in lowered:
            filtered.append(normalized)
            continue
        if any(keyword in lowered for keyword in CERTIFICATION_KEYWORDS):
            filtered.append(normalized)
            continue
    return _unique_trimmed(filtered, limit)


def _compute_top_skill_mentions(
    resume_text: str, skill_map: Dict[str, List[str]], top_n: int = 5
) -> List[str]:
    if not resume_text:
        return []
    text_lower = resume_text.lower()
    counts: Counter[str] = Counter()
    for official, aliases in skill_map.items():
        for alias in aliases:
            alias_lower = alias.lower()
            if not alias_lower or len(alias_lower) < 3:
                continue
            occurrences = text_lower.count(alias_lower)
            if occurrences:
                counts[official] += occurrences
    return [item for item, _ in counts.most_common(top_n)]


def _unique_trimmed(items: List[str], limit: int = 5) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if not item:
            continue
        normalized = item.strip()
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _score_resume_against_jd(jd_summary: JDSummary, signals: ResumeSignals) -> ScoreBreakdown:
    penalties: List[str] = []
    penalty_value = 0.0
    bonus = 0.0

    must_total = len(jd_summary.must_have_skills)
    must_hits = len(signals.matched_must_have)
    if must_total:
        must_ratio = must_hits / must_total
    else:
        must_ratio = 1.0 if signals.matched_extra_skills or signals.matched_nice_to_have else 0.0

    nice_total = len(jd_summary.nice_to_have_skills)
    nice_hits = len(signals.matched_nice_to_have)
    if nice_total:
        nice_ratio = nice_hits / nice_total
    else:
        nice_ratio = 1.0 if signals.matched_extra_skills else 0.0

    if must_total:
        skill_component = min(1.0, (0.8 * must_ratio) + (0.2 * nice_ratio))
    else:
        base = nice_ratio if nice_total else 0.0
        extra_boost = min(0.2, len(signals.matched_extra_skills) * 0.05)
        skill_component = min(1.0, base + extra_boost)

    domain_total = max(1, min(len(jd_summary.domain_keywords), 8))
    domain_hits = len(signals.domain_hits)
    domain_ratio = min(1.0, domain_hits / domain_total)
    domain_component = domain_ratio

    if jd_summary.role_titles:
        role_ratio = min(1.0, len(signals.role_hits) / len(jd_summary.role_titles))
    else:
        role_ratio = 1.0 if signals.role_hits else 0.5
    role_component = role_ratio

    target_years = jd_summary.min_years_experience or 5.0
    experience_ratio = min(1.0, signals.recent_years / max(1.0, target_years))
    experience_component = experience_ratio

    if must_total and must_ratio == 0:
        penalty_value += 0.35
        penalties.append("No core JD skills detected.")
    elif must_total and must_ratio < 0.5:
        penalty_value += 0.2
        penalties.append("Less than half of required JD skills matched.")

    if jd_summary.role_titles and not signals.role_hits:
        penalty_value += 0.12
        penalties.append("Role titles from the JD are missing in the resume.")

    if domain_ratio < 0.2 and jd_summary.domain_keywords:
        penalty_value += 0.1
        penalties.append("Few JD domain keywords found in resume content.")

    if jd_summary.min_years_experience and signals.experience_years < jd_summary.min_years_experience * 0.6:
        penalty_value += 0.15
        penalties.append("Verified experience below JD expectation.")

    if signals.gaps and any(gap["months"] > 6 for gap in signals.gaps):
        penalty_value += 0.05
        penalties.append("Employment gaps longer than six months detected.")

    if must_ratio >= 1.0 and domain_ratio >= 0.6 and role_ratio >= 0.6:
        bonus += 0.07
    if signals.experience_years >= target_years + 3:
        bonus += 0.03

    weighted_score = (
        (skill_component * 0.4)
        + (domain_component * 0.2)
        + (role_component * 0.2)
        + (experience_component * 0.2)
    )

    final_score = max(0.0, min(1.0, weighted_score + bonus - penalty_value))

    return ScoreBreakdown(
        overall=round(final_score * 100, 2),
        skill_component=round(skill_component * 100, 2),
        experience_component=round(experience_component * 100, 2),
        domain_component=round(domain_component * 100, 2),
        role_component=round(role_component * 100, 2),
        bonus_component=round((bonus - penalty_value) * 100, 2),
        penalties=penalties,
        must_have_ratio=round(must_ratio, 2),
        nice_to_have_ratio=round(nice_ratio, 2),
        domain_ratio=round(domain_ratio, 2),
        role_ratio=round(role_ratio, 2),
        experience_ratio=round(experience_ratio, 2),
    )


def _compose_summary(
    final_score_pct: float,
    experience_years: float,
    matched_skills: List[str],
    missing_skills: List[str],
    total_required_skills: int,
) -> str:
    exp_sentence = (
        f"Approx. {experience_years:.1f} years of relevant experience identified from the timeline."
        if experience_years
        else "Experience timeline could not be confidently inferred from the resume text."
    )

    if matched_skills:
        top_matches = ", ".join(matched_skills[:4])
        if total_required_skills:
            skill_sentence = (
                f"Matches {len(matched_skills)} of {total_required_skills} priority skills including {top_matches}."
            )
        else:
            skill_sentence = f"Detected relevant skills including {top_matches}."
    else:
        skill_sentence = "The resume does not explicitly reference the supplied priority skill set."

    if missing_skills:
        gaps_sentence = (
            f"Validate exposure to {', '.join(missing_skills[:3])}; overall suitability score: {round(final_score_pct):d}%."
        )
    else:
        gaps_sentence = f"Overall suitability score: {round(final_score_pct):d}%."

    return " ".join([exp_sentence, skill_sentence, gaps_sentence])


def _derive_strengths_risks(
    experience_years: float,
    matched_skills: List[str],
    missing_skills: List[str],
    experience_metrics: Dict[str, object],
    final_score_pct: float,
    section_skill_breakdown: Dict[str, Dict[str, object]],
) -> Tuple[List[str], List[str], List[str]]:
    strengths: List[str] = []
    risks: List[str] = []
    recommendations: List[str] = []

    if experience_years >= 5:
        strengths.append(f"Demonstrates solid tenure (~{experience_years:.1f} years).")
    elif experience_years >= 2:
        strengths.append(f"Shows {experience_years:.1f} years of directly mapped experience.")
    else:
        risks.append("Limited verified experience (<2 years) detected in the timeline.")

    if matched_skills:
        strengths.append(f"Hands-on exposure to {', '.join(matched_skills[:5])}.")
    else:
        risks.append("Priority technical keywords are missing or implicit.")

    if missing_skills:
        recommendations.append(f"Probe recent work around {', '.join(missing_skills[:3])}.")

    if experience_metrics.get("gaps"):
        gap = experience_metrics["gaps"][0]
        risks.append(
            f"Employment gap of {gap['months']} months detected ({gap['start']} - {gap['end']})."
        )

    project_score = section_skill_breakdown.get("projects", {}).get("score", 0.0)
    if project_score >= 40:
        strengths.append("Projects section highlights measurable delivery aligned to the JD.")
    elif project_score == 0:
        recommendations.append("Request project examples that demonstrate JD-aligned impact.")

    if final_score_pct < 50:
        recommendations.append("Consider a technical screen to validate claims and potential fit.")

    return (
        _unique_trimmed(strengths),
        _unique_trimmed(risks),
        _unique_trimmed(recommendations),
    )


def _scale_skill_strength(
    raw_ratio: float,
    matched_skills: List[str],
    required_skills: List[str],
) -> float:
    matched_count = len(matched_skills)
    required_count = len(required_skills)

    if matched_count == 0:
        return 0.0

    if required_count == 0:
        base = min(1.0, matched_count / 6.0)
    else:
        coverage = matched_count / required_count
        coverage = max(0.0, min(1.0, coverage))
        base = max(raw_ratio, coverage)
        penalty = 1.0 - coverage
        base = base * (1.0 - 0.4 * penalty)

    base = max(0.0, min(1.0, base))
    shaped = base ** 1.2
    category_bonus = 0.0
    if required_count and matched_count >= max(1, required_count // 2):
        category_bonus = 0.1
    shaped += min(0.1, matched_count * 0.02) + category_bonus

    return max(0.0, min(1.0, shaped))


def _scale_experience_signal(years: float) -> float:
    if years <= 0:
        return 0.0
    if years >= 12:
        return 1.0
    if years >= 8:
        return 0.85 + (years - 8) * 0.05
    if years >= 5:
        return 0.7 + (years - 5) * 0.05
    if years >= 3:
        return 0.5 + (years - 3) * 0.1
    if years >= 1:
        return 0.25 + (years - 1) * 0.125
    return years * 0.22


# --- Main analysis entry point -------------------------------------------------

def analyze_one_resume(
    resume_text: str,
    jd_text: str,
    jd_summary: Optional[JDSummary],
    skill_map: Dict[str, List[str]],
    analysis_mode: str = "standard",
) -> Dict[str, object]:
    if resume_text.startswith("Error:"):
        resume_text = ""
    if jd_text.startswith("Error:"):
        jd_text = ""

    if jd_summary is None:
        jd_summary = summarize_jd(jd_text, skill_map)

    extracted_sections = split_resume_into_sections(resume_text)
    signals = _extract_resume_signals(resume_text, extracted_sections, jd_summary, skill_map)
    score_breakdown = _score_resume_against_jd(jd_summary, signals)

    required_skill_pool = jd_summary.must_have_skills + jd_summary.nice_to_have_skills
    coverage_pool = jd_summary.must_have_skills if jd_summary.must_have_skills else required_skill_pool

    matched_skills = signals.matched_must_have + signals.matched_nice_to_have
    missing_core_skills = [skill for skill in jd_summary.must_have_skills if skill not in signals.matched_must_have]
    optional_missing = [skill for skill in jd_summary.nice_to_have_skills if skill not in signals.matched_nice_to_have]

    section_skill_breakdown = _compute_section_skill_breakdown(
        extracted_sections, required_skill_pool, skill_map
    )

    final_score_pct = score_breakdown.overall
    summary_text = _compose_summary(
        final_score_pct,
        signals.experience_years,
        matched_skills,
        missing_core_skills,
        len(coverage_pool),
    )

    strengths, risks, recommendations = _derive_strengths_risks(
        signals.experience_years,
        matched_skills,
        missing_core_skills,
        {
            "years": signals.experience_years,
            "segments": signals.segments,
            "gaps": signals.gaps,
            "used_fallback": signals.used_fallback,
        },
        final_score_pct,
        section_skill_breakdown,
    )

    education_highlights = _extract_education_highlights(extracted_sections.get("education", ""))
    certification_highlights = _extract_certification_highlights(
        extracted_sections.get("certifications", ""), limit=3
    )
    summary_highlights = _extract_section_bullets(
        extracted_sections.get("summary", ""), limit=3
    )

    coverage_ratio = score_breakdown.must_have_ratio
    details: Dict[str, object] = {
        "calculated_years": signals.experience_years,
        "recent_years": signals.recent_years,
        "matched_skills": matched_skills,
        "missing_skills": missing_core_skills,
        "missing_optional_skills": optional_missing,
        "core_skill_matches": signals.matched_must_have,
        "support_skill_matches": signals.matched_nice_to_have,
        "domain_hits": signals.domain_hits,
        "role_hits": signals.role_hits,
        "ai_summary": summary_text,
        "strengths": strengths,
        "risks": risks,
        "recommendations": recommendations,
        "experience_segments": signals.segments,
        "highlighted_keywords": _compute_top_skill_mentions(resume_text, skill_map),
        "education_highlights": education_highlights,
        "certifications": certification_highlights,
        "summary_highlights": summary_highlights,
        "score_breakdown": {
            "core_skill": score_breakdown.skill_component,
            "domain_alignment": score_breakdown.domain_component,
            "role_alignment": score_breakdown.role_component,
            "experience_alignment": score_breakdown.experience_component,
            "bonus_or_penalty": score_breakdown.bonus_component,
            "must_have_ratio": score_breakdown.must_have_ratio,
            "nice_to_have_ratio": score_breakdown.nice_to_have_ratio,
            "domain_ratio": score_breakdown.domain_ratio,
            "role_ratio": score_breakdown.role_ratio,
            "experience_ratio": score_breakdown.experience_ratio,
            "penalties": score_breakdown.penalties,
        },
    }

    if coverage_pool:
        details["skills_coverage_ratio"] = round(coverage_ratio, 2)

    if signals.gaps:
        details["employment_gaps"] = signals.gaps

    if signals.used_fallback:
        details.setdefault(
            "notes",
            "Experience timeline inferred from the full resume text because a dedicated experience section header was not detected.",
        )

    if analysis_mode.lower() == "deep":
        details["deep_insights"] = {
            "notable_sentences": _extract_notable_sentences(resume_text, matched_skills),
            "recommended_questions": [
                f"Can you walk me through your work with {skill}?" for skill in missing_core_skills[:3]
            ],
            "experience_timeline": signals.segments,
            "employment_gaps": signals.gaps,
            "section_skill_breakdown": section_skill_breakdown,
        }

    return {
        "final_score": final_score_pct,
        "details": details,
    }


@lru_cache(maxsize=1)
def _load_spacy_model():
    """Lazy-load the spaCy model once per process."""
    return spacy.load("en_core_web_sm")
