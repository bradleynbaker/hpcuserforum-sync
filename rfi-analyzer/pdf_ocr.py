#!/usr/bin/env python3
"""
PDF text extraction with OCR fallback.

Extracts text from a PDF the cheap way first (the embedded text layer via
`pdftotext`), and falls back to OCR (rasterize with `pdftoppm`, recognize with
`tesseract`) for scanned / image-only PDFs that have little or no text layer.

System dependencies (install once):
  Debian/Ubuntu:  apt-get install poppler-utils tesseract-ocr
  macOS (brew):   brew install poppler tesseract

Usage:
  python pdf_ocr.py document.pdf                 # print extracted text
  python pdf_ocr.py document.pdf --json          # JSON with per-page text + metadata
  python pdf_ocr.py document.pdf --force-ocr     # skip the text layer, always OCR
  python pdf_ocr.py document.pdf --dpi 400       # higher render resolution for OCR
  python pdf_ocr.py document.pdf -o out.txt      # write text to a file

As a library:
  from pdf_ocr import extract_text
  result = extract_text("document.pdf")
  print(result.text, result.method)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from glob import glob

# Below this many characters in the embedded text layer, we treat the PDF as
# scanned/image-only and fall back to OCR.
DEFAULT_TEXT_LAYER_MIN_CHARS = 100
DEFAULT_DPI = 300
DEFAULT_LANG = "eng"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class OcrResult:
    text: str                              # full extracted text (all pages joined)
    method: str                            # "text-layer" | "ocr" | "mixed"
    pages: list = field(default_factory=list)   # per-page text
    page_count: int = 0
    char_count: int = 0
    source: str = ""

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def _have(binary):
    return shutil.which(binary) is not None


def check_dependencies(need_ocr=True):
    """Return a list of missing system binaries (empty if all present)."""
    missing = []
    if not _have("pdftotext"):
        missing.append("pdftotext (poppler-utils)")
    if need_ocr:
        if not _have("pdftoppm"):
            missing.append("pdftoppm (poppler-utils)")
        if not _have("tesseract"):
            missing.append("tesseract (tesseract-ocr)")
    return missing


# ---------------------------------------------------------------------------
# Text-layer extraction (fast path)
# ---------------------------------------------------------------------------

def extract_text_layer(pdf_path):
    """Extract the embedded text layer with pdftotext. Returns text or ""."""
    if not _have("pdftotext"):
        return ""
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True, text=True, timeout=120,
        )
        return out.stdout or ""
    except (subprocess.SubprocessError, OSError) as e:
        print(f"  [pdf_ocr] pdftotext failed: {e}", file=sys.stderr)
        return ""


def page_count(pdf_path):
    """Return the number of pages via pdfinfo, or 0 if unavailable."""
    if not _have("pdfinfo"):
        return 0
    try:
        out = subprocess.run(
            ["pdfinfo", pdf_path], capture_output=True, text=True, timeout=30
        )
        for line in out.stdout.splitlines():
            if line.lower().startswith("pages:"):
                return int(line.split(":", 1)[1].strip())
    except (subprocess.SubprocessError, OSError, ValueError):
        pass
    return 0


# ---------------------------------------------------------------------------
# OCR path (rasterize + recognize)
# ---------------------------------------------------------------------------

def render_pages(pdf_path, out_dir, dpi=DEFAULT_DPI):
    """Rasterize a PDF to PNG pages with pdftoppm. Returns sorted page paths."""
    prefix = os.path.join(out_dir, "page")
    subprocess.run(
        ["pdftoppm", "-r", str(dpi), "-png", pdf_path, prefix],
        check=True, capture_output=True, timeout=600,
    )
    return sorted(glob(prefix + "*.png"))


def ocr_image(image_path, lang=DEFAULT_LANG):
    """Run tesseract on a single image and return recognized text."""
    out = subprocess.run(
        ["tesseract", image_path, "stdout", "-l", lang],
        capture_output=True, text=True, timeout=300,
    )
    return out.stdout or ""


def ocr_pdf(pdf_path, dpi=DEFAULT_DPI, lang=DEFAULT_LANG):
    """OCR every page of a PDF. Returns a list of per-page text strings."""
    pages = []
    with tempfile.TemporaryDirectory(prefix="pdf_ocr_") as tmp:
        images = render_pages(pdf_path, tmp, dpi=dpi)
        for i, img in enumerate(images, 1):
            sys.stderr.write(f"\r  [pdf_ocr] OCR page {i}/{len(images)} ...")
            sys.stderr.flush()
            pages.append(ocr_image(img, lang=lang).strip())
        if images:
            sys.stderr.write("\n")
    return pages


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def extract_text(
    pdf_path,
    force_ocr=False,
    dpi=DEFAULT_DPI,
    lang=DEFAULT_LANG,
    text_layer_min_chars=DEFAULT_TEXT_LAYER_MIN_CHARS,
):
    """
    Extract text from a PDF, OCR-ing if the text layer is thin or absent.

    Returns an OcrResult. Raises FileNotFoundError if the PDF is missing, or
    RuntimeError if required binaries for the chosen path are unavailable.
    """
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(pdf_path)

    layer_text = "" if force_ocr else extract_text_layer(pdf_path)

    if not force_ocr and len(layer_text.strip()) >= text_layer_min_chars:
        pages = layer_text.split("\f")  # pdftotext separates pages with form feed
        pages = [p.strip() for p in pages if p.strip()]
        return OcrResult(
            text=layer_text.strip(),
            method="text-layer",
            pages=pages,
            page_count=len(pages),
            char_count=len(layer_text.strip()),
            source=pdf_path,
        )

    # Fall back to OCR.
    missing = check_dependencies(need_ocr=True)
    if missing:
        raise RuntimeError(
            "OCR required but missing dependencies: " + ", ".join(missing)
        )

    pages = ocr_pdf(pdf_path, dpi=dpi, lang=lang)
    text = "\n\n".join(pages).strip()
    method = "ocr"
    # If there was *some* usable text layer, note it was a mixed extraction.
    if layer_text.strip():
        method = "mixed"
    return OcrResult(
        text=text,
        method=method,
        pages=pages,
        page_count=len(pages),
        char_count=len(text),
        source=pdf_path,
    )


def main():
    p = argparse.ArgumentParser(description="Extract text from a PDF (OCR fallback)")
    p.add_argument("pdf", help="Path to the PDF file")
    p.add_argument("--force-ocr", action="store_true",
                   help="Skip the text layer and always OCR")
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI,
                   help=f"Render resolution for OCR (default: {DEFAULT_DPI})")
    p.add_argument("--lang", default=DEFAULT_LANG,
                   help=f"Tesseract language (default: {DEFAULT_LANG})")
    p.add_argument("--json", action="store_true",
                   help="Output JSON (per-page text + metadata)")
    p.add_argument("-o", "--output", metavar="FILE",
                   help="Write extracted text to FILE instead of stdout")
    args = p.parse_args()

    missing = check_dependencies(need_ocr=True)
    if missing and not _have("pdftotext"):
        print("[pdf_ocr] Missing required dependencies:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        sys.exit(2)

    try:
        result = extract_text(
            args.pdf, force_ocr=args.force_ocr, dpi=args.dpi, lang=args.lang
        )
    except (FileNotFoundError, RuntimeError) as e:
        print(f"[pdf_ocr] Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[pdf_ocr] {result.page_count} page(s), {result.char_count} chars "
          f"via {result.method}", file=sys.stderr)

    if args.json:
        payload = json.dumps(result.to_dict(), indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(payload)
            print(f"[pdf_ocr] Wrote {args.output}", file=sys.stderr)
        else:
            print(payload)
    else:
        if args.output:
            with open(args.output, "w") as f:
                f.write(result.text)
            print(f"[pdf_ocr] Wrote {args.output}", file=sys.stderr)
        else:
            print(result.text)


if __name__ == "__main__":
    main()
