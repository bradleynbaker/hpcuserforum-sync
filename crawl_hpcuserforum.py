#!/usr/bin/env python3
"""
Crawl hpcuserforum.com and hyperionresearch.com, index files (PDFs, XLS, etc.),
and optionally download them. Supports date filtering to only keep files from
the last N years.

Requires: pip install requests beautifulsoup4 lxml

Usage:
  python crawl_hpcuserforum.py                          # crawl + index, last 2 years
  python crawl_hpcuserforum.py --download               # crawl + download
  python crawl_hpcuserforum.py --download --years 3     # last 3 years
  python crawl_hpcuserforum.py --download --years 0     # all years (no filter)
  python crawl_hpcuserforum.py --download --output "D:\\crawler-hpc-user"
  python crawl_hpcuserforum.py --attendee-list          # PDFs + XLS with "attendee" in name
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
}

ALL_EXTENSIONS      = {".pdf", ".ppt", ".pptx", ".doc", ".docx", ".xls", ".xlsx", ".zip"}
PDF_ONLY            = {".pdf"}
ATTENDEE_EXTENSIONS = {".pdf", ".xls", ".xlsx"}

# ---------------------------------------------------------------------------
# Site definitions — add new sites here
# ---------------------------------------------------------------------------

SITES = {
    "hpcuserforum": {
        "base": "https://www.hpcuserforum.com",
        "start_urls": [
            "https://www.hpcuserforum.com/",
            "https://www.hpcuserforum.com/presentations/",
            "https://www.hpcuserforum.com/events/",
            "https://www.hpcuserforum.com/agenda/",
            "https://www.hpcuserforum.com/conference/",
            "https://www.hpcuserforum.com/workshops/",
            "https://www.hpcuserforum.com/tutorials/",
            "https://www.hpcuserforum.com/2017/",
            "https://www.hpcuserforum.com/2018/",
            "https://www.hpcuserforum.com/2019/",
            "https://www.hpcuserforum.com/2020/",
            "https://www.hpcuserforum.com/2021/",
            "https://www.hpcuserforum.com/2022/",
            "https://www.hpcuserforum.com/2023/",
            "https://www.hpcuserforum.com/2024/",
            "https://www.hpcuserforum.com/2025/",
            "https://www.hpcuserforum.com/2026/",
            "https://www.hpcuserforum.com/category/presentations/",
            "https://www.hpcuserforum.com/category/events/",
            "https://www.hpcuserforum.com/wp-sitemap.xml",
            "https://www.hpcuserforum.com/sitemap_index.xml",
        ],
        "cdx_domain": "www.hpcuserforum.com",
    },
    "hyperionresearch": {
        "base": "https://hyperionresearch.com",
        "start_urls": [
            "https://hyperionresearch.com/",
            "https://hyperionresearch.com/events/",
            "https://hyperionresearch.com/resources/",
            "https://hyperionresearch.com/reports/",
            "https://hyperionresearch.com/research/",
            "https://hyperionresearch.com/publications/",
            "https://hyperionresearch.com/downloads/",
            "https://hyperionresearch.com/presentations/",
            "https://hyperionresearch.com/news/",
            "https://hyperionresearch.com/wp-sitemap.xml",
            "https://hyperionresearch.com/sitemap.xml",
            "https://hyperionresearch.com/sitemap_index.xml",
        ],
        "cdx_domain": "hyperionresearch.com",
    },
}

# WordPress uploads path pattern: /wp-content/uploads/YYYY/MM/filename
_WP_UPLOAD_RE = re.compile(r"/wp-content/uploads/(\d{4})/(\d{2})/")

# ---------------------------------------------------------------------------
# Live metrics / status line
# ---------------------------------------------------------------------------

_metrics = {
    "pages":   0,
    "queued":  0,
    "files":   0,
    "matched": 0,
    "errors":  0,
    "start":   None,
}

def _status_line(site_label, current_url=""):
    elapsed = time.time() - _metrics["start"]
    mins    = elapsed / 60
    rate    = _metrics["pages"] / mins if mins > 0 else 0
    trunc   = current_url[-60:] if len(current_url) > 60 else current_url
    line = (
        f"\r  [{site_label:<16}]  "
        f"Pages:{_metrics['pages']:>5}  Queue:{_metrics['queued']:>4}  "
        f"Files:{_metrics['files']:>4}  Matched:{_metrics['matched']:>3}  "
        f"Errors:{_metrics['errors']:>3}  "
        f"{rate:>5.1f} pg/min  {elapsed:>5.0f}s  {trunc:<60}"
    )
    sys.stdout.write(line)
    sys.stdout.flush()

def _newline():
    sys.stdout.write("\n")
    sys.stdout.flush()


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
        _metrics["errors"] += 1
        print(f"\n  [WARN] {url}: {e}", file=sys.stderr)
        return None


def head(session, url, timeout=15):
    try:
        r = session.head(url, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return r
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# Attendee-list filter
# ---------------------------------------------------------------------------

_ATTENDEE_RE = re.compile(r"attendee", re.IGNORECASE)

def is_attendee_file(url):
    filename = os.path.basename(urlparse(url).path)
    return bool(_ATTENDEE_RE.search(filename))


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
    lm = r.headers.get("Last-Modified")
    if lm:
        try:
            return parsedate_to_datetime(lm)
        except Exception:
            pass
    return None


def file_passes_date_filter(session, url, cutoff_year):
    year = year_from_url(url)
    if year is not None:
        return year >= cutoff_year
    r = head(session, url)
    if r:
        dt = date_from_headers(r)
        if dt:
            return dt.year >= cutoff_year
    return True


def filter_by_date(session, file_urls, cutoff_year):
    kept    = set()
    dropped = set()
    total   = len(file_urls)

    print(f"\n[DATE FILTER] Keeping files from {cutoff_year} onwards ({total} to check) ...")
    for i, url in enumerate(sorted(file_urls), 1):
        year = year_from_url(url)
        if year is not None:
            if year >= cutoff_year:
                kept.add(url)
            else:
                dropped.add(url)
                print(f"  [DROP] {year} {os.path.basename(urlparse(url).path)}")
        else:
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

def wayback_cdx_urls(domain, extensions, cutoff_year=None, keyword=None, limit=10000):
    """Query Wayback CDX API for file URLs under domain."""
    found    = set()
    base_cdx = "https://web.archive.org/cdx/search/cdx"
    params   = {
        "url":        f"{domain}/wp-content/uploads/*",
        "matchType":  "prefix",
        "output":     "json",
        "fl":         "original,timestamp",
        "collapse":   "urlkey",
        "limit":      str(limit),
    }
    if cutoff_year:
        params["from"] = f"{cutoff_year}0101000000"

    print(f"[CDX] Querying Wayback Machine for {domain} ...")
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
            if keyword and not re.search(keyword, os.path.basename(urlparse(url).path), re.IGNORECASE):
                continue
            found.add(url)
    except Exception as e:
        print(f"  [CDX] Failed for {domain}: {e}", file=sys.stderr)

    print(f"[CDX] {domain}: {len(found)} file URLs found.")
    return found


# ---------------------------------------------------------------------------
# Live site crawler
# ---------------------------------------------------------------------------

def extract_links(base_url, html, extensions, allowed_host):
    soup       = BeautifulSoup(html, "lxml")
    page_links = set()
    file_links = set()

    for loc in soup.find_all("loc"):
        url = loc.get_text(strip=True)
        if not url:
            continue
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if ext in extensions:
            file_links.add(url)
        elif urlparse(url).netloc == allowed_host or ext == ".xml":
            page_links.add(url)

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        full   = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc != allowed_host:
            continue
        ext = os.path.splitext(parsed.path)[1].lower()
        if ext in extensions:
            file_links.add(full)
        elif parsed.scheme in ("http", "https"):
            clean = full.split("#")[0]
            if clean:
                page_links.add(clean)

    ext_group = "|".join(re.escape(e) for e in extensions)
    pattern   = rf'https?://{re.escape(allowed_host)}/[^\s"\'<>]+(?:{ext_group})'
    for m in re.finditer(pattern, html, re.I):
        file_links.add(m.group(0))

    return page_links, file_links


def crawl_site(session, site_key, site_cfg, extensions, max_pages=1000, delay=0.4, keyword=None):
    """Crawl a single site and return (all_file_urls, matched_file_urls)."""
    allowed_host = urlparse(site_cfg["base"]).netloc
    visited      = set()
    file_urls    = set()
    matched      = set()
    queue        = deque(site_cfg["start_urls"])

    _metrics["start"]   = time.time()
    _metrics["pages"]   = 0
    _metrics["queued"]  = len(queue)
    _metrics["files"]   = 0
    _metrics["matched"] = 0
    _metrics["errors"]  = 0

    label = site_key
    print(f"\n[CRAWL] {site_cfg['base']}  (max {max_pages} pages, delay {delay}s)")
    print(f"        Extensions: {', '.join(sorted(extensions))}"
          + (f"  |  Keyword: '{keyword}'" if keyword else ""))
    print()

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        _metrics["pages"]  = len(visited)
        _metrics["queued"] = len(queue)
        _status_line(label, url)

        r = get(session, url)
        if r is None:
            time.sleep(delay)
            continue

        ct = r.headers.get("Content-Type", "")
        if "html" not in ct and "xml" not in ct:
            time.sleep(delay)
            continue

        page_links, found = extract_links(url, r.text, extensions, allowed_host)
        new_files = found - file_urls
        file_urls.update(found)
        _metrics["files"] = len(file_urls)

        for fu in new_files:
            if keyword is None or re.search(keyword, os.path.basename(urlparse(fu).path), re.IGNORECASE):
                matched.add(fu)
                _metrics["matched"] = len(matched)
                _newline()
                fname = os.path.basename(urlparse(fu).path)
                year  = year_from_url(fu) or "????"
                src   = urlparse(fu).netloc
                print(f"  *** MATCH [{year}] [{src}] {fname}")
                print(f"            {fu}")

        for link in sorted(page_links):
            if link not in visited:
                queue.append(link)
        _metrics["queued"] = len(queue)

        time.sleep(delay)

    _newline()
    elapsed = time.time() - _metrics["start"]
    print(f"[CRAWL] {site_cfg['base']} done in {elapsed:.0f}s — "
          f"{len(visited)} pages, {len(file_urls)} files, {len(matched)} matched.")
    return file_urls, matched


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_all(session, file_urls, output_dir, delay=0.5):
    os.makedirs(output_dir, exist_ok=True)
    results = []
    total   = len(file_urls)

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

def write_index(file_urls, output_dir, suffix=""):
    os.makedirs(output_dir, exist_ok=True)
    urls = sorted(file_urls)

    json_path = os.path.join(output_dir, f"index{suffix}.json")
    with open(json_path, "w") as f:
        json.dump(urls, f, indent=2)

    csv_path = os.path.join(output_dir, f"index{suffix}.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["#", "year", "source", "filename", "url"])
        for i, url in enumerate(urls, 1):
            year   = year_from_url(url) or ""
            source = urlparse(url).netloc
            w.writerow([i, year, source, os.path.basename(urlparse(url).path), url])

    print(f"\nIndex saved:\n  {json_path}\n  {csv_path}")
    return json_path, csv_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="Crawl hpcuserforum.com + hyperionresearch.com and index/download files"
    )
    p.add_argument("--download", action="store_true", help="Download all matched files")
    p.add_argument("--output", default="D:\\crawler-hpc-user", metavar="DIR",
                   help="Output directory (default: D:\\crawler-hpc-user)")
    p.add_argument("--years", type=int, default=2,
                   help="Only keep files from the last N years (default: 2, use 0 for all)")
    p.add_argument("--max-pages", type=int, default=1000,
                   help="Max pages to crawl per site (default: 1000)")
    p.add_argument("--delay", type=float, default=0.4,
                   help="Seconds between requests (default: 0.4)")
    p.add_argument("--attendee-list", action="store_true",
                   help="Collect only PDFs/XLS files whose name contains 'attendee'")
    p.add_argument("--pdfs-only", action="store_true",
                   help="Only collect PDF files")
    p.add_argument("--wayback-only", action="store_true",
                   help="Skip live crawl; use only Wayback Machine CDX")
    p.add_argument("--no-wayback", action="store_true",
                   help="Skip Wayback Machine CDX; only do live crawl")
    p.add_argument("--sites", nargs="+", choices=list(SITES.keys()),
                   default=list(SITES.keys()),
                   help="Which sites to crawl (default: all)")
    args = p.parse_args()

    if args.attendee_list:
        extensions = ATTENDEE_EXTENSIONS
        keyword    = "attendee"
    elif args.pdfs_only:
        extensions = PDF_ONLY
        keyword    = None
    else:
        extensions = ALL_EXTENSIONS
        keyword    = None

    session    = make_session()
    all_files  = set()
    matched    = set()

    cutoff_year = None
    if args.years > 0:
        cutoff_year = datetime.date.today().year - args.years + 1
        print(f"[INFO] Date filter  : files from {cutoff_year} onwards (last {args.years} years)")

    if args.attendee_list:
        print("[INFO] Mode         : attendee-list  (PDF + XLS/XLSX, filename contains 'attendee')")

    active_sites = {k: SITES[k] for k in args.sites}
    print(f"[INFO] Sites        : {', '.join(active_sites.keys())}")
    print()

    # 1. Wayback Machine CDX (one query per site)
    if not args.no_wayback:
        for site_key, site_cfg in active_sites.items():
            cdx_files = wayback_cdx_urls(
                site_cfg["cdx_domain"], extensions,
                cutoff_year=cutoff_year, keyword=keyword,
            )
            all_files.update(cdx_files)
            if keyword:
                matched.update(cdx_files)

    # 2. Live crawl (one crawl per site)
    if not args.wayback_only:
        for site_key, site_cfg in active_sites.items():
            live_files, live_matched = crawl_site(
                session, site_key, site_cfg, extensions,
                max_pages=args.max_pages, delay=args.delay, keyword=keyword,
            )
            all_files.update(live_files)
            matched.update(live_matched)

    result_files = matched if keyword else all_files

    if not result_files:
        print("\nNo files found.")
        sys.exit(0)

    # 3. Apply date filter
    if cutoff_year:
        result_files = filter_by_date(session, result_files, cutoff_year)

    if not result_files:
        print(f"\nNo files found from {cutoff_year} onwards. Try --years 5 or --years 0.")
        sys.exit(0)

    # Summary
    label      = "ATTENDEE FILES" if keyword else "FILES FOUND"
    year_label = f"from {cutoff_year} onwards" if cutoff_year else "all years"
    print(f"\n{'='*60}")
    print(f"{label} ({year_label}): {len(result_files)}")
    print(f"{'='*60}")
    for i, url in enumerate(sorted(result_files), 1):
        year   = year_from_url(url) or "????"
        source = urlparse(url).netloc
        print(f"  {i:>4}. [{year}] [{source}] {os.path.basename(urlparse(url).path)}")
        print(f"        {url}")

    suffix = "_attendee" if keyword else ""
    write_index(result_files, args.output, suffix=suffix)

    if args.download:
        print(f"\n[DOWNLOAD] Fetching {len(result_files)} files into: {args.output}")
        results = download_all(session, result_files, args.output, delay=args.delay)
        ok      = sum(1 for r in results if r["status"] == "ok")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        errors  = sum(1 for r in results if r["status"] == "error")
        print(f"\nDone: {ok} downloaded, {skipped} skipped, {errors} errors.")
    else:
        print(f"\nRun with --download to fetch all {len(result_files)} files.")


if __name__ == "__main__":
    main()
