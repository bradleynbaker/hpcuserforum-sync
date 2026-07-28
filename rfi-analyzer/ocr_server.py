#!/usr/bin/env python3
"""
OCR server — a small HTTP service over pdf_ocr.py and rfi_analyzer.py.

Dependency-free (Python stdlib only). Wraps the same extraction and analysis
used by the CLIs so a PDF can be OCR'd or analyzed over HTTP.

Run:
  python ocr_server.py                 # listen on 127.0.0.1:8000
  python ocr_server.py --port 9000 --host 0.0.0.0

Endpoints:
  GET  /health                 -> {"status": "ok", "dependencies": {...}}
  POST /ocr                    -> extract text (text layer or OCR fallback)
  POST /analyze                -> RFI analysis (heuristics; ?llm=1 for Claude)

Send the PDF as the raw request body:
  curl -s --data-binary @MAITSRFI.pdf \
       -H 'Content-Type: application/pdf' \
       http://127.0.0.1:8000/analyze | jq .

Query params:
  /ocr:      force_ocr=1, dpi=300, lang=eng
  /analyze:  llm=1, force_ocr=1, dpi=300, lang=eng, include_text=1
"""

import argparse
import json
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pdf_ocr
import rfi_analyzer

MAX_BODY_BYTES = 64 * 1024 * 1024  # 64 MB cap


def _truthy(qs, key):
    v = qs.get(key, ["0"])[0].lower()
    return v in ("1", "true", "yes", "on")


def _int(qs, key, default):
    try:
        return int(qs.get(key, [str(default)])[0])
    except (ValueError, IndexError):
        return default


def _str(qs, key, default):
    return qs.get(key, [default])[0]


class Handler(BaseHTTPRequestHandler):
    server_version = "OCRServer/1.0"

    # ---- helpers -------------------------------------------------------

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_pdf_body(self):
        """Read the request body to a temp .pdf file. Returns path or None."""
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            self._send_json({"error": "empty request body; send the PDF as "
                             "raw body (curl --data-binary @file.pdf)"}, 400)
            return None
        if length > MAX_BODY_BYTES:
            self._send_json({"error": f"body too large (> {MAX_BODY_BYTES} bytes)"},
                            413)
            return None
        data = self.rfile.read(length)
        if data[:5] != b"%PDF-":
            self._send_json({"error": "body is not a PDF (missing %PDF- header). "
                             "Send raw PDF bytes, not multipart/JSON."}, 400)
            return None
        fd, path = tempfile.mkstemp(suffix=".pdf", prefix="ocr_srv_")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return path

    def log_message(self, fmt, *args):
        sys.stderr.write(
            f"  [ocr_server] {self.address_string()} - {fmt % args}\n")

    # ---- routes --------------------------------------------------------

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/health":
            missing = pdf_ocr.check_dependencies(need_ocr=True)
            self._send_json({
                "status": "ok",
                "dependencies": {
                    "pdftotext": pdf_ocr._have("pdftotext"),
                    "pdftoppm": pdf_ocr._have("pdftoppm"),
                    "tesseract": pdf_ocr._have("tesseract"),
                },
                "ocr_ready": not missing,
                "missing": missing,
            })
        else:
            self._send_json({"error": "not found",
                             "routes": ["/health", "POST /ocr", "POST /analyze"]},
                            404)

    def do_POST(self):
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)

        if route not in ("/ocr", "/analyze"):
            self._send_json({"error": "not found",
                             "routes": ["/health", "POST /ocr", "POST /analyze"]},
                            404)
            return

        path = self._read_pdf_body()
        if path is None:
            return  # error already sent

        try:
            dpi = _int(qs, "dpi", pdf_ocr.DEFAULT_DPI)
            lang = _str(qs, "lang", pdf_ocr.DEFAULT_LANG)
            force_ocr = _truthy(qs, "force_ocr")

            if route == "/ocr":
                result = pdf_ocr.extract_text(
                    path, force_ocr=force_ocr, dpi=dpi, lang=lang)
                self._send_json(result.to_dict())
            else:  # /analyze
                record = rfi_analyzer.analyze(
                    path, use_llm=_truthy(qs, "llm"),
                    force_ocr=force_ocr, dpi=dpi, lang=lang)
                if not _truthy(qs, "include_text"):
                    record.pop("text", None)
                record["markdown"] = rfi_analyzer.build_markdown(
                    {**record, "text": record.get("text", "")})
                self._send_json(record)
        except (FileNotFoundError, RuntimeError) as e:
            self._send_json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001 - surface unexpected errors as 500
            self._send_json({"error": f"internal error: {e}"}, 500)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


def main():
    p = argparse.ArgumentParser(description="HTTP OCR / RFI-analysis server")
    p.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    args = p.parse_args()

    missing = pdf_ocr.check_dependencies(need_ocr=True)
    if missing:
        print("[ocr_server] WARNING: OCR dependencies missing: "
              + ", ".join(missing), file=sys.stderr)
        print("[ocr_server] Text-layer PDFs will still work; scans will fail.",
              file=sys.stderr)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[ocr_server] listening on http://{args.host}:{args.port}", file=sys.stderr)
    print("[ocr_server] routes: GET /health, POST /ocr, POST /analyze",
          file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[ocr_server] shutting down", file=sys.stderr)
        server.shutdown()


if __name__ == "__main__":
    main()
