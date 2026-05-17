#!/usr/bin/env python3
"""
seo_score.py — Single-page on-page SEO scorecard.

Usage:
    python scripts/seo_score.py https://example.com/page
    python scripts/seo_score.py /path/to/local/file.html

Hard checks (must pass):
  - <title> present and 50-70 chars long
  - <meta name="description"> present
  - At least one H1
  - Image <img alt=""> coverage >= 80%

Installs: pip install beautifulsoup4 lxml requests
"""

import sys
import os
import re
import argparse
from pathlib import Path


def get_html(url_or_path: str) -> str:
    """Fetch URL or read local HTML file."""
    if url_or_path.startswith("http"):
        try:
            import requests  # type: ignore
            r = requests.get(url_or_path, timeout=15)
            r.raise_for_status()
            return r.text
        except ImportError:
            print("Skipping URL fetch, requests not installed.")
            return ""
        except Exception as e:
            print(f"Error fetching URL: {e}")
            return ""
    else:
        p = Path(url_or_path)
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace")
        print(f"File not found: {url_or_path}")
        return ""


def analyse(html: str, url: str = "") -> dict:
    from bs4 import BeautifulSoup  # type: ignore

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


def print_report(r: dict) -> None:
    level_icon = {"critical": "X", "warning": "!", "info": "i"}
    status_icon = "PASS" if r["score"] >= 70 else "FAIL"

    print(f"\n{'=' * 50}")
    print(f"  SEO Scorecard  --  {r['url']}")
    print(f"{'=' * 50}")
    print(f"\n  Score: {r['score']:3d}/100  {status_icon}")
    print(f"\n  Title:       {r['title'][:70]}")
    print(f"  Title chars: {r['title_len']}")
    print(f"  Description: {r['meta_desc'][:70]}")
    print(f"  H1s found:   {r['h1_hits']}")
    print(f"  Headings:    {r['heading_count']}")
    if r["images"]:
        print(f"  Images:      {r['images']} total, "
              f"{r['alt_coverage_pct']}% with alt text")
    else:
        print(f"  Images:      none")

    print(f"\n  Issues ({len(r['issues'])}):")
    for issue in r["issues"]:
        icon = level_icon.get(issue["severity"], " ")
        print(f"    [{icon}] [{issue['severity']:8s}] {issue['msg']}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Single-page on-page SEO scorecard"
    )
    parser.add_argument("target",
                        help="URL or local HTML file path to audit")
    args = parser.parse_args()

    html = get_html(args.target)
    if not html.strip():
        print(f"No HTML content to analyse: {args.target}")
        sys.exit(1)

    report = analyse(html, args.target)
    print_report(report)
