#!/usr/bin/env python3
"""
seo_score.py — On-page SEO scorecard.

Usage (single URL — unchanged):
    python scripts/seo_score.py https://example.com
    python scripts/seo_score.py /path/to/local/file.html --json score.json

Usage (bulk file — one URL or path per line):
    python scripts/seo_score.py --bulk urls.txt --json-out results.json

Usage (sitemap — auto-discover + audit all pages):
    python scripts/seo_score.py --sitemap https://example.com --json-out results.json --limit 25

Hard checks (must pass):
  - <title> present and 50-70 chars long
  - <meta name="description"> present
  - At least one H1
  - Image <img alt=""> coverage >= 80%

Installs: pip install beautifulsoup4 lxml requests
Standard-lib fallback: BeautifulSoup import is deferred (missing deps → graceful skip).
NOTE: local HTML file single-page mode works without any installs.
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import requests  # type: ignore
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup  # type: ignore
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

CHROME_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/132.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;"
                       "q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT":             "1",
    "Connection":      "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":  "document",
    "Sec-Fetch-Mode":  "navigate",
    "Sec-Fetch-Site":  "cross-site",
}


def _http_get(url: str, timeout: int = 15) -> str:
    """Fetch URL with chrome headers; returns text or '' on failure."""
    if not HAS_REQUESTS:
        return ""
    try:
        r = requests.get(url, timeout=timeout, headers=CHROME_HEADERS)
        r.raise_for_status()
        return r.text
    except Exception:
        return ""


def _fetch_html(source: str) -> str:
    """Fetch or read HTML from a URL or local file path."""
    if source.startswith("http"):
        return _http_get(source)
    p = Path(source)
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# SEO ANALYSIS (unchanged core)
# ═══════════════════════════════════════════════════════════════════════════════

def analyse(html: str, url: str = "") -> dict:
    if not HAS_BS4:
        return {"url": url or "unknown", "score": 0,
                "error": "beautifulsoup4 not installed",
                "title": "", "title_len": 0, "meta_desc": "",
                "desc_len": 0, "h1_hits": 0, "heading_count": 0,
                "images": 0, "alt_coverage_pct": None, "issues": []}

    soup = BeautifulSoup(html, "lxml")
    issues = []
    score = 100

    # Hard checks
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    title_len = len(title)

    if not title:
        issues.append({"severity": "critical", "msg": "Missing <title>"})
        score -= 30
    elif not (50 <= title_len <= 70):
        issues.append({"severity": "warning",
                        "msg": f"Title length {title_len} chars (target 50-70)"})
        score -= 15

    meta_desc = soup.find("meta", attrs={"name": "description", "content": True})
    desc = meta_desc["content"] if meta_desc else ""
    if not desc:
        issues.append({"severity": "critical", "msg": "Missing meta description"})
        score -= 25

    h1s = soup.find_all("h1")
    if not h1s:
        issues.append({"severity": "critical", "msg": "Missing <h1>"})
        score -= 20

    headings = soup.find_all(re.compile("^h[1-3]$"))
    if len(headings) < 2:
        issues.append({"severity": "warning",
                        "msg": "Fewer than 2 heading tags (<h1>-<h3>)"})
        score -= 10

    images = soup.find_all("img")
    total_imgs = len(images)
    missing_alt = sum(1 for img in images if not img.get("alt", "").strip())
    if total_imgs > 0:
        alt_coverage = (total_imgs - missing_alt) / total_imgs * 100
        if alt_coverage < 80:
            issues.append({"severity": "warning",
                            "msg": f"Image alt coverage: {alt_coverage:.0f}% "
                                   f"({missing_alt}/{total_imgs} missing)"})
            score -= 10
    elif total_imgs == 0:
        issues.append({"severity": "info", "msg": "No <img> tags found"})

    # Soft checks
    if not soup.html or not soup.html.get("lang"):
        issues.append({"severity": "info",
                        "msg": "Missing lang attribute on <html>"})
        score -= 5

    canonical = soup.find("link", rel="canonical", href=True)
    if not canonical:
        issues.append({"severity": "info", "msg": "No canonical URL"})
        score -= 5

    score = max(0, min(100, score))

    return {
        "url": url or "unknown",
        "score": score,
        "title": title,
        "title_len": title_len,
        "meta_desc": desc[:120],
        "desc_len": len(desc),
        "h1_hits": len(h1s),
        "heading_count": len(headings),
        "images": total_imgs,
        "alt_coverage_pct": round(
            (total_imgs - missing_alt) / total_imgs * 100, 1
        ) if total_imgs else None,
        "issues": issues,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BULK HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _tier(score: int) -> str:
    if score >= 80: return "excellent"
    if score >= 70: return "good"
    if score >= 50: return "fair"
    return "poor"


def _format_single(url: str, result: dict) -> str:
    icon = "X" if result["score"] < 70 else "!"
    tier = _tier(result["score"])
    lines = [
        f"\n--- {result['score']:3d}/100  [{tier:8s}]  {url} ---",
        f"  Title:       {result.get('title','')[:70]}",
        f"  Description: {result.get('meta_desc','')[:70]}",
        f"  H1s:         {result.get('h1_hits',0)}",
    ]
    if result.get("images", 0):
        alt = result.get("alt_coverage_pct")
        lines.append(f"  Images:      {result['images']} total, "
                     f"{alt}% with alt text" if alt
                     else f"  Images:      {result['images']} total")
    for issue in result.get("issues", []):
        lines.append(f"  [{icon}] [{issue['severity']:8s}] {issue['msg']}")
    return "\n".join(lines)


def run_bulk(targets: list[dict]) -> list[dict]:
    """Run analyse() on every target entry with eager failure on missing HTML."""
    results = []
    for entry in targets:
        if isinstance(entry, str):
            entry = {"url": entry}
        src = entry.get("url", "")
        html = _fetch_html(src)
        if not html or not html.strip():
            results.append({
                "url": src, "score": 0,
                "error": "No HTML content", "title": "", "title_len": 0,
                "meta_desc": "", "desc_len": 0, "h1_hits": 0,
                "heading_count": 0, "images": 0, "alt_coverage_pct": None,
                "issues": [{"severity": "critical", "msg": f"No HTML content fetched: {src}"}],
            })
            continue
        r = analyse(html, src)
        results.append(r)
    return results


def print_bulk_summary(results: list[dict], limit: int | None = None) -> str:
    lines = []
    shown = results[:limit] if limit else results
    lines.append("=" * 58)
    lines.append(f"BULK SEO SCORECARD  —  {len(results)} URL(s) scanned")
    lines.append("=" * 58)
    for r in shown:
        tier = _tier(r["score"])
        status = "PASS" if r["score"] >= 70 else "FAIL"
        lines.append(f"  {r['url'][:50]:<50s}  {r['score']:3d}/100  {status}  [{tier}]")
    if limit and len(results) > limit:
        lines.append(f"  ... and {len(results) - limit} more")
    scores = [r["score"] for r in results]
    avg = sum(scores) / len(scores) if scores else 0
    passed  = sum(1 for s in scores if s >= 70)
    failed  = len(scores) - passed
    lines.append("_" * 58)
    lines.append(f"  Average score   : {avg:.0f}/100")
    lines.append(f"  Pass (>= 70)    : {passed}")
    lines.append(f"  Fail (< 70)     : {failed}")
    lines.append("=" * 58)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def print_report(r: dict) -> str:
    level_icon = {"critical": "X", "warning": "!", "info": "i"}
    status_icon = "PASS" if r["score"] >= 70 else "FAIL"

    lines = []
    lines.append("=" * 50)
    lines.append(f"  SEO Scorecard  --  {r['url']}")
    lines.append("=" * 50)
    lines.append(f"\n  Score: {r['score']:3d}/100  {status_icon}")
    lines.append(f"\n  Title:       {r['title'][:70]}")
    lines.append(f"  Title chars: {r['title_len']}")
    lines.append(f"  Description: {r['meta_desc'][:70]}")
    lines.append(f"  H1s found:   {r['h1_hits']}")
    lines.append(f"  Headings:    {r['heading_count']}")
    if r["images"]:
        lines.append(f"  Images:      {r['images']} total, "
                     f"{r['alt_coverage_pct']}% with alt text")
    else:
        lines.append(f"  Images:      none")
    lines.append(f"\n  Issues ({len(r['issues'])}):")
    for issue in r["issues"]:
        icon = level_icon.get(issue["severity"], " ")
        lines.append(f"    [{icon}] [{issue['severity']:8s}] {issue['msg']}")
    lines.append("")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="On-page SEO scorecard")
    ap.add_argument("target", nargs="?", default=None,
                    help="URL or local HTML file path to audit")
    ap.add_argument("--json", dest="json_out",
                    help="Save JSON result for single-page audit")
    ap.add_argument("--bulk", dest="bulk_file",
                    help="File with one URL or local HTML path per line")
    ap.add_argument("--sitemap", dest="sitemap_url", default=None,
                    help="Auto-discover sitemap from site root URL and audit all pages")
    ap.add_argument("--json-out", dest="json_bulk",
                    help="Save bulk/sitemap results as JSON")
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop after N URLs (sitemap/bulk)")
    args = ap.parse_args()

    # ── Bulk file mode ───────────────────────────────────────────────────────
    if args.bulk_file:
        bulk_path = Path(args.bulk_file)
        if not bulk_path.exists():
            print(f"Bulk file not found: {args.bulk_file}")
            sys.exit(1)
        targets = [
            {"url": line.strip()}
            for line in bulk_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not targets:
            print("No URLs found in bulk file.")
            sys.exit(0)
        results = run_bulk(targets)
        print(print_bulk_summary(results, args.limit))
        if args.json_bulk:
            payload = {
                "mode": "bulk",
                "source": str(bulk_path),
                "total_urls": len(results),
                "results": results,
                "average_score": round(sum(r["score"] for r in results) / len(results), 1)
                                  if results else 0,
                "pass_count": sum(1 for r in results if r["score"] >= 70),
                "fail_count": sum(1 for r in results if r["score"] < 70),
            }
            Path(args.json_bulk).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"\nJSON saved → {args.json_bulk}")

    # ── Sitemap mode ─────────────────────────────────────────────────────────
    elif args.sitemap_url:
        if not HAS_REQUESTS:
            print("Error: requests required for sitemap mode. Run: pip install requests", file=sys.stderr)
            sys.exit(1)

        base = args.sitemap_url.rstrip("/")
        candidates = [
            f"{base}/sitemap.xml",
            f"{base}/sitemap_index.xml",
            base + "/robots.txt",
        ]
        all_urls: list[str] = []

        for candidate in candidates:
            print(f"Checking: {candidate}", file=sys.stderr)
            raw = _http_get(candidate, timeout=15)
            if not raw:
                continue

            if candidate.endswith("/robots.txt"):
                sm_re = re.findall(r"(?im)^Sitemap:\s*(\S+)", raw)
                for sm in sm_re:
                    sitemap_xml = _http_get(sm, timeout=20)
                    if sitemap_xml:
                        all_urls.extend(_sitemap_locs_from_xml(sitemap_xml))
            else:
                locs, child_locs = _sitemap_locs_and_children(raw)
                if child_locs:
                    # index — follow each leaf
                    for child_url in child_locs:
                        leaf_raw = _http_get(child_url, timeout=20)
                        if leaf_raw:
                            all_urls.extend(_sitemap_locs_from_xml(leaf_raw))
                else:
                    all_urls.extend(locs)

            if all_urls:
                break

        all_urls = list(dict.fromkeys(all_urls))  # dedicated order-preserving dedup

        if args.limit and args.limit > 0:
            all_urls = all_urls[:args.limit]

        if not all_urls:
            print(f"No URLs found in sitemap for: {args.sitemap_url}")
            sys.exit(1)

        print(f"\nSitemap discovered: {len(all_urls)} unique URL(s)\n",
              file=sys.stderr)
        results = run_bulk([{"url": u} for u in all_urls])
        print(print_bulk_summary(results, args.limit))
        if args.json_bulk:
            payload = {
                "mode": "sitemap",
                "source": args.sitemap_url,
                "total_urls": len(results),
                "results": results,
                "average_score": round(sum(r["score"] for r in results) / len(results), 1)
                                  if results else 0,
                "pass_count": sum(1 for r in results if r["score"] >= 70),
                "fail_count": sum(1 for r in results if r["score"] < 70),
            }
            Path(args.json_bulk).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"\nJSON saved → {args.json_bulk}")

    # ── Single-page mode (unchanged) ─────────────────────────────────────────
    elif args.target:
        html = _fetch_html(args.target)
        if not html or not html.strip():
            print(f"No HTML content to analyse: {args.target}")
            sys.exit(1)
        result = analyse(html, args.target)
        print(print_report(result))
        if args.json_out:
            Path(args.json_out).write_text(
                json.dumps(result, indent=2), encoding="utf-8")
    else:
        ap.print_help()
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# SITEMAP XML PARSING HELPERS (used by --sitemap mode)
# ═══════════════════════════════════════════════════════════════════════════════

import xml.etree.ElementTree as ET


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if tag.startswith("{") else tag


def _sitemap_xml_children(xml_text: str) -> tuple[list[str], list[str]]:
    """
    Parse one sitemap XML with stdlib ElementTree (no lxml, no getparent).
    Returns (leaf_urls, sitemap_index_children).
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return [], []

    leaf_urls: list[str] = []
    child_urls: list[str] = []

    # Manual depth-first traversal tracking the parent tag of each child
    stack: list[tuple[ET.Element, str]] = [(root, "")]
    while stack:
        node, parent_tag = stack.pop()
        for child in list(node):
            child_tag = _strip_ns(child.tag)
            if child_tag == "loc" and child.text and child.text.strip():
                loc = child.text.strip()
                if parent_tag == "sitemap":
                    child_urls.append(loc)
                elif parent_tag == "url":
                    leaf_urls.append(loc)
            stack.append((child, child_tag))

    return leaf_urls, child_urls


def _sitemap_locs_from_xml(xml_text: str) -> list[str]:
    urls, _ = _sitemap_xml_children(xml_text)
    return urls


def _sitemap_locs_and_children(xml_text: str) -> tuple[list[str], list[str]]:
    return _sitemap_xml_children(xml_text)


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
