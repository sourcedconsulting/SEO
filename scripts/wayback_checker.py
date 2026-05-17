#!/usr/bin/env python3
"""
wayback_checker.py — Check domain archival across multiple Wayback services.

Usage:
    python scripts/wayback_checker.py https://example.com
    python scripts/wayback_checker.py https://example.com --json

Services checked:
  1. Internet Archive "available" API (preferred — small JSON response)
  2. Internet Archive CDX (fallback if available API returns empty)
  3. Archive.today  (rate-limited — flagged if 429/non-200)
  4. Google site:   (bonus index signal — requires live network)

All fetches use Chrome-like headers with strict timeouts (10–20 s) and clear
labels for every non-success outcome: BLOCKED / TIMEOUT / NOT FOUND / ERROR.

Installs: pip install requests beautifulsoup4
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

try:
    import requests                          # type: ignore
    from bs4 import BeautifulSoup            # type: ignore
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# ── Chrome desktop headers (AU locale) ────────────────────────────────────────
CHROME_HEADERS = {
    "User-Agent":      ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/132.0.0.0 Safari/537.36"),
    "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "DNT":             "1",
    "Referer":         "https://www.google.com/",
    "Connection":      "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":  "document",
    "Sec-Fetch-Mode":  "navigate",
    "Sec-Fetch-Site":  "cross-site",
}

# pyright: reportPossiblyUnboundVariable=false
# (all call sites are guarded by `if not HAS_DEPS` at the top of each function)

CDX_URL = "https://web.archive.org/cdx/search/cdx"


# ── Helpers ───────────────────────────────────────────────────────────────────

def http_get(url: str, timeout: int, headers: dict | None = None) -> "requests.Response":
    return requests.get(url, timeout=timeout, headers=headers or CHROME_HEADERS)


def slugify(domain: str) -> str:
    return domain.replace("https://", "").replace("http://", "").rstrip("/")


# ── Internet Archive — wayback/available (preferred) ─────────────────────────

def ia_available(domain: str) -> dict:
    """IA 'is this domain archived?' endpoint — small JSON, fast."""
    if not HAS_DEPS:
        return {"service": "ia_available", "status": "error",
                "summary": "requests/bs4 not installed"}

    slug = slugify(domain)
    url  = f"https://archive.org/wayback/available?url={urllib.parse.quote_plus(slug)}"

    try:
        resp  = http_get(url, timeout=15)
        ct    = resp.headers.get("Content-Type", "")
        body  = resp.text.strip()

        if resp.status_code in (429, 503) or not body:
            return {"service": "ia_available", "status": "blocked",
                    "available": None, "http_code": resp.status_code,
                    "summary": f"HTTP {resp.status_code} (rate-limited or no data)"}

        try:
            import json as _json
            data = _json.loads(body)
        except Exception:
            return {"service": "ia_available", "status": "error",
                    "available": None, "http_code": resp.status_code,
                    "summary": "non-JSON response from IA"}

        arch     = data.get("archived_snapshots", {})
        closest  = arch.get("closest", {})

        if closest:
            return {
                "service":   "ia_available",
                "status":    "archived",
                "available": True,
                "url":       closest.get("url", ""),
                "timestamp": closest.get("timestamp", ""),
                "http_code": resp.status_code,
            }
        return {"service": "ia_available", "status": "not_found",
                "available": False, "http_code": resp.status_code}

    except requests.exceptions.Timeout:
        return {"service": "ia_available", "status": "timeout",
                "available": None, "http_code": None,
                "summary": "timeout 15 s"}
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response else "?"
        blob = "blocked" if code in (403, 429) else "error"
        return {"service": "ia_available", "status": blob,
                "available": None, "http_code": code,
                "summary": f"HTTP {code} ({blob})"}
    except Exception as exc:
        return {"service": "ia_available", "status": "error",
                "available": None, "summary": str(exc)[:120]}


def ia_cdx(domain: str) -> dict:
    """CDX API fallback — can return large payloads; wrapped with a read timeout."""
    if not HAS_DEPS:
        return {"service": "ia_cdx", "status": "error",
                "summary": "requests/bs4 not installed"}

    slug = slugify(domain)
    params = {
        "url":    slug + "/*",
        "fl":     "timestamp,statuscode",
        "filter": "statuscode:200",
        "output": "json",
        "limit":  "5",
        "collapse": "urlkey",
    }
    try:
        url  = "https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(params)
        # Stream so we don't stall on a mega-response spanning minutes
        resp = http_get(url, timeout=30, headers={"User-Agent": "hermes-seo-tools/2.0"})
        resp.raise_for_status()

        # Read only the first 200 KB — enough to confirm existence
        chunk = resp.raw.read(200_000, decode_content=True)
        try:
            import json as _json
            rows = _json.loads(chunk)
        except Exception:
            rows = []

        stamps = [r[0] for r in rows[1:] if isinstance(r, list) and r[0]]
        if stamps:
            return {
                "service":    "ia_cdx",
                "status":     "archived",
                "available":  True,
                "first_seen": min(stamps),
                "last_seen":  max(stamps),
                "sample_pages": len(stamps),
                "http_code":  resp.status_code,
                "note":       "partial read (first 200 KB)",
            }
        return {"service": "ia_cdx", "status": "not_found",
                "available": False, "http_code": resp.status_code}

    except requests.exceptions.Timeout:
        return {"service": "ia_cdx", "status": "timeout",
                "available": None, "summary": "CDX read timeout 30 s"}
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response else "?"
        blob = "blocked" if code in (403, 429) else "error"
        return {"service": "ia_cdx", "status": blob,
                "available": None, "http_code": code,
                "summary": f"HTTP {code} ({blob})"}
    except Exception as exc:
        return {"service": "ia_cdx", "status": "error",
                "available": None, "summary": str(exc)[:120]}


# ── Archive.today ─────────────────────────────────────────────────────────────

def archive_today(domain: str) -> dict:
    """Archive.today /submit/ page probe — no public API, rate-gated."""
    if not HAS_DEPS:
        return {"service": "archive_today", "status": "error",
                "summary": "requests/bs4 not installed"}

    try:
        resp = http_get(
            "https://archive.today/submit/",
            timeout=12,
            headers={"User-Agent": "hermes-seo-tools/2.0"},
        )
        resp.raise_for_status()

        # splash page up → treat service as reachable
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.title.text if soup.title else ""
        down  = any(kw in title.lower() for kw in ["down", "maintenance", "offline"])

        if down:
            return {"service": "archive_today", "status": "error",
                    "available": False, "summary": f"page shows: {title.strip()}"}

        return {
            "service":    "archive_today",
            "status":     "unknown",
            "available":  True,
            "http_code":  resp.status_code,
            "summary":    "service reachable — no public API; IP may be rate-gated",
        }

    except requests.exceptions.Timeout:
        return {"service": "archive_today", "status": "timeout",
                "available": None, "summary": "timeout 12 s"}
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response else "?"
        if code == 429:
            return {"service": "archive_today", "status": "blocked",
                    "available": False, "http_code": 429,
                    "summary": "HTTP 429 Too Many Requests — IP rate-limited"}
        return {"service": "archive_today", "status": "error",
                "available": None, "http_code": code,
                "summary": f"HTTP {code}"}
    except Exception as exc:
        return {"service": "archive_today", "status": "error",
                "available": None, "summary": str(exc)[:120]}


# ── Google site: (bonus signal) ────────────────────────────────────────────────

def google_site(domain: str) -> dict:
    """Bonus signal: is this domain in the current Google index?"""
    if not HAS_DEPS:
        return {"service": "google_site", "status": "error",
                "summary": "requests not installed"}

    slug = slugify(domain)
    url  = f"https://www.google.com/search?q=site:{urllib.parse.quote_plus(slug)}&num=1"

    try:
        resp = http_get(url, timeout=15)
        text = resp.text.lower()

        no_results = any(ph in text for ph in [
            "did not return any results",
            "no results found",
            "your search did not match any documents",
            "did not match any documents",
        ])

        if no_results:
            return {"service": "google_site", "status": "not_indexed",
                    "available": True, "http_code": resp.status_code,
                    "summary": "not in Google index results"}

        count = None
        m = re.search(r"about\s+([\d,]+)\s+results", text)
        if m:
            count = int(m.group(1).replace(",", ""))

        return {
            "service":    "google_site",
            "status":     "indexed",
            "available":  True,
            "http_code":  resp.status_code,
            "result_count": count,
            "summary":    f"in Google index — ~{count:,} results" if count else "in Google index",
        }

    except requests.exceptions.Timeout:
        return {"service": "google_site", "status": "timeout",
                "available": None, "summary": "timeout 15 s"}
    except Exception as exc:
        return {"service": "google_site", "status": "error",
                "available": None, "summary": str(exc)[:120]}


# ── Report ─────────────────────────────────────────────────────────────────────

def _fmt(r: dict) -> str:
    s = r.get("status", "?")
    avail = r.get("available")

    if avail is None:
        return f"  {r['service'].upper():22s}  ✗ {s.upper()}{'':12s}  {r.get('summary','')}"
    if r.get("summary"):
        return f"  {r['service'].upper():22s}  ✓ {s.upper()}{'':12s}  {r['summary']}"
    return f"  {r['service'].upper():22s}  ✓ OK"


def format_report(domain: str, results: list[dict]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"WAYBACK / ARCHIVAL CHECK — {domain}")
    lines.append("=" * 60)
    for r in results:
        lines.append(_fmt(r))
    lines.append("_" * 60)

    any_archived = any(r.get("status") == "archived" for r in results)
    any_indexed  = any(r.get("service") == "google_site" and r.get("status") == "indexed" for r in results)
    problems = [r for r in results if r.get("status") in ("timeout", "blocked", "error")]

    lines.append(f"  Archived somewhere: {'YES' if any_archived else 'NO'}")
    lines.append(f"  In Google index   : {'YES' if any_indexed  else 'NO'}")
    if problems:
        lines.append(f"  Problematic services ({len(problems)}): "
                     + ", ".join(r["service"] for r in problems))
    lines.append("=" * 60)
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Multi-Wayback domain checker.")
    ap.add_argument("domain", help="Domain, e.g. https://example.com")
    ap.add_argument("--json", help="Save JSON output to file")
    args = ap.parse_args()

    results = [
        ia_available(args.domain),
        ia_cdx(args.domain),
        archive_today(args.domain),
        google_site(args.domain),
    ]
    print(format_report(args.domain, results))

    if args.json:
        Path(args.json).write_text(
            json.dumps({"domain": args.domain, "services": results}, indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON saved → {args.json}")


if __name__ == "__main__":
    main()
