#!/usr/bin/env python3
"""
RFI Analyzer — read a government RFI/Sources-Sought PDF and extract the things
a contractor actually needs: the deadline, who to send it to, what they're
asking for, NAICS codes, page limits, and a capture-focused assessment.

It uses pdf_ocr.py to read the document (text layer or OCR for scanned PDFs),
then analyzes it two ways:

  1. Heuristics (always on, no network/key) — fast regex extraction of
     deadlines, emails, POCs, NAICS codes, page limits, etc.

  2. Claude (optional, --llm) — a structured deep analysis via the Anthropic
     API (Opus 4.8): summary, key requirements, technologies, response
     checklist, and capabilities a respondent should emphasize.

Output is a JSON record and a readable Markdown brief.

Setup:
  pip install -r requirements.txt
  apt-get install poppler-utils tesseract-ocr   # for OCR
  export ANTHROPIC_API_KEY=sk-ant-...            # only for --llm

Usage:
  python rfi_analyzer.py MAITSRFI.pdf
  python rfi_analyzer.py MAITSRFI.pdf --llm
  python rfi_analyzer.py MAITSRFI.pdf --llm --json-out rfi.json --md-out rfi.md
  python rfi_analyzer.py MAITSRFI.pdf --force-ocr --dpi 400
"""

import argparse
import json
import os
import re
import sys
from datetime import date

import pdf_ocr

MODEL = "claude-opus-4-8"


# ---------------------------------------------------------------------------
# Heuristic extraction (no API key needed)
# ---------------------------------------------------------------------------

# Common federal acquisition document types.
_DOC_TYPES = [
    ("Request for Information", r"\brequest for information\b|\bRFI\b"),
    ("Sources Sought", r"\bsources sought\b"),
    ("Request for Proposal", r"\brequest for proposal\b|\bRFP\b"),
    ("Request for Quote", r"\brequest for quote\b|\bRFQ\b"),
    ("Draft RFP", r"\bdraft RFP\b"),
]

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+~\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_NAICS_RE = re.compile(r"\bNAICS\b[^0-9]{0,40}(\d{6})", re.IGNORECASE)
_PHONE_RE = re.compile(r"\(?\b\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}\b")

# Page-limit phrasings: "no more than 20 pages", "limited to 20 pages",
# "submissions are limited to no more than 20 pages".
_PAGE_LIMIT_RE = re.compile(
    r"(?:no more than|limited to(?: no more than)?|not(?: to)? exceed(?:ing)?|maximum of)\s+"
    r"(\d{1,3})\s+pages",
    re.IGNORECASE,
)

# Deadline phrasings: "no later than Wednesday, 1 July 2026 at 1600 EST",
# "due by July 1, 2026", "responses are due ... 2026".
_MONTHS = (r"January|February|March|April|May|June|July|August|September|"
           r"October|November|December")
_DATE_PATTERNS = [
    # 1 July 2026 [at 1600 EST] — lookbehind avoids matching "1.0 October" -> "0 October"
    re.compile(
        rf"((?<![\d.])\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}}"
        rf"(?:\s+at\s+\d{{3,4}}\s*(?:hours|hrs)?\s*[A-Z]{{2,4}}T?)?)",
        re.IGNORECASE),
    # July 1, 2026 [at 4:00 PM EST]
    re.compile(
        rf"((?:{_MONTHS})\s+\d{{1,2}},?\s+\d{{4}}"
        rf"(?:\s+at\s+\d{{1,2}}:\d{{2}}\s*(?:[AP]M)?\s*[A-Z]{{2,4}}T?)?)",
        re.IGNORECASE),
    # 07/01/2026
    re.compile(r"(\d{1,2}/\d{1,2}/\d{4})"),
]

_DEADLINE_CONTEXT_RE = re.compile(
    r"(?:no later than|due (?:by|date|no later than)|received (?:no later than|by)|"
    r"submitted? (?:no later than|by)|responses?(?: are)? due|closing date|deadline)",
    re.IGNORECASE,
)

