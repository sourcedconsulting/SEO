\
#!/usr/bin/env python3
"""
citation_checker.py — Check Australian business directory citations (NAP consistency).

Usage:
    python scripts/citation_checker.py "Your Business Name" "Brisbane QLD"
    python scripts/citation_checker.py "Clean Pro Plumbing" "Brisbane QLD" --json

Checks Yellow Pages, TrueLocal, HotFrog AU, and Google (via direct lookup).

Installs: pip install requests beautifulsoup4
"""

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

try:
    import requests  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


AUS_DIRECTORIES = [
    {"name": "Yellow Pages",  "url": "https://www.yellowpages.com.au/search/listings?clue={query}"},
    {"name": "TrueLocal",     "url": "https://www.truelocal.com.au/search?what={query}&where={where}"},
    {"name": "HotFrog",       "url": "https://www.hotfrog.com.au/search/au/{query}"},
    {"name": "StartLocal",    "url": "https://www.startlocal.com.au/search/{cat}/{where}/{query}.html"},
]


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def looks_like_match(text: str, business_name: str, suburb: str) -> bool:
    raw_n = normalise(business_name)
    raw_s = normalise(suburb)
    blob = normalise(text)
    return raw_n in blob or (raw_s and raw_s in blob)


def check_directory(d: dict, query: str, suburb: str) -> dict:
    if not HAS_DEPS:
        return {"name": d["name"], "found": None, "match": None,
                "error": "requests/bs4 not installed"}
    try:
        url = d["url"].format(query=urllib.parse.quote_plus(query),
                              where=urllib.parse.quote_plus(suburb), cat="")
        resp = requests.get(url, timeout=15, headers={"User-Agent": "hermes-seo-tools/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        snippet = soup.get_text(" ", strip=True)[:600]
        match = looks_like_match(snippet, query, suburb)
        return {"name": d["name"], "found": True, "match": match,
                "url": str(resp.url)[:120]}
    except Exception as e:
        return {"name": d["name"], "found": False, "match": None, "error": str(e)[:80]}


def format_report(business: str, suburb: str, results: list[dict]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"CITATION AUDIT — {business}")
    lines.append(f"Location: {suburb}")
    lines.append("=" * 60)
    found = 0
    matched = 0
    for r in results:
        status = "✓ FOUND" if r.get("found") else "✗ NOT FOUND"
        match_lbl = "✓ MATCH" if r.get("match") else ("✗ MISMATCH" if r.get("found") else "—")
        lines.append(f"  {r['name']:<20s} {status:<12s}  {match_lbl}")
        if r.get("error"):
            lines.append(f"    Error: {r['error']}")
        if r.get("url"):
            lines.append(f"    URL: {r['url']}")
        if r.get("found"): found += 1
        if r.get("match"): matched += 1
    lines.append("=" * 60)
    lines.append(f"Directories surveyed : {len(results)}")
    lines.append(f"Listings found        : {found}/{len(results)}")
    lines.append(f"NAP-likely matching   : {matched}/{found}")
    lines.append("=" * 60)
    if matched < len(results) * 0.5:
        lines.append("⚠  <50% match rate — audit NAP data across directories")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Australian citation auditor.")
    ap.add_argument("business_name", help="Registered business name")
    ap.add_argument("suburb", help="Suburb / city (e.g. Brisbane QLD)")
    ap.add_argument("--json", help="Save results as JSON")
    args = ap.parse_args()
    results = [check_directory(d, args.business_name, args.suburb) for d in AUS_DIRECTORIES]
    print(format_report(args.business_name, args.suburb, results))
    if args.json:
        out = {"business": args.business_name, "suburb": args.suburb, "results": results}
        Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
