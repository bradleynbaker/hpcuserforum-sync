FROM python:3.11-slim

# System dependencies for OCR: poppler (pdftotext/pdftoppm) + tesseract.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps. anthropic is only needed for /analyze?llm=1; harmless otherwise.
COPY requirements.txt .
RUN pip install --no-cache-dir anthropic

COPY pdf_ocr.py rfi_analyzer.py ocr_server.py ./

EXPOSE 8000

# Bind 0.0.0.0 so the port is reachable from outside the container.
CMD ["python", "ocr_server.py", "--host", "0.0.0.0", "--port", "8000"]
