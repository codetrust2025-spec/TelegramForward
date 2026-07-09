"""Ollama-powered resume PDF extraction.

Extracts structured candidate profile data from uploaded PDF resumes:
  - candidate_name
  - phone
  - email
  - technology (primary skill / tech stack)
  - years_of_experience
  - current_company
  - skills (list)
  - education
  - summary (2-3 line professional summary)

Flow:
  1. Extract text from PDF using PyPDF2/pdfplumber
  2. Send raw text to qwen2.5:7b (fast text model, ~10-30s) for structured extraction
  3. If text extraction fails (scanned PDF), convert pages to images and use qwen2.5vl:7b vision
  4. Return structured JSON with candidate profile data

Ollama runs on developer's laptop, tunneled to VPS via SSH.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import date
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_REASONING_MODEL = os.environ.get("OLLAMA_REASONING_MODEL", "qwen2.5:7b")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
OLLAMA_TEXT_TIMEOUT = int(os.environ.get("OLLAMA_TEXT_TIMEOUT", "60"))
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "900"))


# ── Prompt ──────────────────────────────────────────────────────────────────
RESUME_EXTRACTION_PROMPT = """You are a resume parsing assistant for an IT staffing company in India.
Extract candidate profile data from the following resume text.

Return ONLY valid JSON. Do not explain. Do not use markdown. Do not wrap JSON in code blocks.

Schema:
{{"candidate_name": "", "phone": "", "email": "", "technology": "", "years_of_experience": "", "current_company": "", "current_designation": "", "location": "", "skills": [], "education": "", "certifications": [], "summary": "", "confidence_score": 0}}

Rules:
- "candidate_name": Full name of the candidate
- "phone": Indian mobile number (10 digits) if found, else ""
- "email": Email address if found
- "technology": The PRIMARY technology/skill (e.g., "SAP BASIS", "React JS", "AWS", "Java", ".NET", "Python", "DevOps", "Salesforce"). Pick the most prominent one.
- "years_of_experience": Total years as a string (e.g., "5", "3.5", "10+"). If not explicit, estimate from work history dates.
- "current_company": Most recent employer
- "current_designation": Current job title/role
- "location": City, State if found
- "skills": Array of technical skills (max 10 most relevant)
- "education": Highest degree + institution (e.g., "B.Tech CS - JNTU Hyderabad")
- "certifications": Array of certifications (e.g., ["AWS SAA", "Azure AZ-900"])
- "summary": 1-2 sentence professional summary
- "confidence_score": 0-100 based on how complete the extraction is