# A reasonable set of capability/technology keywords to flag for capture teams.
_TECH_KEYWORDS = [
    "AI/ML", "artificial intelligence", "machine learning", "DevSecOps", "DevOps",
    "Zero Trust", "cloud", "RMF", "Risk Management Framework", "cybersecurity",
    "Agile", "Scrum", "ETL", "data management", "microservices", "ITIL", "ITSM",
    "Platform as a Service", "PaaS", "Disaster Recovery", "COOP", "SDLC",
    "continuous integration", "continuous delivery", "containerization",
    "Kubernetes", "API", "data analytics", "automation", "modernization",
]

_AGENCY_RE = re.compile(
    r"\b("
    r"Defense Intelligence Agency|Department of Defense|Department of the Army|"
    r"Department of the Navy|Department of the Air Force|Department of War|"
    r"National Security Agency|Central Intelligence Agency|"
    r"General Services Administration|Department of Homeland Security|"
    r"Department of Veterans Affairs|Department of Energy|"
    r"National Aeronautics and Space Administration|"
    r"Defense Information Systems Agency"
    r")\b"
)

# Government-jargon abbreviations expanded inline as "Full Name (ABC)".
_ACRONYM_DEF_RE = re.compile(r"\b([A-Z][A-Za-z&/ ]{3,60}?)\s*\(([A-Z]{2,6})\)")


def _first(patterns_text, text):
    for rx in patterns_text:
        m = rx.search(text)
        if m:
            return m.group(1).strip()
    return None


def find_deadline(text):
    """Find the most likely submission deadline (date near a deadline cue)."""
    # Prefer a date that appears near a deadline cue.
    for m in _DEADLINE_CONTEXT_RE.finditer(text):
        window = text[m.start(): m.start() + 200]
        d = _first(_DATE_PATTERNS, window)
        if d:
            return d
    # Otherwise, fall back to the first future-looking date in the document.
    return _first(_DATE_PATTERNS, text)


