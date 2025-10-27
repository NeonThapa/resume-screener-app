import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ResumeLLMInput:
    filename: str
    jd_text: str
    resume_text: str = ""
    resume_pdf_base64: str = ""
    must_have_skills: List[str] = field(default_factory=list)
    nice_to_have_skills: List[str] = field(default_factory=list)
    jd_keywords: List[str] = field(default_factory=list)


def _default_client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("AI Analyzer: missing API key. Set OPENROUTER_API_KEY or OPENAI_API_KEY.")
        return None

    base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    headers = {
        "HTTP-Referer": os.getenv("LLM_HTTP_REFERER", "Local"),
        "X-Title": os.getenv("LLM_APP_TITLE", "Resume Screener"),
    }

    try:
        client = OpenAI(api_key=api_key, base_url=base_url, default_headers=headers)
        logger.info("AI Analyzer: initialized OpenAI-compatible client for base_url=%s", base_url)
        return client
    except Exception as exc:  # pragma: no cover - best effort logging
        logger.exception("AI Analyzer: failed to initialize client: %s", exc)
        return None


CLIENT = _default_client()
MODEL_NAME = os.getenv("RESUME_LLM_MODEL", "minimax/minimax-m2:free")


LLM_PROMPT_TEMPLATE = """
You are an expert technical recruiter. Read the job description and resume text carefully (ignore layout artefacts).

Objectives (in priority order):
1. Determine true relevant experience by scanning roles, dates, and responsibilities. Convert timelines into whole years (round to nearest integer).
2. Identify skills and achievements that align with the JD requirements, even when phrased differently.
3. Summarise the candidate's fit and highlight decisive strengths, risks, and follow-up questions.

Must-have focus areas: {must_have_bullets}
Supporting focus areas: {nice_to_have_bullets}
Key domain terms: {domain_terms}

If the resume text appears truncated AND a PDF payload is provided below, decode the PDF and read it to ensure you capture the candidate's technical experience.
If the resume text explicitly states that no content could be extracted and the PDF also appears unreadable, treat the candidate as having insufficient data and reflect that in the output.

Respond ONLY with a JSON object matching this schema:
{{
  "final_score": <integer 0-100 representing overall fit>,
  "details": {{
    "ai_summary": <string 2-3 sentence synopsis>,
    "overall_skill_score": <integer 0-100>,
    "experience_score": <integer 0-100>,
    "project_score": <integer 0-100>,
    "calculated_years": <number of total relevant years>,
    "recent_years": <number of relevant years in the last 5 years>,
    "core_skill_matches": [<matched core skills>],
    "support_skill_matches": [<matched supporting/optional skills>],
    "matched_skills": [<all matched skills>],
    "missing_skills": [<critical missing skills>],
    "missing_optional_skills": [<optional skills missing>],
    "strengths": [<candidate strengths bullet list>],
    "risks": [<concerns or red flags>],
    "recommendations": [<follow-up interview questions or notes>],
    "experience_segments": [
      {{
        "label": <role or focus>,
        "company": <employer>,
        "start": <human readable start date>,
        "end": <human readable end date or 'Present'>,
        "duration_years": <float years in role>
      }}
    ],
    "employment_gaps": [
      {{
        "start": <gap start>,
        "end": <gap end>,
        "months": <float months gap>
      }}
    ],
    "education_highlights": [<key education facts>],
    "certifications": [<certifications>],
    "summary_highlights": [<headline profile bullets>],
    "highlighted_keywords": [<notable keywords to surface>],
    "score_breakdown": {{
      "core_skill": <integer 0-100>,
      "domain_alignment": <integer 0-100>,
      "role_alignment": <integer 0-100>,
      "experience_alignment": <integer 0-100>,
      "must_have_ratio": <float 0-1 coverage of critical skills>,
      "nice_to_have_ratio": <float 0-1 coverage of optional skills>,
      "bonus_or_penalty": <float positive/negative adjustment>,
      "penalties": [<strings describing penalties>]
    }},
    "deep_insights": {{
      "notable_sentences": [<accomplishment snippets>],
      "recommended_questions": [<interview follow-up prompts>]
    }},
    "skills_coverage_ratio": <float 0-1 overall skill coverage>,
    "ai_assessment": {{
      "final_score": <integer 0-100>,
      "matched_skills": [<skills>],
      "ai_summary": <string summary or null>
    }}
  }}
}}

Rules:
- Output must be valid JSON (double quotes, no trailing commas).
- Always populate every key: use empty arrays for missing lists, null for unknown numerics, and 0 when you cannot estimate a score.
- Keep reasoning concise; avoid repeating the JD verbatim.

Job Description:
---
{jd_text}
---

Resume Text (may be empty if extraction failed):
---
{resume_text}
---

Base64 PDF Payload (decode if needed):
---
{resume_pdf_base64}
---
"""


