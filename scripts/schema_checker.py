\
#!/usr/bin/env python3
"""
schema_checker.py — Validate JSON-LD structured data on a page.

Usage:
    python scripts/schema_checker.py https://example.com
    python scripts/schema_checker.py /path/to/local/file.html --check local-business service

Checks for:
  - Presence of at least one JSON-LD block
  - Required @type for known schema types
  - Common mandatory fields per schema type

Installs: pip install beautifulsoup4 requests
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import requests  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore
    HAS_BS = True
except ImportError:
    HAS_BS = False


REQUIRED_FIELDS = {
    "LocalBusiness": ["name", "address"],
    "Service":       ["name", "provider"],
    "Organization":  ["name"],
    "WebSite":       ["name", "url"],
    "Article":       ["headline", "author"],
    "FAQPage":       ["mainEntity"],
    "BreadcrumbList":["itemListElement"],
}

SCHEMA_ALIASES = {
    "local-business": "LocalBusiness",
    "service":        "Service",
    "org":            "Organization",
    "website":        "WebSite",
    "article":        "Article",
    "faq":            "FAQPage",
    "breadcrumb":     "BreadcrumbList",
}


def load_html(url_or_path: str) -> str:
    if url_or_path.startswith("http"):
        if not HAS_BS:
            print("requests/beautifulsoup4 required for URL checks.")
            return ""
        try:
            r = requests.get(url_or_path, timeout=15, headers={"User-Agent": "hermes-seo/1.0"})
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"Fetch error: {e}")
            return ""
    p = Path(url_or_path)
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def extract_jsonld(html: str) -> list[dict]:
    if not HAS_BS:
        return []
    soup = BeautifulSoup(html, "lxml")
    blocks = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
            if isinstance(data, dict):
                blocks.append(data)
            elif isinstance(data, list):
                blocks.extend(data)
        except (json.JSONDecodeError, TypeError):
            pass
    return blocks


def get_type(block: dict) -> str | None:
    t = block.get("@type")
    if isinstance(t, list):
        return t[0]
    return t


def validate_block(block: dict, check_types: list[str]) -> list[str]:
    issues = []
    stype = get_type(block)
    if not stype:
        issues.append("Missing @type")
        return issues
    resolved = [SCHEMA_ALIASES.get(t, t) for t in check_types]
    if stype not in resolved:
        return issues  # not a type we're checking
    req = REQUIRED_FIELDS.get(stype, [])
    present_keys = set(block.keys())
    for field in req:
        if field not in present_keys:
            issues.append(f"Missing required field '{field}' on @type={stype}")
    return issues


def format_report(url: str, blocks: list[dict],
                  results: list[tuple[str, list[str]]]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("SCHEMA VALIDATOR")
    lines.append(f"Source: {url}")
    lines.append(f"JSON-LD blocks found : {len(blocks)}")
    lines.append("=" * 60)
    for (stype, issues) in results:
        typ = stype or "(detecting…)"
        if issues:
            lines.append(f"\n  @type={typ}")
            for iss in issues:
                lines.append(f"    ⚠  {iss}")
        else:
            lines.append(f"\n  @type={typ}  ✓ all required fields present")
    total_issues = sum(len(i) for _, i in results)
    lines.append(f"\n{'=' * 60}")
    lines.append(f"Total issues: {total_issues}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url_or_file", help="URL or local HTML file")
    ap.add_argument("--check", nargs="*",
                    help="Schema types to verify (local-business, service, org, …)")
    ap.add_argument("--json-out", help="Save full JSON-LD blocks as JSON")
    args = ap.parse_args()
    if not args.check:
        args.check = list(SCHEMA_ALIASES.keys())
    check_types = args.check
    html = load_html(args.url_or_file)
    if not html:
        sys.exit(1)
    blocks = extract_jsonld(html)
    if not blocks:
        print("No JSON-LD blocks found on this page.")
        print("Add <script type=\"application/ld+json\">…</script> to enable rich results.")
        sys.exit(0)
    results = [(get_type(b) or "", validate_block(b, check_types)) for b in blocks]
    print(format_report(args.url_or_file, blocks, results))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(blocks, indent=2), encoding="utf-8")
        print(f"\nFull blocks → {args.json_out}")


if __name__ == "__main__":
    main()
