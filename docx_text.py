#!/usr/bin/env python3
"""
DOCX text extraction (stdlib only).

A .docx is a zip of XML. This pulls the readable text out of the main
document, headers, and footers without any third-party dependency, preserving
paragraph and table-cell breaks well enough for downstream analysis.

Usage:
  python docx_text.py file.docx           # print text
  python docx_text.py file.docx -o out.txt

As a library:
  from docx_text import extract_docx_text
  text = extract_docx_text("file.docx")
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _para_text(paragraph):
    """Join the text runs of one <w:p>, honoring tabs and line breaks."""
    parts = []
    for node in paragraph.iter():
        tag = node.tag
        if tag == _W + "t":
            parts.append(node.text or "")
        elif tag == _W + "tab":
            parts.append("\t")
        elif tag in (_W + "br", _W + "cr"):
            parts.append("\n")
    return "".join(parts)


def _xml_text(xml_bytes):
    """Extract paragraph-separated text from one document-part XML blob."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""
    lines = []
    for p in root.iter(_W + "p"):
        line = _para_text(p).rstrip()
        lines.append(line)
    return "\n".join(lines)


def extract_docx_text(path):
    """Return the readable text of a .docx (body + headers + footers)."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        chunks = []
        if "word/document.xml" in names:
            chunks.append(_xml_text(z.read("word/document.xml")))
        # Headers/footers carry contract IDs, page footers, revision marks.
        for name in sorted(names):
            if re.match(r"word/(header|footer)\d*\.xml$", name):
                t = _xml_text(z.read(name)).strip()
                if t:
                    chunks.append(t)
    text = "\n".join(c for c in chunks if c)
    # Collapse runs of blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    p = argparse.ArgumentParser(description="Extract text from a .docx file")
    p.add_argument("docx", help="Path to the .docx file")
    p.add_argument("-o", "--output", metavar="FILE",
                   help="Write text to FILE instead of stdout")
    args = p.parse_args()

    try:
        text = extract_docx_text(args.docx)
    except (FileNotFoundError, zipfile.BadZipFile) as e:
        print(f"[docx_text] Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w") as f:
            f.write(text)
        print(f"[docx_text] Wrote {args.output} ({len(text)} chars)",
              file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