def analyze_one_resume(
    *,
    resume_input: ResumeLLMInput,
    client: Optional[OpenAI] = None,
) -> Dict[str, Any]:
    """Send resume + JD context to the LLM and normalise the structured response."""

    llm_client = client or CLIENT
    if llm_client is None:
        return {
            "final_score": 0,
            "details": {
                "ai_summary": "AI client not initialised. Provide OPENROUTER_API_KEY or OPENAI_API_KEY."
            },
        }

    prepared_resume_text = _prepare_resume_excerpt(resume_input.resume_text)
    prompt = LLM_PROMPT_TEMPLATE.format(
        jd_text=resume_input.jd_text.strip(),
        resume_text=prepared_resume_text.strip(),
        resume_pdf_base64=resume_input.resume_pdf_base64.strip(),
        must_have_bullets=_format_focus_list(resume_input.must_have_skills),
        nice_to_have_bullets=_format_focus_list(resume_input.nice_to_have_skills),
        domain_terms=", ".join(resume_input.jd_keywords[:12]) or "None provided",
    )

    messages = [
        {
            "role": "system",
            "content": "You are a meticulous HR analyst. Respond only with valid JSON matching the requested schema.",
        },
        {"role": "user", "content": prompt},
    ]

    request_kwargs: Dict[str, Any] = {
        "model": MODEL_NAME,
        "messages": messages,
    }
    if not MODEL_NAME.startswith("minimax/"):
        request_kwargs["response_format"] = {"type": "json_object"}

    try:
        raw, parsed = _call_llm_with_retries(llm_client, request_kwargs, resume_input.filename)
    except Exception as exc:  # pragma: no cover - network/runtime failure path
        logger.exception("LLM call failed for %s: %s", resume_input.filename, exc)
        return {
            "final_score": 0,
            "details": {
                "ai_summary": f"AI analysis failed: {exc}",
            },
        }

    payload = _normalise_llm_payload(parsed)
    return _apply_score_guards(payload, resume_input)


