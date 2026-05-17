from typing import Any
\
#!/usr/bin/env python3
"""
backlink_checker.py — Lightweight backlink profile signals (no paid API required).

Usage:
    python scripts/backlink_checker.py https://example.com
    python scripts/backlink_checker.py https://example.com --json

Modes of operation:
  1. Wayback/CDX check — has the domain been indexed historically?
  2. Google cache check — is the domain in the Google index?
  3. Quick search footprint — number of pages indexed approximation.

NOTE: This is a signal-level tool, NOT a full backlink scraper.
      For full backlink data use Ahrefs/Semrush/Moz APIs.
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

try:
    import requests  # type: ignore
    HAS_REQ = True
except ImportError:
    HAS_REQ = False


CDX_URL = "https://web.archive.org/cdx/search/cdx"


def wayback_indexed(domain: str) -> dict[str, Any]:
    slug = domain.replace("https://", "").replace("http://", "").rstrip("/")
    params = {"url": slug + "/*", "fl": "timestamp,statuscode,mimetype",
              "output": "json", "limit": "3"}
    try:
        url = CDX_URL + "?" + urllib.parse.urlencode(params)
        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
        rows = data[1:] if len(data) > 1 else []
        return {
            "indexed": len(rows) > 0,
            "first_seen": rows[0][0] if rows else None,
            "last_seen":  rows[-1][0] if rows else None,
            "sample_pages": len(rows),
        }
    except Exception as e:
        return {"indexed": None, "error": str(e)[:120]}


def google_indexed(domain: str) -> dict[str, Any]:
    if not HAS_REQ:
        return {"indexed": None, "note": "requests not installed"}
    try:
        slug = urllib.parse.quote_plus("site:" + domain.replace("https://", "").replace("http://", "").rstrip("/"))
        r = requests.get(
            f"https://www.google.com/search?q={slug}&num=1",
            headers={"User-Agent": "Mozilla/5.0 (compatible; hermes-seo-tools/1.0)"},
            timeout=10
        )
        text = r.text.lower()
        no_results = "did not return any results" in text or "no results found" in text
        return {
            "indexed": not no_results,
            "http_code": r.status_code,
        }
    except Exception as e:
        return {"indexed": None, "error": str(e)[:120]}


def format_report(domain: str, wb: dict, gi: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"BACKLINK PROFILE SIGNALS — {domain}")
    lines.append("=" * 60)

    lines.append(f"\n  Wayback Machine index")
    if "error" in wb:
        lines.append(f"    ✗ Error: {wb['error']}")
    elif wb.get("indexed"):
        lines.append(f"    ✓ First seen  : {wb.get('first_seen', 'N/A')}")
        lines.append(f"    ✓ Last seen   : {wb.get('last_seen', 'N/A')}")
    else:
        lines.append("    ✗ Not indexed in Wayback")

    lines.append(f"\n  Google index check")
    if "error" in gi:
        lines.append(f"    ✗ Error: {gi['error']}")
    elif gi.get("indexed") is True:
        lines.append("    ✓ Appears in Google index")
    elif gi.get("indexed") is False:
        lines.append("    ✗ NOT found in Google search results")
    else:
        lines.append(f"    ? Unable to determine ({gi.get('note', 'unknown')})")

    if wb.get("error") or gi.get("error"):
        lines.append("\n  ⚠  If errors appear above, check IP / firewall — may be rate-limited.")

    lines.append(f"\n{'=' * 60}")
    lines.append("These are quick signals, not a full backlink profile.")
    lines.append("For complete data: Ahrefs, Semrush, Moz, Majestic.")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Lightweight backlink/domain signals.")
    ap.add_argument("domain", help="Domain e.g. https://example.com")
    ap.add_argument("--json", help="Save JSON output")
    args = ap.parse_args()
    wb = wayback_indexed(args.domain)
    gi = google_indexed(args.domain)
    print(format_report(args.domain, wb, gi))
    if args.json:
        out = {"domain": args.domain, "wayback": wb, "google": gi}
        Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nJSON → {args.json}")


if __name__ == "__main__":
    main()
