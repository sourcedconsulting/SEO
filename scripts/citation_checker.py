#!/usr/bin/env python3
"""
citation_checker.py — Check Australian business directory citations (NAP consistency).

Usage:
    python scripts/citation_checker.py "Your Business Name" "Brisbane QLD"
    python scripts/citation_checker.py "Clean Pro Plumbing" "Brisbane QLD" --json

Checks Yellow Pages, TrueLocal, HotFrog AU, and StartLocal AU.

Key fix: chrome-like HTTP headers + 3-retry backoff are used for all
directory fetches. Sites that block non-browser UAs (YP 403, TrueLocal 403)
are now surfaced honestly as "blocked" rather than silently failing.

Installs: pip install requests beautifulsoup4
"""

import argparse
import json
import random
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


# ── Chrome desktop headers (AU locale) ──
CHROME_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/132.0.0.0 Safari/537.36",
    "Accept":          ("text/html,application/xhtml+xml,application/xml;"
                        "q=0.9,image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-AU,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT":             "1",
    "Referer":         "https://www.google.com/",
    "Connection":      "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":  "document",
    "Sec-Fetch-Mode":  "navigate",
    "Sec-Fetch-Site":  "cross-site",
}

AUS_DIRECTORIES = [
    {"name": "Yellow Pages",
     "url":  "https://www.yellowpages.com.au/search/listings?clue={query}&location=QLD",
     "timeout": 20},
    {"name": "TrueLocal",
     "url":  "https://www.truelocal.com.au/search?what={query}&where={where}",
     "timeout": 20},
    {"name": "HotFrog",
     "url":  "https://www.hotfrog.com.au/search/au/{query}",
     "timeout": 15},
    {"name": "StartLocal",
     "url":  "https://www.startlocal.com.au/search?q={query}&t=b",
     "timeout": 20},
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def normalise(text: str) -> str:
    """Lowercase + strip non-alphanumeric for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def looks_like_match(text: str, business_name: str, suburb: str) -> bool:
    raw_n = normalise(business_name)
    raw_s = normalise(suburb)
    blob  = normalise(text)
    return raw_n in blob or (raw_s and raw_s in blob)


def fetch_with_retry(url: str, timeout: int, attempts: int = 3) -> "requests.Response":
    """GET with jittered exponential backoff."""
    import requests
    for i in range(attempts):
        try:
            resp = requests.get(url, timeout=timeout, headers=CHROME_HEADERS)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code if exc.response else 0
            if 400 <= code < 500:
                raise
            if i < attempts - 1:
                time.sleep((2 ** i) + random.random())
        except Exception:
            if i < attempts - 1:
                time.sleep((2 ** i) + random.random())
    raise RuntimeError(f"Failed after {attempts} attempts")


def check_directory(d: dict, query: str, suburb: str) -> dict:
    if not HAS_DEPS:
        return {"name": d["name"], "found": None, "match": None,
                "error": "requests/bs4 not installed"}

    url = d["url"].format(
        query  = urllib.parse.quote_plus(query),
        where  = urllib.parse.quote_plus(suburb),
        cat    = "",
    )

    try:
        resp = fetch_with_retry(url, timeout=d["timeout"])
        soup = BeautifulSoup(resp.text, "lxml")

        # Prefer listing containers if present
        listings = soup.find_all(
            ["div", "li", "article"],
            class_=re.compile(r"listing|result|business", re.I),
        )
        text_parts = [el.get_text(" ", strip=True) for el in listings]
        snippet = (" ".join(text_parts)[:600]
                   if text_parts
                   else soup.get_text(" ", strip=True)[:600])

        match = looks_like_match(snippet, query, suburb)
        return {"name": d["name"], "found": True, "match": match,
                "url": str(resp.url)[:120]}

    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response else "?"
        label = "blocked" if code in (403, 429) else "error"
        return {"name": d["name"], "found": False, "match": None,
                "error": f"HTTP {code} ({label})"}

    except requests.exceptions.Timeout:
        return {"name": d["name"], "found": False, "match": None,
                "error": "timeout"}

    except Exception as exc:
        return {"name": d["name"], "found": False, "match": None,
                "error": str(exc)[:80]}


# ── Report ───────────────────────────────────────────────────────────────────

def format_report(business: str, suburb: str, results: list[dict]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"CITATION AUDIT — {business}")
    lines.append(f"Location: {suburb}")
    lines.append("=" * 60)

    found = matched = blocked = 0

    for r in results:
        err = r.get("error", "")

        if err.startswith("HTTP 40"):
            status  = "▣ BLOCKED"
            match_lbl = "—"
            blocked += 1
        else:
            status  = "✓ FOUND"   if r.get("found")   else "✗ NOT FOUND"
            match_lbl = ("✓ MATCH" if r.get("match")
                          else "✗ MISMATCH" if r.get("found") else "—")

        lines.append(f"  {r['name']:<20s}  {status:<14s}  {match_lbl:10s}  {err}")
        if r.get("url"):
            lines.append(f"    URL: {r['url']}")
        if r.get("found"):
            found += 1
        if r.get("match"):
            matched += 1

    lines.append("=" * 60)
    lines.append(f"Directories surveyed   : {len(results)}")
    lines.append(f"Listings found          : {found}/{len(results)}")
    lines.append(f"NAP-likely matching     : {matched}/{found}")
    if blocked:
        lines.append(f"Blocked by WAF/robots   : {blocked}")
    lines.append("=" * 60)
    if matched < len(results) * 0.5:
        lines.append("WARNING: less than 50% match rate — NAP consistency check needed.")
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Australian citation auditor.")
    ap.add_argument("business_name",   help="Registered business name")
    ap.add_argument("suburb",          help="Suburb/city (e.g. Brisbane QLD)")
    ap.add_argument("--json",          help="Save results as JSON")
    ap.add_argument("--no-browser-headers", action="store_true",
                    help="Use simple UA instead of chrome headers")
    args = ap.parse_args()

    if args.no_browser_headers:
        CHROME_HEADERS.clear()
        CHROME_HEADERS["User-Agent"] = "hermes-seo-tools/2.0"

    results = [check_directory(d, args.business_name, args.suburb)
               for d in AUS_DIRECTORIES]
    print(format_report(args.business_name, args.suburb, results))

    if args.json:
        out = {"business": args.business_name, "suburb": args.suburb,
               "results": results}
        Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
