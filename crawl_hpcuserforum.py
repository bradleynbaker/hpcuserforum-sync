#!/usr/bin/env python3
"""
Crawl hpcuserforum.com, index all files (PDFs, PPTs, etc.), and optionally download them.
Supports date filtering to only keep files from the last N years.

Requires: pip install requests beautifulsoup4 lxml

Usage:
  python crawl_hpcuserforum.py                          # crawl + index, last 2 years
  python crawl_hpcuserforum.py --download               # crawl + download
  python crawl_hpcuserforum.py --download --years 3     # last 3 years
  python crawl_hpcuserforum.py --download --years 0     # all years (no filter)
  python crawl_hpcuserforum.py --download --output "D:\\crawler-hpc-user"
  python crawl_hpcuserforum.py --pdfs-only              # PDFs only
  python crawl_hpcuserforum.py --wayback-only           # Wayback Machine CDX only
"""

import argparse
import csv
import datetime
import json
import os
import re
import sys
import time
from collections import deque
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.hpcuserforum.com"
UPLOADS_PREFIX = "https://www.hpcuserforum.com/wp-content/uploads/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.hpcuserforum.com/",
}

ALL_EXTENSIONS = {".pdf", ".ppt", ".pptx", ".doc", ".docx", ".xls", ".xlsx", ".zip"}
PDF_ONLY = {".pdf"}

START_URLS = [
    BASE_URL + "/",
    BASE_URL + "/presentations/",
    BASE_URL + "/events/",
    BASE_URL + "/agenda/",
    BASE_URL + "/conference/",
    BASE_URL + "/workshops/",
    BASE_URL + "/tutorials/",
    BASE_URL + "/2024/",
    BASE_URL + "/2025/",
    BASE_URL + "/2026/",
    BASE_URL + "/2023/",
    BASE_URL + "/2022/",
    BASE_URL + "/2021/",
    BASE_URL + "/2020/",
    BASE_URL + "/2019/",
    BASE_URL + "/2018/",
    BASE_URL + "/2017/",
    BASE_URL + "/category/presentations/",
    BASE_URL + "/category/events/",
    BASE_URL + "/wp-sitemap.xml",
    BASE_URL + "/sitemap_index.xml",
]

# WordPress uploads path pattern: /wp-content/uploads/YYYY/MM/filename
_WP_UPLOAD_RE = re.compile(r"/wp-content/uploads/(\d{4})/(\d{2})/")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def get(session, url, timeout=30, stream=False):
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True, stream=stream)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        print(f"  [WARN] {url}: {e}", file=sys.stderr)
        return None