Resume text:
---
{resume_text}
---
"""


# ── Empty result ────────────────────────────────────────────────────────────
def _empty_extraction() -> dict[str, Any]:
    return {
        "candidate_name": "",
        "phone": "",
        "email": "",
        "technology": "",
        "years_of_experience": "",
        "current_company": "",
        "current_designation": "",
        "location": "",
        "skills": [],
        "education": "",
        "certifications": [],
        "summary": "",
        "confidence_score": 0,
        "extraction_source": "",
        "extraction_method": "",
        "primary_model": "",
        "is_resume": False,
    }


# ── Ollama helpers ──────────────────────────────────────────────────────────
def _is_ollama_available() -> bool:
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def _call_text_model(prompt: str, *, timeout: int = OLLAMA_TEXT_TIMEOUT) -> str | None:
    try:
        payload = {
            "model": OLLAMA_REASONING_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2048},
        }
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return content.strip() if content else None
        return None
    except Exception as exc:
        logger.warning("Text model error: %s", exc)
        return None


def _call_vision_model(image_base64: str, prompt: str, *, timeout: int = OLLAMA_TIMEOUT) -> str | None:
    try:
        payload = {
            "model": OLLAMA_VISION_MODEL,
            "messages": [
                {"role": "user", "content": prompt, "images": [image_base64]}
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2048},
        }
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return content.strip() if content else None
        return None
    except Exception as exc:
        logger.warning("Vision model error: %s", exc)
        return None


# ── JSON parsing ────────────────────────────────────────────────────────────
def _parse_json_response(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    text = raw.strip()
    # Strip markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    # Find JSON object
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    # Try more aggressive JSON extraction for nested arrays
    start = text.find('{')
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        result = json.loads(text[start:i+1])
                        if isinstance(result, dict):
                            return result
                    except json.JSONDecodeError:
                        pass
                    break
    return None


# ── PDF text extraction ─────────────────────────────────────────────────────
def _extract_text_from_pdf(pdf_data: bytes) -> str | None:
    """Extract text from a PDF using available libraries."""
    # Try pdfplumber first (best quality)
    try:
        import pdfplumber
        import io
        text_parts = []
        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            for page in pdf.pages[:10]:  # Max 10 pages
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("pdfplumber failed: %s", exc)

    # Try PyPDF2
    try:
        import PyPDF2
        import io
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
        text_parts = []
        for page in reader.pages[:10]:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("PyPDF2 failed: %s", exc)

    # Try pymupdf (fitz)
    try:
        import fitz
        import io
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        text_parts = []
        for page in doc[:10]:
            page_text = page.get_text()
            if page_text:
                text_parts.append(page_text)
        doc.close()
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("pymupdf failed: %s", exc)

    return None


def _pdf_first_page_to_image(pdf_data: bytes) -> str | None:
    """Convert first page of PDF to base64 image for vision model (fallback for scanned PDFs)."""
    try:
        import fitz
        import base64
        import io
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        page = doc[0]
        # Render at 2x for better OCR
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        doc.close()
        return base64.b64encode(img_data).decode("utf-8")
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("PDF to image failed: %s", exc)
    return None


# ── Regex fallback extraction ───────────────────────────────────────────────
def _regex_extract_from_text(text: str) -> dict[str, Any]:
    """Basic regex extraction when AI is unavailable."""
    result = _empty_extraction()
    if not text:
        return result

    # Phone number (Indian 10-digit)
    phone_match = re.search(r'(?:\+91[\s\-]?)?([6-9]\d{9})', text)
    if phone_match:
        result["phone"] = phone_match.group(1)

    # Email
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    if email_match:
        result["email"] = email_match.group(0)

    # Common technologies
    tech_keywords = [
        "SAP BASIS", "SAP HANA", "SAP FICO", "SAP MM", "SAP SD", "SAP ABAP",
        "React", "Angular", "Vue", "Node.js", "Python", "Java", "C#", ".NET",
        "AWS", "Azure", "GCP", "DevOps", "Docker", "Kubernetes",
        "Salesforce", "ServiceNow", "Workday", "Oracle", "SQL Server",
        "Data Engineer", "Machine Learning", "AI/ML", "Full Stack",
        "iOS", "Android", "Flutter", "React Native",
    ]
    text_lower = text.lower()
    for tech in tech_keywords:
        if tech.lower() in text_lower:
            result["technology"] = tech
            break

    # Years of experience
    exp_match = re.search(r'(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)', text, re.IGNORECASE)
    if exp_match:
        result["years_of_experience"] = exp_match.group(1)

    result["extraction_source"] = "regex_only"
    result["extraction_method"] = "regex_fallback"
    result["is_resume"] = bool(result["phone"] or result["email"] or result["technology"])
    result["confidence_score"] = sum(10 for f in ["phone", "email", "technology", "years_of_experience"] if result.get(f))
    return result


# ── Main extraction function ────────────────────────────────────────────────
def extract_resume_with_ollama(
    pdf_data: bytes,
    mime_type: str = "application/pdf",
) -> dict[str, Any]:
    """Extract candidate profile from a PDF resume using hybrid text + AI approach.

    Flow:
      1. Extract text from PDF (pdfplumber/PyPDF2/pymupdf)
      2. If text found, send to qwen2.5:7b text model (~10-30s)
      3. If no text (scanned PDF), render first page to image → qwen2.5vl:7b vision
      4. If AI unavailable, fall back to regex extraction

    Returns structured dict with candidate_name, technology, phone, etc.
    """
    # ── Step 1: Extract text from PDF ───────────────────────────────────────
    pdf_text = _extract_text_from_pdf(pdf_data)

    if pdf_text and len(pdf_text.strip()) > 50:
        logger.info("PDF text extracted: %d chars", len(pdf_text))

        # Try regex first (instant) — gives us a baseline
        regex_result = _regex_extract_from_text(pdf_text)

        # ── Step 2: AI text model extraction ────────────────────────────────
        if _is_ollama_available():
            logger.info("Sending resume text to %s", OLLAMA_REASONING_MODEL)
            start = time.time()
            prompt = RESUME_EXTRACTION_PROMPT.format(
                resume_text=pdf_text[:6000]  # Limit to avoid token overflow
            )
            response = _call_text_model(prompt, timeout=OLLAMA_TEXT_TIMEOUT)
            elapsed = time.time() - start
            logger.info("Text model responded in %.1fs", elapsed)

            if response:
                parsed = _parse_json_response(response)
                if parsed and parsed.get("candidate_name"):
                    result = _empty_extraction()
                    result.update(parsed)
                    result["extraction_source"] = "pdf_text_ai"
                    result["extraction_method"] = "hybrid_fast"
                    result["primary_model"] = OLLAMA_REASONING_MODEL
                    result["is_resume"] = True
                    # Ensure skills is a list
                    if isinstance(result.get("skills"), str):
                        result["skills"] = [s.strip() for s in result["skills"].split(",") if s.strip()]
                    if isinstance(result.get("certifications"), str):
                        result["certifications"] = [c.strip() for c in result["certifications"].split(",") if c.strip()]
                    # Normalize confidence
                    try:
                        result["confidence_score"] = max(0, min(100, int(result.get("confidence_score", 0))))
                    except (ValueError, TypeError):
                        result["confidence_score"] = 70
                    logger.info(
                        "AI extracted: name=%s, tech=%s, exp=%s",
                        result["candidate_name"],
                        result["technology"],
                        result["years_of_experience"],
                    )
                    return result

        # AI unavailable or failed — return regex result
        return regex_result

    # ── Step 3: Scanned PDF — try vision model ──────────────────────────────
    logger.info("PDF text extraction failed or too short, trying vision model")

    if not _is_ollama_available():
        logger.info("Ollama not available for vision fallback")
        result = _empty_extraction()
        result["extraction_source"] = "failed"
        result["extraction_method"] = "no_text_no_ai"
        result["confidence_score"] = 0
        return result

    # Convert first page to image
    img_b64 = _pdf_first_page_to_image(pdf_data)
    if not img_b64:
        logger.warning("Could not convert PDF to image for vision model")
        result = _empty_extraction()
        result["extraction_source"] = "failed"
        result["extraction_method"] = "pdf_to_image_failed"
        return result

    # Call vision model
    vision_prompt = RESUME_EXTRACTION_PROMPT.format(resume_text="[Image of resume page attached]")
    logger.info("Calling vision model for scanned resume")
    start = time.time()
    response = _call_vision_model(img_b64, vision_prompt, timeout=OLLAMA_TIMEOUT)
    elapsed = time.time() - start
    logger.info("Vision model responded in %.1fs", elapsed)

    if response:
        parsed = _parse_json_response(response)
        if parsed and parsed.get("candidate_name"):
            result = _empty_extraction()
            result.update(parsed)
            result["extraction_source"] = "scanned_pdf_vision"
            result["extraction_method"] = "vision"
            result["primary_model"] = OLLAMA_VISION_MODEL
            result["is_resume"] = True
            if isinstance(result.get("skills"), str):
                result["skills"] = [s.strip() for s in result["skills"].split(",") if s.strip()]
            if isinstance(result.get("certifications"), str):
                result["certifications"] = [c.strip() for c in result["certifications"].split(",") if c.strip()]
            try:
                result["confidence_score"] = max(0, min(100, int(result.get("confidence_score", 0))))
            except (ValueError, TypeError):
                result["confidence_score"] = 60
            return result

    # Everything failed
    result = _empty_extraction()
    result["extraction_source"] = "failed"
    result["extraction_method"] = "all_failed"
    return result
