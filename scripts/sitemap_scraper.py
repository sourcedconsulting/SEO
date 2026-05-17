#!/usr/bin/env python3
"""
sitemap_scraper.py — Discover and extract URLs from XML sitemaps.

Usage:
    python scripts/sitemap_scraper.py https://example.com
    python scripts/sitemap_scraper.py /path/to/sitemap.xml --json urls.json
    python scripts/sitemap_scraper.py https://example.com --limit 10

Supports:
  - Local sitemap XML files
  - Site root URLs  (tries /sitemap.xml, /sitemap_index.xml, robots.txt)
  - Direct sitemap or sitemap-index URLs
  - Sitemap index resolution (follows each <sitemap><loc> leaf)
  - URL deduplication

Installs: pip install requests beautifulsoup4
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path
from xml.etree import ElementTree

try:
    import requests  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# ── Chrome desktop headers ───────────────────────────────────────────────────
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


# ═══════════════════════════════════════════════════════════════════════════════
# LOW-LEVEL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def http_get(url: str, timeout: int, headers: dict | None = None) -> "requests.Response":
    return requests.get(url, timeout=timeout, headers=headers or CHROME_HEADERS)


def fetch_with_retry(url: str, timeout: int, attempts: int = 3) -> "requests.Response":
    """GET with jittered exponential backoff."""
    import random
    for i in range(attempts):
        try:
            resp = requests.get(url, timeout=timeout, headers=CHROME_HEADERS)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code if exc.response else 0
            if 400 <= i < 500:
                raise
            if i < attempts - 1:
                time.sleep((2 ** i) + random.random())
        except Exception:
            if i < attempts - 1:
                time.sleep((2 ** i) + random.random())
    raise RuntimeError(f"Failed after {attempts} attempts: {url}")


# ═══════════════════════════════════════════════════════════════════════════════
# SITEMAP XML PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def _strip_ns(tag: str) -> str:
    """Remove XML namespace prefix: {http://…}urlset → urlset."""
    if tag.startswith("{"):
        tag = tag.split("}", 1)[1]
    return tag


def _iter_with_parent(
    root: ElementTree.Element,
) -> list[tuple[ElementTree.Element, ElementTree.Element | None]]:
    """Yield (element, parent) using a manual stack — stdlib-compatible (no getparent)."""
    pairs: list[tuple[ElementTree.Element, ElementTree.Element | None]] = []
    stack: list[ElementTree.Element] = [root]
    while stack:
        node = stack.pop()
        for child in list(node):
            pairs.append((child, node))
            stack.append(child)
    return pairs


def _parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """
    Parse one sitemap XML document.

    Uses a manual parent-stack so it works with stdlib ElementTree
    (getparent() is lxml-only).

    Returns:
        urls     — <url><loc> entries
        children — <sitemap><loc> entries (sitemap index leaves)
    """
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return [], []

    urls: list[str] = []
    children: list[str] = []

    for elem, parent in _iter_with_parent(root):
        tag = _strip_ns(elem.tag)
        if tag != "loc" or not elem.text:
            continue
        text = elem.text.strip()
        if not text:
            continue
        parent_tag = _strip_ns(parent.tag) if parent is not None else ""
        if parent_tag == "sitemap":
            children.append(text)
        elif parent_tag == "url":
            urls.append(text)

    return urls, children


def parse_sitemap(xml_text: str) -> list[str]:
    """Return all <url><loc> entries from a leaf sitemap."""
    urls, _ = _parse_sitemap_xml(xml_text)
    return urls


def parse_sitemap_index(xml_text: str) -> list[str]:
    """Return all <sitemap><loc> entries from a sitemap index."""
    _, children = _parse_sitemap_xml(xml_text)
    return children


# ═══════════════════════════════════════════════════════════════════════════════
# DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

def discover_sitemap_candidates(root_url: str) -> list[str]:
    """Return ordered list of sitemap URLs to try for a site root."""
    base = root_url.rstrip("/")
    return [
        f"{base}/sitemap.xml",
        f"{base}/sitemap_index.xml",
    ]


def fetch_text(url: str, timeout: int = 20) -> str:
    """Fetch URL with retry; returns raw text or '' on total failure."""
    if not HAS_DEPS:
        print("Error: requests not installed. Run: pip install requests", file=sys.stderr)
        sys.exit(1)
    try:
        resp = fetch_with_retry(url, timeout=timeout)
        return resp.text
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response else "?"
        label = "blocked" if code in (403, 429) else "error"
        print(f"  {label.upper()}: HTTP {code} — {url}", file=sys.stderr)
        return ""
    except requests.exceptions.Timeout:
        print(f"  TIMEOUT: {url}", file=sys.stderr)
        return ""
    except Exception as exc:
        print(f"  ERROR: {exc} — {url}", file=sys.stderr)
        return ""


def parse_robots_txt(text: str) -> list[str]:
    """Extract Sitemap: directives from robots.txt."""
    return re.findall(r"(?im)^Sitemap:\s*(\S+)", text)


# ═══════════════════════════════════════════════════════════════════════════════
# CORE LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

def extract_leaves_from_index(index_xml: str, dry: bool = False) -> tuple[list[tuple[str, str]], list[str]]:
    """
    Given a sitemap-index XML, return (leaf_tuples, errors).
    leaf_tuples: [(sitemap_url, child_xml_or_empty), ...]
    """
    child_urls = parse_sitemap_index(index_xml)
    leaves = []
    errors = []
    for child_url in child_urls:
        print(f"Fetching leaf sitemap: {child_url}", file=sys.stderr)
        xml = fetch_text(child_url)
        if xml:
            leaves.append((child_url, xml))
        else:
            leaves.append((child_url, ""))
            errors.append(child_url)
    return leaves, errors


def load_input(source: str) -> tuple[list[str], str, list[str], list[str]]:
    """
    Unified entry point: accept URL, sitemap URL, or local file path.
    Returns:
        all_urls   — deduplicated flat list of page URLs
        mode_label — 'file' | 'direct' | 'discovered' | 'index'
        fetched    — list of source URLs/classes that were fetched
        errors     — list of sources that failed
    """
    # ── Local file ──────────────────────────────────────────────────────────
    p = Path(source)
    if p.exists() and p.is_file():
        xml = p.read_text(encoding="utf-8", errors="replace")
        urls = parse_sitemap(xml)
        return urls, "file", [str(p)], []

    # ── URL ─────────────────────────────────────────────────────────────────
    if not source.startswith("http"):
        print(f"Error: unrecognised input — {source}", file=sys.stderr)
        sys.exit(1)

    # Direct sitemap URL — fetch as-is
    if "sitemap" in source.lower():
        print(f"Fetching sitemap: {source}", file=sys.stderr)
        xml = fetch_text(source)
        fetched = [source]
        errors = []
        if not xml:
            return [], "direct", fetched, [source]

        child_locs = parse_sitemap_index(xml)
        if child_locs:
            # It's an index — follow all leaves
            print(f"Sitemap index detected — {len(child_locs)} leaf sitemaps.", file=sys.stderr)
            all_urls: list[str] = []
            for child_url in child_locs:
                print(f"Fetching leaf: {child_url}", file=sys.stderr)
                leaf_xml = fetch_text(child_url)
                if leaf_xml:
                    all_urls.extend(parse_sitemap(leaf_xml))
                    fetched.append(child_url)
                else:
                    errors.append(child_url)
            return all_urls, "index", fetched, errors

        # Leaf sitemap
        urls = parse_sitemap(xml)
        return urls, "direct", fetched, [source] if not xml else []

    # ── Site root — discovery path ──────────────────────────────────────────
    print(f"Discovering sitemap for: {source}", file=sys.stderr)
    candidates = discover_sitemap_candidates(source)
    for candidate in candidates:
        print(f"Trying: {candidate}", file=sys.stderr)
        xml = fetch_text(candidate)
        if xml:
            child_locs = parse_sitemap_index(xml)
            if child_locs:
                print(f"Sitemap index found — {len(child_locs)} leaves.", file=sys.stderr)
                all_urls = []
                for child_url in child_locs:
                    print(f"Fetching leaf: {child_url}", file=sys.stderr)
                    leaf_xml = fetch_text(child_url)
                    if leaf_xml:
                        all_urls.extend(parse_sitemap(leaf_xml))
                        fetched.append(candidate)
                        fetched.append(child_url)
                    else:
                        errors.append(child_url)
                return all_urls, "discovered", fetched, errors

            urls = parse_sitemap(xml)
            if urls:
                return urls, "discovered", [candidate], []

    # Try robots.txt
    robots_url = source.rstrip("/") + "/robots.txt"
    print(f"Trying robots.txt: {robots_url}", file=sys.stderr)
    robots = fetch_text(robots_url, timeout=10)
    if robots:
        sitemaps = parse_robots_txt(robots)
        for sm in sitemaps:
            print(f"robots.txt → sitemap: {sm}", file=sys.stderr)
            xml = fetch_text(sm)
            if xml:
                child_locs = parse_sitemap_index(xml)
                if child_locs:
                    all_urls = []
                    for child_url in child_locs:
                        leaf_xml = fetch_text(child_url)
                        if leaf_xml:
                            all_urls.extend(parse_sitemap(leaf_xml))
                            fetched.append(sm)
                            fetched.append(child_url)
                        else:
                            errors.append(child_url)
                    return all_urls, "discovered", fetched, errors
                urls = parse_sitemap(xml)
                if urls:
                    return urls, "discovered", [sm], []

    return [], "discovered", [], ["all sitemap candidates failed"]


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def format_report(source: str, all_urls: list[str], mode: str,
                  fetched: list[str], errors: list[str],
                  limit: int | None = None) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"SITEMAP SCRAPER — {source}")
    lines.append(f"Mode: {mode}")
    lines.append("=" * 60)

    for fsrc in fetched:
        lines.append(f"Fetched: {fsrc}")

    limit_note = f" (limited to {limit})" if limit else ""
    lines.append(f"Total URLs : {len(all_urls)}{limit_note}")
    unique = len(set(all_urls))
    if unique != len(all_urls):
        lines.append(f"Unique URLs: {unique}  ({len(all_urls) - unique} duplicates removed)")
    else:
        lines.append(f"Unique URLs: {unique}")

    if errors:
        lines.append("Errors:")
        for err in errors:
            lines.append(f"  ✗ {err}")

    lines.append("=" * 60)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main(argv=None):
    ap = argparse.ArgumentParser(description="Discover and extract URLs from XML sitemaps.")
    ap.add_argument("source", nargs="?", default=None,
                    help="Site root URL, direct sitemap URL, or local XML file path")
    ap.add_argument("--input", dest="input_flag", default=None,
                    help="Alternative: site root URL or local sitemap XML file (overrides positional)")
    ap.add_argument("--output", default=None,
                    help="Write newline-delimited URL list to this file")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="Write structured JSON report to this file")
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop after N URLs (testing/sampling)")
    ap.add_argument("--ua-simple", action="store_true",
                    help="Use simple UA instead of chrome headers")
    args = ap.parse_args(argv)

    source = args.input_flag or args.source
    if not source:
        ap.print_help()
        sys.exit(1)

    if args.ua_simple:
        CHROME_HEADERS.clear()
        CHROME_HEADERS["User-Agent"] = "hermes-seo-tools/2.0"

    all_urls, mode, fetched, errors = load_input(source)

    if args.limit and args.limit > 0:
        all_urls = all_urls[:args.limit]

    print(format_report(source, all_urls, mode, fetched, errors, args.limit))

    # Print URL list to stdout
    for u in all_urls:
        print(u)

    # Save outputs
    if args.output:
        Path(args.output).write_text("\n".join(all_urls) + "\n", encoding="utf-8")
        print(f"URL list saved → {args.output}")

    if args.json_out:
        payload = {
            "source": source,
            "mode": mode,
            "count": len(all_urls),
            "unique": len(set(all_urls)),
            "urls": all_urls,
            "sources": {},
            "errors": errors,
        }
        # Build per-source counts from fetched list
        for fsrc in fetched:
            payload["sources"][fsrc] = "ok"
        Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"JSON saved → {args.json_out}")


if __name__ == "__main__":
    main()