def find_points_of_contact(text):
    """Extract named contacts like Contracting Officer / Contract Specialist."""
    pocs = []
    role_re = re.compile(
        r"(Contracting Officer|Contract Specialist|Contracting Specialist|"
        r"Point of Contact|Program Manager|Contract(?:ing)? Officer'?s? Representative)"
        r"\s+(?:is\s+)?([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)",
        re.IGNORECASE,
    )
    for m in role_re.finditer(text):
        role = re.sub(r"\s+", " ", m.group(1)).strip().title()
        name = m.group(2).strip()
        pocs.append({"role": role, "name": name})
    # Dedupe preserving order.
    seen = set()
    unique = []
    for p in pocs:
        key = (p["role"], p["name"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def find_acronyms(text, limit=40):
    found = {}
    for m in _ACRONYM_DEF_RE.finditer(text):
        full = re.sub(r"\s+", " ", m.group(1)).strip()
        abbr = m.group(2).strip()
        # Skip when the "full" text is itself just uppercase noise.
        if abbr not in found and len(full) > len(abbr):
            found[abbr] = full
    return dict(list(found.items())[:limit])


def heuristic_analysis(text):
    # OCR wraps lines mid-phrase, which breaks contextual regexes (a deadline
    # cue and its date land on different lines, a name splits across a break).
    # Run the contextual extractors on a whitespace-normalized copy.
    norm = re.sub(r"\s+", " ", text)

    doc_type = None
    for label, pat in _DOC_TYPES:
        if re.search(pat, norm):
            doc_type = label
            break

    emails = sorted(set(_EMAIL_RE.findall(norm)))
    naics = sorted(set(_NAICS_RE.findall(norm)))
    phones = sorted(set(m.group(0) for m in _PHONE_RE.finditer(norm)))
    page_limit = None
    m = _PAGE_LIMIT_RE.search(norm)
    if m:
        page_limit = int(m.group(1))

    agency = None
    am = _AGENCY_RE.search(norm)
    if am:
        agency = am.group(1)

    techs = []
    low = norm.lower()
    for kw in _TECH_KEYWORDS:
        if kw.lower() in low and kw not in techs:
            techs.append(kw)

    # Subject line, if present.
    subject = None
    sm = re.search(r"SUBJECT:\s*(.+?)(?:\n\s*\n|\n\d\.\s)", text,
                   re.IGNORECASE | re.DOTALL)
    if sm:
        subject = re.sub(r"\s+", " ", sm.group(1)).strip()

    return {
        "document_type": doc_type,
        "issuing_agency": agency,
        "subject": subject,
        "response_deadline": find_deadline(norm),
        "submission_emails": emails,
        "points_of_contact": find_points_of_contact(norm),
        "phones": phones,
        "naics_codes": naics,
        "page_limit": page_limit,
        "technologies_mentioned": techs,
        "acronyms": find_acronyms(norm),
    }


# ---------------------------------------------------------------------------
# Claude-powered deep analysis (optional)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a federal capture and proposal analyst. You read government "
    "solicitation documents (RFIs, Sources Sought notices, RFPs) and extract "
    "structured intelligence for a contractor deciding whether and how to "
    "respond. Be precise and factual. Pull dates, names, and codes verbatim "
    "from the document. When a field is not stated, return an empty string or "
    "empty list rather than guessing. The capture-analysis fields "
    "(capabilities_to_highlight, risks_and_notes) are your professional "
    "assessment grounded in the document's stated scope."
)

# JSON schema for structured output. Kept flat and additionalProperties:false
# per the structured-outputs requirements.
_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string"},
        "issuing_agency": {"type": "string"},
        "title": {"type": "string"},
        "summary": {"type": "string", "description": "2-4 sentence plain-English summary"},
        "response_deadline": {"type": "string", "description": "Date, time, and timezone, verbatim"},
        "submission_method": {"type": "string", "description": "Email / portal / mail, with the address"},
        "points_of_contact": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                },
                "required": ["name", "role", "email", "phone"],
                "additionalProperties": False,
            },
        },
        "naics_codes": {"type": "array", "items": {"type": "string"}},
        "page_limit": {"type": "string"},
        "format_requirements": {"type": "string", "description": "Fonts, margins, page size, copies"},
        "set_aside_or_business_size": {"type": "string"},
        "funding_or_period": {"type": "string", "description": "e.g. FY27-31 funding, contract length"},
        "bidders_conference": {"type": "string", "description": "Whether one is planned, with details"},
        "key_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The scope of work / capabilities the government wants",
        },
        "technologies": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific technologies, methodologies, or frameworks named",
        },
        "required_response_elements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What a respondent must include (company info, POC, size, etc.)",
        },
        "key_dates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["label", "date"],
                "additionalProperties": False,
            },
        },
        "capabilities_to_highlight": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Analyst recommendation: what a strong response should emphasize",
        },
        "risks_and_notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Caveats, e.g. 'not a commitment to award', classification handling",
        },
    },
    "required": [
        "document_type", "issuing_agency", "title", "summary",
        "response_deadline", "submission_method", "points_of_contact",
        "naics_codes", "page_limit", "format_requirements",
        "set_aside_or_business_size", "funding_or_period", "bidders_conference",
        "key_requirements", "technologies", "required_response_elements",
        "key_dates", "capabilities_to_highlight", "risks_and_notes",
    ],
    "additionalProperties": False,
}