def _normalise_llm_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce missing keys and types so the frontend can render safely."""
    final_score = _coerce_int(payload.get("final_score", 0))
    details = payload.get("details") or {}

    defaults: Dict[str, Any] = {
        "ai_summary": "No summary generated.",
        "overall_skill_score": final_score,
        "experience_score": final_score,
        "project_score": final_score,
        "calculated_years": 0,
        "recent_years": None,
        "core_skill_matches": [],
        "support_skill_matches": [],
        "matched_skills": [],
        "missing_skills": [],
        "missing_optional_skills": [],
        "strengths": [],
        "risks": [],
        "recommendations": [],
        "experience_segments": [],
        "employment_gaps": [],
        "education_highlights": [],
        "certifications": [],
        "summary_highlights": [],
        "highlighted_keywords": [],
        "deep_insights": {"notable_sentences": [], "recommended_questions": []},
        "score_breakdown": {
            "core_skill": final_score,
            "domain_alignment": final_score,
            "role_alignment": final_score,
            "experience_alignment": final_score,
            "must_have_ratio": 0.0,
            "nice_to_have_ratio": 0.0,
            "bonus_or_penalty": 0.0,
            "penalties": [],
        },
        "skills_coverage_ratio": 0.0,
        "ai_assessment": {
            "final_score": final_score,
            "matched_skills": [],
            "ai_summary": details.get("ai_summary", "No summary generated."),
        },
    }

    normalised = {}
    for key, default in defaults.items():
        normalised[key] = _coerce_value(details.get(key, default), default)

    # ensure deep_insights nested defaults exist
    deep_insights = normalised["deep_insights"]
    if not isinstance(deep_insights, dict):
        deep_insights = {"notable_sentences": [], "recommended_questions": []}
    deep_insights.setdefault("notable_sentences", [])
    deep_insights.setdefault("recommended_questions", [])
    deep_insights["notable_sentences"] = _ensure_list_of_strings(deep_insights["notable_sentences"])
    deep_insights["recommended_questions"] = _ensure_list_of_strings(deep_insights["recommended_questions"])
    normalised["deep_insights"] = deep_insights

    # normalise score breakdown
    score_breakdown = normalised["score_breakdown"]
    if not isinstance(score_breakdown, dict):
        score_breakdown = defaults["score_breakdown"]
    for metric in defaults["score_breakdown"]:
        score_breakdown[metric] = _coerce_value(score_breakdown.get(metric), defaults["score_breakdown"][metric])
    score_breakdown["penalties"] = _ensure_list_of_strings(score_breakdown.get("penalties", []))
    normalised["score_breakdown"] = score_breakdown

    # ensure list fields are clean
    list_fields = [
        "core_skill_matches",
        "support_skill_matches",
        "matched_skills",
        "missing_skills",
        "missing_optional_skills",
        "strengths",
        "risks",
        "recommendations",
        "education_highlights",
        "certifications",
        "summary_highlights",
        "highlighted_keywords",
    ]
    for field in list_fields:
        normalised[field] = _ensure_list_of_strings(normalised.get(field, []))

    normalised["experience_segments"] = _normalise_segments(normalised.get("experience_segments", []))
    normalised["employment_gaps"] = _normalise_gaps(normalised.get("employment_gaps", []))

    # ai_assessment fallback
    ai_assessment = normalised.get("ai_assessment") or {}
    if not isinstance(ai_assessment, dict):
        ai_assessment = defaults["ai_assessment"]
    ai_assessment.setdefault("final_score", final_score)
    ai_assessment["final_score"] = _coerce_int(ai_assessment.get("final_score", final_score))
    ai_assessment["matched_skills"] = _ensure_list_of_strings(ai_assessment.get("matched_skills", []))
    ai_assessment["ai_summary"] = ai_assessment.get("ai_summary") or normalised["ai_summary"]
    normalised["ai_assessment"] = ai_assessment

    payload_out = {
        "final_score": final_score,
        "details": normalised,
    }
    return payload_out


def _coerce_value(value: Any, default: Any) -> Any:
    if isinstance(default, list):
        return _ensure_list_of_strings(value)
    if isinstance(default, dict):
        return value if isinstance(value, dict) else default
    if isinstance(default, (int, float)) and value is not None:
        try:
            return type(default)(value)
        except (TypeError, ValueError):
            return default
    if default is None:
        return value if value is not None else None
    return value if value is not None else default


def _ensure_list_of_strings(payload: Any) -> List[str]:
    if not isinstance(payload, list):
        if payload is None:
            return []
        if isinstance(payload, str):
            return [payload.strip()] if payload.strip() else []
        return []
    output: List[str] = []
    for item in payload:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                output.append(stripped)
    return output


def _normalise_segments(segments: Any) -> List[Dict[str, Any]]:
    if not isinstance(segments, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for item in segments:
        if not isinstance(item, dict):
            continue
        cleaned.append(
            {
                "label": str(item.get("label", "") or "").strip(),
                "company": str(item.get("company", "") or "").strip(),
                "start": str(item.get("start", "") or "").strip(),
                "end": str(item.get("end", "") or "").strip(),
                "duration_years": _coerce_float(item.get("duration_years")),
            }
        )
    return cleaned


def _normalise_gaps(gaps: Any) -> List[Dict[str, Any]]:
    if not isinstance(gaps, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for item in gaps:
        if not isinstance(item, dict):
            continue
        cleaned.append(
            {
                "start": str(item.get("start", "") or "").strip(),
                "end": str(item.get("end", "") or "").strip(),
                "months": _coerce_float(item.get("months")),
            }
        )
    return cleaned


def _coerce_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _call_llm_with_retries(
    llm_client: OpenAI,
    request_kwargs: Dict[str, Any],
    filename: str,
    max_attempts: int = 2,
) -> (str, Dict[str, Any]):
    base_messages = request_kwargs.get("messages", [])
    for attempt in range(max_attempts):
        response = llm_client.chat.completions.create(**request_kwargs)
        raw = response.choices[0].message.content or ""
        logger.debug("AI Analyzer raw response (%s, attempt %s): %s", filename, attempt + 1, raw)
        try:
            json_payload = _extract_json_from_response(raw)
            parsed = json.loads(json_payload)
            return raw, parsed
        except ValueError as exc:
            logger.warning("JSON extraction failed for %s (attempt %s): %s", filename, attempt + 1, exc)
            if attempt == max_attempts - 1:
                raise
            reminder_messages = base_messages + [
                {
                    "role": "system",
                    "content": "Reminder: respond strictly with the requested JSON object. Do not include any markdown, explanations, or surrounding text.",
                }
            ]
            request_kwargs = dict(request_kwargs)
            request_kwargs["messages"] = reminder_messages
    raise RuntimeError("LLM retry loop exhausted.")  # pragma: no cover


SECTION_PRIORITY = (
    "experience",
    "project",
    "employment",
    "work history",
    "technical",
    "technology",
    "skills",
    "summary",
    "objective",
    "profile",
)


def _prepare_resume_excerpt(resume_text: str, max_chars: int = 6000) -> str:
    if not resume_text:
        return ""
    cleaned = resume_text.strip()
    if len(cleaned) <= max_chars:
        return cleaned

    sections = re.split(r"\n{2,}", cleaned)
    prioritized: List[str] = []
    others: List[str] = []
    for section in sections:
        if not section.strip():
            continue
        first_line = section.splitlines()[0].lower()
        if any(keyword in first_line for keyword in SECTION_PRIORITY):
            prioritized.append(section.strip())
        else:
            others.append(section.strip())
    combined = "\n\n".join(prioritized + others)
    if len(combined) > max_chars:
        combined = combined[:max_chars]
    return combined


def _format_focus_list(items: List[str]) -> str:
    if not items:
        return "None specified"
    return ", ".join(items[:12])


def _keyword_hits(resume_text: str, skills: List[str]) -> Set[str]:
    hits: Set[str] = set()
    if not resume_text or not skills:
        return hits
    lowered = resume_text.lower()
    for skill in skills:
        term = skill.strip().lower()
        if not term:
            continue
        if term in lowered:
            hits.add(skill)
    return hits


def _apply_score_guards(payload: Dict[str, Any], resume_input: ResumeLLMInput) -> Dict[str, Any]:
    final_score = payload.get("final_score", 0)
    details = payload.get("details", {})

    resume_text = resume_input.resume_text.lower()
    must_hits = _keyword_hits(resume_text, resume_input.must_have_skills)
    nice_hits = _keyword_hits(resume_text, resume_input.nice_to_have_skills)

    must_have_total = len(resume_input.must_have_skills)
    coverage_ratio = (len(must_hits) / must_have_total) if must_have_total else 0.0

    if must_hits:
        merged_core = set(details.get("core_skill_matches", []))
        merged_core.update(sorted(must_hits))
        details["core_skill_matches"] = sorted(merged_core)

    support_matches = set(details.get("support_skill_matches", []))
    support_matches.update(sorted(nice_hits))
    details["support_skill_matches"] = sorted(support_matches)

    details["skills_coverage_ratio"] = coverage_ratio

    calculated_years = details.get("calculated_years", 0)
    try:
        calculated_years = float(calculated_years)
    except (TypeError, ValueError):
        calculated_years = 0.0

    summary_text = str(details.get("ai_summary", "")).lower()
    if must_have_total and coverage_ratio == 0:
        final_score = min(final_score, 5)
    if calculated_years <= 0:
        final_score = min(final_score, 5)
    if "insufficient data" in summary_text or "unable to assess" in summary_text:
        final_score = min(final_score, 5)

    payload["final_score"] = final_score
    payload["details"] = details
    return payload


def _extract_json_from_response(raw: str) -> str:
    """Best-effort extraction of a JSON object from LLM output."""
    if not raw:
        raise ValueError("Empty response from LLM.")

    text = raw.strip()
    if text.startswith("```"):
        # remove code fence markers
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    while start != -1 and end != -1 and start < end:
        candidate = text[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            end = text.rfind("}", 0, end)

    raise ValueError("LLM response did not contain a valid JSON object.")
