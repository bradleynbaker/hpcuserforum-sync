# RFI Analyzer

Read a government **RFI / Sources Sought / RFP** PDF — including scanned,
image-only PDFs — and pull out the things a contractor actually needs to act
on: the response deadline, who to send it to, the scope of work, NAICS codes,
page limits, and a capture-focused assessment of what to emphasize.

Two pieces:

| File | What it does |
|------|--------------|
| `pdf_ocr.py` | Reusable PDF text extraction. Uses the embedded text layer when present, falls back to OCR (Tesseract) for scanned documents. |
| `rfi_analyzer.py` | Runs the OCR, then analyzes the RFI — heuristically (always) and with Claude (optionally). Emits JSON + a Markdown brief. |
| `ocr_server.py` | Optional HTTP service (stdlib only) exposing the OCR + analysis over `/ocr` and `/analyze`. |

## Install

```bash
pip install -r requirements.txt

# System tools for OCR (required to read scanned PDFs):
#   Debian/Ubuntu
apt-get install poppler-utils tesseract-ocr
#   macOS
brew install poppler tesseract

# Only needed for the --llm deep analysis:
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
# Heuristic analysis — no API key, no network. Prints a Markdown brief.
python rfi_analyzer.py MAITSRFI.pdf

# Deep analysis via Claude (Opus 4.8): summary, scope, response checklist,
# capabilities to highlight, risks.
python rfi_analyzer.py MAITSRFI.pdf --llm

# Save structured outputs
python rfi_analyzer.py MAITSRFI.pdf --llm --json-out rfi.json --md-out rfi.md

# Force OCR (skip the text layer) at higher resolution for poor scans
python rfi_analyzer.py MAITSRFI.pdf --force-ocr --dpi 400
```

`pdf_ocr.py` is usable on its own for any PDF → text job:

```bash
python pdf_ocr.py document.pdf                # print text
python pdf_ocr.py document.pdf --json -o out.json
python pdf_ocr.py document.pdf --force-ocr --dpi 400
```

```python
from pdf_ocr import extract_text
result = extract_text("document.pdf")   # OcrResult(text, method, pages, ...)
```

## HTTP server

For a running service (e.g. to OCR/analyze PDFs from another app), start the
stdlib server — no extra dependencies:

```bash
python ocr_server.py                      # 127.0.0.1:8000
python ocr_server.py --host 0.0.0.0 --port 9000
```

| Route | Method | Returns |
|-------|--------|---------|
| `/health` | GET | Status + which OCR binaries are present |
| `/ocr` | POST | Extracted text (text layer or OCR fallback) |
| `/analyze` | POST | Full RFI analysis + a Markdown brief |

Send the PDF as the **raw request body**:

```bash
curl -s --data-binary @MAITSRFI.pdf \
     -H 'Content-Type: application/pdf' \
     http://127.0.0.1:8000/analyze | jq .
```

Query params — `/ocr`: `force_ocr=1`, `dpi=300`, `lang=eng`.
`/analyze`: also `llm=1`, `include_text=1`.

## How extraction works

1. **Text layer first.** `pdftotext -layout` is fast and exact. If the PDF
   has a real text layer, that's used.
2. **OCR fallback.** If the text layer is thin or absent (< 100 chars — i.e. a
   scan), each page is rasterized with `pdftoppm` and read with `tesseract`.
   The `method` field in the output tells you which path ran
   (`text-layer`, `ocr`, or `mixed`).

The attached DIA MAITS RFI, for example, is an image-only PDF with **no text
layer**, so it goes through OCR automatically.

## What the analysis extracts

**Heuristics (always on):** document type, issuing agency, subject/title,
response deadline, submission email(s), points of contact (Contracting
Officer, Contract Specialist, etc.), phone numbers, NAICS codes, page limit,
technologies/methodologies mentioned, and a glossary of defined acronyms.

**Claude (`--llm`):** everything above plus a plain-English summary, the full
key-requirements / scope list, a "what your response must include" checklist,
key dates, format requirements, set-aside/business-size notes,
funding/period, **capabilities to highlight** (analyst recommendation), and
**risks & notes**. Returned as structured JSON (validated against a schema)
and folded into the Markdown brief.

## Notes

- Heuristic extraction is best-effort regex over OCR text. OCR can introduce
  small artifacts (e.g. a leading character misread); the `--llm` pass and a
  human reviewer catch these. Always verify the deadline and submission
  address against the source PDF before relying on them.
- The tool reads documents only — it does not submit anything.
