# RFI Analyzer

Read a government **RFI / Sources Sought / RFP** — including scanned, image-only
PDFs — and pull out what a contractor actually has to act on: the response
deadline, who to send it to, the scope of work, NAICS codes, page limits, and a
capture-focused view of what to emphasize.

Built because the useful parts of a solicitation are often locked inside a
600-page scan with no text layer.

```bash
python rfi_analyzer.py SOLICITATION.pdf              # heuristics only, offline
python rfi_analyzer.py SOLICITATION.pdf --llm        # + Claude deep analysis
```

## What's in the box

| File | What it does |
|------|--------------|
| `pdf_ocr.py` | PDF text extraction. Uses the embedded text layer when there is one, falls back to OCR (Tesseract) when there isn't. |
| `docx_text.py` | `.docx` text extraction, stdlib only — no `python-docx` dependency. |
| `rfi_analyzer.py` | Runs extraction, then analyzes: heuristically always, with Claude optionally. Emits JSON + a Markdown brief. |
| `ocr_server.py` | Optional HTTP service (stdlib only) exposing extraction and analysis over `/ocr` and `/analyze`. |

## Install

```bash
pip install -r requirements.txt

# System tools for OCR (needed only for scanned PDFs):
apt-get install poppler-utils tesseract-ocr    # Debian/Ubuntu
brew install poppler tesseract                 # macOS

# Needed only for --llm:
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
# Heuristics — no API key, no network. Prints a Markdown brief.
python rfi_analyzer.py MAITSRFI.pdf

# Deep analysis via Claude: summary, scope, response checklist,
# capabilities to highlight, risks.
python rfi_analyzer.py MAITSRFI.pdf --llm

# Save structured outputs
python rfi_analyzer.py MAITSRFI.pdf --llm --json-out rfi.json --md-out rfi.md

# Force OCR (skip the text layer) at higher resolution for a poor scan
python rfi_analyzer.py MAITSRFI.pdf --force-ocr --dpi 400
```

`pdf_ocr.py` and `docx_text.py` are usable on their own for any PDF/DOCX → text job:

```bash
python pdf_ocr.py document.pdf --json -o out.json
python docx_text.py document.docx
```

```python
from pdf_ocr import extract_text
result = extract_text("document.pdf")   # OcrResult(text, method, pages, ...)
```

## HTTP server

```bash
python ocr_server.py                      # 127.0.0.1:8000
python ocr_server.py --host 0.0.0.0 --port 9000
```

| Route | Method | Returns |
|-------|--------|---------|
| `/health` | GET | Status + which OCR binaries are present |
| `/ocr` | POST | Extracted text |
| `/analyze` | POST | Full analysis + a Markdown brief |

Send the document as the **raw request body**:

```bash
curl -s --data-binary @RFI.pdf -H 'Content-Type: application/pdf' \
     http://127.0.0.1:8000/analyze | jq .
```

Query params — `/ocr`: `force_ocr=1`, `dpi=300`, `lang=eng`.
`/analyze` also takes `llm=1`, `include_text=1`.

### Docker

The bundled `Dockerfile` installs poppler + tesseract and binds `0.0.0.0:8000`:

```bash
docker build -t rfi-ocr .
docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... rfi-ocr
```

> Running `ocr_server.py` bare binds to `127.0.0.1` (local only). Use
> `--host 0.0.0.0` — as the image does — to accept outside connections.

## How extraction works

1. **Text layer first.** `pdftotext -layout` is fast and exact.
2. **OCR fallback.** If the text layer is thin or absent (< 100 chars — i.e. a
   scan), each page is rasterized with `pdftoppm` and read with `tesseract`.

The `method` field in the output says which path ran: `text-layer`, `ocr`, or
`mixed`.

## What the analysis extracts

**Heuristics (always on):** document type, issuing agency, subject, response
deadline, submission emails, points of contact, phone numbers, NAICS codes, page
limit, technologies mentioned, and a glossary of acronyms defined inline.

**Claude (`--llm`):** all of the above plus a plain-English summary, the full
scope list, a "what your response must include" checklist, key dates, format
requirements, set-aside notes, funding/period, capabilities to highlight, and
risks. Returned as schema-validated JSON and folded into the Markdown brief.

## Known limits

- Heuristic extraction is best-effort regex over OCR text, and OCR introduces
  artifacts. **Always verify the deadline and submission address against the
  source document** before relying on them.
- Two known extraction bugs, both covered by `xfail` tests in `tests/` and
  both good first contributions:
  - **Document type is matched case-sensitively.** The `_DOC_TYPES` phrase
    patterns are lowercase and matched without `re.IGNORECASE`, so only
    all-lowercase prose matches. Both `Request for Information` and
    `REQUEST FOR INFORMATION` — the Title Case and ALL-CAPS forms that real
    solicitations actually use — return `None`. Bare acronyms like `RFI` still
    match, because those alternatives are literal uppercase.
  - **Acronym capture is greedy.** The pattern's character class includes
    spaces, so it swallows preceding capitalised words: `... INFORMATION Defense
    Intelligence Agency (DIA)` maps `DIA` to the whole run.
- Encrypted or password-protected PDFs are not handled.
- `--llm` sends document text to the Anthropic API. Don't point it at material
  you aren't cleared to send to a third party. See [SECURITY.md](SECURITY.md).
- The tool reads documents. It does not submit anything anywhere.

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
Good first contributions: new agency patterns, deadline phrasings we miss, and
extraction test cases from real solicitation formats.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