def head(session, url, timeout=15):
    try:
        r = session.head(url, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return r
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------

def year_from_url(url):
    """Extract upload year from WordPress URL path, e.g. /wp-content/uploads/2024/03/file.pdf -> 2024."""
    m = _WP_UPLOAD_RE.search(url)
    if m:
        return int(m.group(1))
    return None


def date_from_headers(r):
    """Parse Last-Modified header into a datetime, or None."""
    lm = r.headers.get("Last-Modified")
    if lm:
        try:
            return parsedate_to_datetime(lm)
        except Exception:
            pass
    return None


def file_passes_date_filter(session, url, cutoff_year):
    """
    Return True if the file is from cutoff_year or later.
    First tries the URL path (fast), then falls back to a HEAD request.
    """
    year = year_from_url(url)
    if year is not None:
        return year >= cutoff_year

    # Fall back to HEAD request for files not following WP upload path
    r = head(session, url)
    if r:
        dt = date_from_headers(r)
        if dt:
            return dt.year >= cutoff_year

    # Can't determine date — include it to be safe
    return True


def filter_by_date(session, file_urls, cutoff_year):
    """Filter file_urls to those from cutoff_year or later."""
    kept = set()
    dropped = set()
    total = len(file_urls)

    print(f"\n[DATE FILTER] Keeping files from {cutoff_year} onwards ({total} to check) ...")
    for i, url in enumerate(sorted(file_urls), 1):
        year = year_from_url(url)
        if year is not None:
            # Fast path — no network request needed
            if year >= cutoff_year:
                kept.add(url)
            else:
                dropped.add(url)
                print(f"  [DROP] {year} {os.path.basename(urlparse(url).path)}")
        else:
            # Slow path — HEAD request
            print(f"  [CHECK {i}/{total}] {os.path.basename(urlparse(url).path)}")
            if file_passes_date_filter(session, url, cutoff_year):
                kept.add(url)
            else:
                dropped.add(url)

    print(f"[DATE FILTER] {len(kept)} kept, {len(dropped)} dropped.")
    return kept


# ---------------------------------------------------------------------------
# Wayback Machine CDX
# ---------------------------------------------------------------------------

def wayback_cdx_urls(domain, extensions, cutoff_year=None, limit=10000):
    """Query Wayback CDX API for file URLs under domain."""
    found = set()
    base_cdx = "https://web.archive.org/cdx/search/cdx"
    params = {
        "url": f"{domain}/wp-content/uploads/*",
        "matchType": "prefix",
        "output": "json",
        "fl": "original,timestamp",
        "collapse": "urlkey",
        "limit": str(limit),
    }
    if cutoff_year:
        params["from"] = f"{cutoff_year}0101000000"

    print("[CDX] Querying Wayback Machine for indexed files ...")
    try:
        r = requests.get(base_cdx, params=params, timeout=60)
        r.raise_for_status()
        rows = r.json()
        for row in rows[1:]:
            url, timestamp = row[0], row[1]
            ext = os.path.splitext(urlparse(url).path)[1].lower()
            if ext not in extensions:
                continue
            if cutoff_year:
                try:
                    if int(timestamp[:4]) < cutoff_year:
                        continue
                except Exception:
                    pass
            found.add(url)
    except Exception as e:
        print(f"  [CDX] Failed: {e}", file=sys.stderr)

    print(f"[CDX] Found {len(found)} file URLs in Wayback index.")
    return found


# ---------------------------------------------------------------------------
# Live site crawler
# ---------------------------------------------------------------------------

def extract_links(base_url, html, extensions):
    soup = BeautifulSoup(html, "lxml")
    page_links = set()
    file_links = set()
    parsed_base = urlparse(base_url)
    host = parsed_base.netloc

    # Handle XML sitemaps
    for loc in soup.find_all("loc"):
        url = loc.get_text(strip=True)
        if not url:
            continue
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if ext in extensions:
            file_links.add(url)
        elif urlparse(url).netloc == host or ext == ".xml":
            page_links.add(url)

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc != host:
            continue
        ext = os.path.splitext(parsed.path)[1].lower()
        if ext in extensions:
            file_links.add(full)
        elif parsed.scheme in ("http", "https"):
            clean = full.split("#")[0]
            if clean:
                page_links.add(clean)

    # Bare URLs in raw HTML / JS / data attributes
    ext_group = "|".join(re.escape(e) for e in extensions)
    pattern = rf'https?://{re.escape(host)}/[^\s"\'<>]+(?:{ext_group})'
    for m in re.finditer(pattern, html, re.I):
        file_links.add(m.group(0))

    return page_links, file_links


def crawl(session, start_urls, extensions, max_pages=1000, delay=0.4):
    visited = set()
    file_urls = set()
    queue = deque(start_urls)

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        print(f"  [{len(visited):>4}/{max_pages}] {url}")
        r = get(session, url)
        if r is None:
            continue

        ct = r.headers.get("Content-Type", "")
        if "html" not in ct and "xml" not in ct:
            continue

        page_links, found = extract_links(url, r.text, extensions)
        file_urls.update(found)

        for link in sorted(page_links):
            if link not in visited:
                queue.append(link)

        time.sleep(delay)

    print(f"\nCrawled {len(visited)} pages — {len(file_urls)} files found.")
    return file_urls


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_all(session, file_urls, output_dir, delay=0.5):
    os.makedirs(output_dir, exist_ok=True)
    results = []
    total = len(file_urls)

    for i, url in enumerate(sorted(file_urls), 1):
        path = urlparse(url).path.lstrip("/")
        dest = os.path.join(output_dir, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        if os.path.exists(dest):
            print(f"  [{i}/{total}] Skip (exists): {os.path.basename(dest)}")
            results.append({"url": url, "dest": dest, "status": "skipped"})
            continue

        print(f"  [{i}/{total}] {os.path.basename(dest)}")
        r = get(session, url, timeout=120, stream=True)
        if r is None:
            results.append({"url": url, "dest": dest, "status": "error"})
            continue

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)

        size = os.path.getsize(dest)
        print(f"       -> {dest} ({size // 1024} KB)")
        results.append({"url": url, "dest": dest, "status": "ok", "size": size})
        time.sleep(delay)

    return results


# ---------------------------------------------------------------------------
# Index output
# ---------------------------------------------------------------------------

def write_index(file_urls, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    urls = sorted(file_urls)

    json_path = os.path.join(output_dir, "index.json")
    with open(json_path, "w") as f:
        json.dump(urls, f, indent=2)

    csv_path = os.path.join(output_dir, "index.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["#", "year", "filename", "url"])
        for i, url in enumerate(urls, 1):
            year = year_from_url(url) or ""
            w.writerow([i, year, os.path.basename(urlparse(url).path), url])

    print(f"\nIndex saved:\n  {json_path}\n  {csv_path}")
    return json_path, csv_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Crawl hpcuserforum.com and index/download files")
    p.add_argument("--download", action="store_true", help="Download all found files")
    p.add_argument("--output", default="D:\\crawler-hpc-user", metavar="DIR",
                   help="Output directory (default: D:\\crawler-hpc-user)")
    p.add_argument("--years", type=int, default=2,
                   help="Only keep files from the last N years (default: 2, use 0 for all)")
    p.add_argument("--max-pages", type=int, default=1000,
                   help="Max pages to crawl (default: 1000)")
    p.add_argument("--delay", type=float, default=0.4,
                   help="Seconds between requests (default: 0.4)")
    p.add_argument("--pdfs-only", action="store_true",
                   help="Only collect PDF files")
    p.add_argument("--wayback-only", action="store_true",
                   help="Skip live crawl; use only Wayback Machine CDX")
    p.add_argument("--no-wayback", action="store_true",
                   help="Skip Wayback Machine CDX; only do live crawl")
    args = p.parse_args()

    extensions = PDF_ONLY if args.pdfs_only else ALL_EXTENSIONS
    session = make_session()
    all_files = set()

    cutoff_year = None
    if args.years > 0:
        cutoff_year = datetime.date.today().year - args.years + 1
        print(f"[INFO] Date filter: files from {cutoff_year} onwards (last {args.years} years)")

    # 1. Wayback Machine CDX
    if not args.no_wayback:
        cdx_files = wayback_cdx_urls("hpcuserforum.com", extensions, cutoff_year=cutoff_year)
        all_files.update(cdx_files)

    # 2. Live crawl
    if not args.wayback_only:
        print(f"\n[CRAWL] Starting live crawl (max {args.max_pages} pages) ...")
        live_files = crawl(session, START_URLS, extensions,
                           max_pages=args.max_pages, delay=args.delay)
        all_files.update(live_files)

    if not all_files:
        print("\nNo files found.")
        sys.exit(0)

    # 3. Apply date filter (for files not already filtered by CDX timestamp)
    if cutoff_year:
        all_files = filter_by_date(session, all_files, cutoff_year)

    if not all_files:
        print(f"\nNo files found from {cutoff_year} onwards. Try --years 5 or --years 0.")
        sys.exit(0)

    # Print summary
    print(f"\n{'='*60}")
    print(f"FILES FOUND (from {cutoff_year} onwards): {len(all_files)}")
    print(f"{'='*60}")
    for i, url in enumerate(sorted(all_files), 1):
        year = year_from_url(url) or "????"
        print(f"  {i:>4}. [{year}] {os.path.basename(urlparse(url).path)}")
        print(f"        {url}")

    write_index(all_files, args.output)

    if args.download:
        print(f"\n[DOWNLOAD] Fetching {len(all_files)} files into: {args.output}")
        results = download_all(session, all_files, args.output, delay=args.delay)
        ok = sum(1 for r in results if r["status"] == "ok")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        errors = sum(1 for r in results if r["status"] == "error")
        print(f"\nDone: {ok} downloaded, {skipped} skipped, {errors} errors.")
    else:
        print(f"\nRun with --download to fetch all {len(all_files)} files.")


if __name__ == "__main__":
    main()