def llm_analysis(text):
    """Run a structured analysis via the Anthropic API. Returns a dict or None."""
    try:
        import anthropic
    except ImportError:
        print("[rfi_analyzer] --llm requires the 'anthropic' package "
              "(pip install anthropic).", file=sys.stderr)
        return None

    if not (os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("[rfi_analyzer] --llm requires ANTHROPIC_API_KEY in the "
              "environment.", file=sys.stderr)
        return None

    client = anthropic.Anthropic()
    user_content = (
        "Analyze the following government solicitation document and return the "
        "structured fields. Quote dates, names, emails, and codes exactly as "
        "they appear.\n\n=== DOCUMENT START ===\n"
        + text
        + "\n=== DOCUMENT END ==="
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high",
                           "format": {"type": "json_schema",
                                      "schema": _ANALYSIS_SCHEMA}},
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.APIError as e:
        print(f"[rfi_analyzer] Anthropic API error: {e}", file=sys.stderr)
        return None

    if response.stop_reason == "refusal":
        print("[rfi_analyzer] Model declined to analyze this document.",
              file=sys.stderr)
        return None

    raw = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("[rfi_analyzer] Could not parse model output as JSON.",
              file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _md_list(items):
    if not items:
        return "_None found._\n"
    return "".join(f"- {i}\n" for i in items)


def build_markdown(record):
    h = record["heuristics"]
    llm = record.get("llm")
    meta = record["extraction"]
    src = os.path.basename(record["source"])

    lines = [f"# RFI Analysis — {src}", ""]
    lines.append(f"_Extracted via **{meta['method']}** "
                 f"({meta['page_count']} pages, {meta['char_count']} chars). "
                 f"Generated {date.today().isoformat()}._")
    lines.append("")

    # Prefer LLM values where available, fall back to heuristics.
    def pick(llm_key, heur_val):
        if llm and llm.get(llm_key):
            return llm[llm_key]
        return heur_val

    lines.append("## At a glance")
    lines.append("")
    lines.append(f"- **Document type:** {pick('document_type', h['document_type']) or '—'}")
    lines.append(f"- **Issuing agency:** {pick('issuing_agency', h['issuing_agency']) or '—'}")
    title = pick("title", h["subject"])
    lines.append(f"- **Title/subject:** {title or '—'}")
    lines.append(f"- **Response deadline:** {pick('response_deadline', h['response_deadline']) or '—'}")
    page_limit = (llm.get("page_limit") if llm else None) or (
        f"{h['page_limit']} pages" if h["page_limit"] else None)
    lines.append(f"- **Page limit:** {page_limit or '—'}")
    naics = pick("naics_codes", h["naics_codes"])
    lines.append(f"- **NAICS codes:** {', '.join(naics) if naics else '—'}")
    if llm and llm.get("submission_method"):
        lines.append(f"- **Submission:** {llm['submission_method']}")
    elif h["submission_emails"]:
        lines.append(f"- **Submission emails:** {', '.join(h['submission_emails'])}")
    if llm and llm.get("funding_or_period"):
        lines.append(f"- **Funding/period:** {llm['funding_or_period']}")
    lines.append("")

    if llm and llm.get("summary"):
        lines.append("## Summary")
        lines.append("")
        lines.append(llm["summary"])
        lines.append("")

    # Points of contact
    pocs = (llm.get("points_of_contact") if llm else None) or [
        {"name": p["name"], "role": p["role"], "email": "", "phone": ""}
        for p in h["points_of_contact"]
    ]
    if pocs:
        lines.append("## Points of contact")
        lines.append("")
        for p in pocs:
            bits = [p.get("name", "").strip(), f"({p.get('role','').strip()})"]
            extra = ", ".join(x for x in (p.get("email", ""), p.get("phone", "")) if x)
            line = " ".join(b for b in bits if b.strip("()"))
            if extra:
                line += f" — {extra}"
            lines.append(f"- {line}")
        lines.append("")

    if llm:
        lines.append("## Key requirements / scope")
        lines.append("")
        lines.append(_md_list(llm.get("key_requirements")))
        lines.append("## Technologies & methodologies")
        lines.append("")
        lines.append(_md_list(llm.get("technologies") or h["technologies_mentioned"]))
        lines.append("## What your response must include")
        lines.append("")
        lines.append(_md_list(llm.get("required_response_elements")))
        if llm.get("key_dates"):
            lines.append("## Key dates")
            lines.append("")
            for d in llm["key_dates"]:
                lines.append(f"- **{d.get('label','')}:** {d.get('date','')}")
            lines.append("")
        if llm.get("format_requirements"):
            lines.append("## Format requirements")
            lines.append("")
            lines.append(llm["format_requirements"])
            lines.append("")
        if llm.get("bidders_conference"):
            lines.append(f"**Bidders conference:** {llm['bidders_conference']}\n")
        if llm.get("set_aside_or_business_size"):
            lines.append(f"**Set-aside / business size:** {llm['set_aside_or_business_size']}\n")
        lines.append("## Capabilities to highlight (analyst view)")
        lines.append("")
        lines.append(_md_list(llm.get("capabilities_to_highlight")))
        lines.append("## Risks & notes")
        lines.append("")
        lines.append(_md_list(llm.get("risks_and_notes")))
    else:
        lines.append("## Technologies & methodologies mentioned")
        lines.append("")
        lines.append(_md_list(h["technologies_mentioned"]))
        lines.append("")
        lines.append("> Run again with `--llm` (and `ANTHROPIC_API_KEY` set) for a "
                     "full capture analysis: summary, scope, response checklist, "
                     "and capabilities to highlight.")
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def analyze(pdf_path, use_llm=False, force_ocr=False, dpi=pdf_ocr.DEFAULT_DPI,
            lang=pdf_ocr.DEFAULT_LANG):
    ocr = pdf_ocr.extract_text(pdf_path, force_ocr=force_ocr, dpi=dpi, lang=lang)
    record = {
        "source": pdf_path,
        "extraction": {
            "method": ocr.method,
            "page_count": ocr.page_count,
            "char_count": ocr.char_count,
        },
        "heuristics": heuristic_analysis(ocr.text),
        "text": ocr.text,
    }
    if use_llm:
        record["llm"] = llm_analysis(ocr.text)
    return record


def main():
    p = argparse.ArgumentParser(
        description="Analyze a government RFI/Sources-Sought PDF (with OCR)."
    )
    p.add_argument("pdf", help="Path to the RFI PDF")
    p.add_argument("--llm", action="store_true",
                   help="Run a deep analysis via the Anthropic API (needs ANTHROPIC_API_KEY)")
    p.add_argument("--force-ocr", action="store_true",
                   help="Skip the text layer and always OCR")
    p.add_argument("--dpi", type=int, default=pdf_ocr.DEFAULT_DPI,
                   help=f"OCR render resolution (default: {pdf_ocr.DEFAULT_DPI})")
    p.add_argument("--lang", default=pdf_ocr.DEFAULT_LANG,
                   help=f"Tesseract language (default: {pdf_ocr.DEFAULT_LANG})")
    p.add_argument("--json-out", metavar="FILE", help="Write the JSON record to FILE")
    p.add_argument("--md-out", metavar="FILE", help="Write the Markdown brief to FILE")
    p.add_argument("--include-text", action="store_true",
                   help="Keep the full extracted text in the JSON output")
    args = p.parse_args()

    missing = pdf_ocr.check_dependencies(need_ocr=True)
    if "pdftotext (poppler-utils)" in missing:
        print("[rfi_analyzer] pdftotext is required. Install poppler-utils.",
              file=sys.stderr)
        sys.exit(2)

    try:
        record = analyze(args.pdf, use_llm=args.llm, force_ocr=args.force_ocr,
                         dpi=args.dpi, lang=args.lang)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"[rfi_analyzer] Error: {e}", file=sys.stderr)
        sys.exit(1)

    markdown = build_markdown(record)

    if not args.include_text:
        record = {k: v for k, v in record.items() if k != "text"}

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(record, f, indent=2)
        print(f"[rfi_analyzer] Wrote {args.json_out}", file=sys.stderr)
    if args.md_out:
        with open(args.md_out, "w") as f:
            f.write(markdown)
        print(f"[rfi_analyzer] Wrote {args.md_out}", file=sys.stderr)

    # Always print the brief to stdout so the tool is useful with no flags.
    print(markdown)


if __name__ == "__main__":
    main()
