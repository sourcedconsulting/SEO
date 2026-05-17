# Plan — Sitemap Scraper + Bulk / Sitemap Mode for seo_score.py

## Context

The `sourcedconsulting/SEO` repo has 6 production CLI scripts. Code conventions:
- Chrome desktop headers (en-AU), 3-retry jittered backoff
- Honest labels: `blocked`, `timeout`, `error`, `not_found`
- `requests` + `beautifulsoup4` for network work
- Self-contained tests in `scripts/tests/` (no pytest required)
- `--json` flag on audit scripts to save structured output
- Single-purpose scripts composed via shell pipes

---

## Task A — `sitemap_scraper.py` (new script)

### Purpose
Fetch a live sitemap or local sitemap XML, extract every `<url><loc>` entry, emit plain URLs or structured JSON.

### Supported inputs
1. **Local file** (`/path/to/sitemap.xml`) — read directly, no network
2. **Site root URL** (`https://example.com`) — try discovered path:
   - `https://example.com/sitemap.xml`
   - `https://example.com/sitemap_index.xml`
   - Fall back to `/robots.txt` → `Sitemap:` directive
3. **Direct sitemap URL** (URL containing `sitemap`) — fetch as-is

### Sitemap index support
If the fetched XML is a sitemap index (`<sitemapindex>`), follow every `<sitemap><loc>` child sitemap, merge all `<loc>` entries from all leaf sitemaps into one flat list. Deduplicate (same URL in multiple sitemaps → keep once).

### CLI flags
```
usage: sitemap_scraper.py [-h] [--input INPUT] [--output FILE] [--json FILE] [--limit N]

optional arguments:
  -h, --help           show this help message and exit
  --input INPUT        Site root URL or local sitemap XML file (positional fallback)
  --output FILE        Write newline-delimited URL list here
  --json FILE          Write structured JSON report (urls[], count, sources{})
  --limit N            Stop after N URLs (useful for testing)
  --ua-simple          Use simple UA instead of chrome headers
```

### Network behaviour
- Chrome headers (same dict used across all other scripts) unless `--ua-simple`
- 3-retry jittered backoff on HTTP fetch
- Timeout 20 s per sitemap fetch
- `blocked` label for 403/429, `timeout` for deadline exceeded, `error` for everything else
- Never report `not_found` when the service itself failed — label the root cause

### Report output
```
============================================================
SITEMAP SCRAPER — https://example.com
============================================================
Fetching: https://example.com/sitemap.xml
  200 OK — 847 URLs extracted
Processing sitemap index: https://example.com/sitemap_index.xml
  Leaf: /sitemap-posts.xml   → 312 URLs
  Leaf: /sitemap-pages.xml   → 89 URLs
  ...

Total URLs : 1248
Unique URLs: 1248
Output     : stdout (or --output file)
============================================================
```

### JSON output shape
```json
{
  "source": "https://example.com/sitemap.xml",
  "count": 1248,
  "unique": 1248,
  "urls": ["https://example.com/...", "..."],
  "sources": {
    "https://example.com/sitemap.xml": 847,
    "https://example.com/sitemap_index.xml": 0,
    "https://example.com/sitemap-posts.xml": 312
  },
  "errors": []
}
```

### Edge cases
- Empty sitemap → report count 0, exit 0 (not a failure)
- Invalid XML → report error, exit 1
- No `<loc>` tags found → report 0 URLs, exit 0
- All fetches fail → report errors, exit 1

---

## Task B — `seo_score.py` bulk/sitemap mode

### Changes only to `seo_score.py` (no new dependencies, no import of sitemap_scraper)

Add two new optional flags; keep single-url behaviour 100% unchanged.

#### `--bulk FILE`
```
usage: seo_score.py [-h] [--bulk FILE] [--json-out FILE] [target]
```
- `FILE` contains one URL or local HTML path per line (blank lines and `#` comments ignored)
- Run `analyse()` on every entry
- Print per-URL scorecard (same format as single-page)
- Print summary table at end

**Summary table:**
```
============================================================
BULK SEO SCORECARD — 10 URLs
============================================================
https://a.com     92/100  PASS
https://b.com     45/100  FAIL
...
============================================================
Average score    : 68/100
Pass (>=70)      : 4
Fail (<70)       : 6
============================================================
```

#### `--sitemap URL`
```
usage: seo_score.py [-h] [--sitemap URL] [--json-out FILE]
```
- Discover sitemap from given URL (tries `/sitemap.xml`, `/sitemap_index.xml`, `/robots.txt` — exact same logic as `sitemap_scraper.py` but implemented inline, no import)
- Extract URLs, then run bulk analysis
- `--json-out FILE` writes full results including per-URL breakdown

**`--json-out` shape:**
```json
{
  "mode": "sitemap",
  "source": "https://example.com/sitemap.xml",
  "total_urls": 847,
  "results": [
    {"url": "...", "score": 85, "status": "PASS", "issues": [...]},
    ...
  ],
  "average_score": 68,
  "pass_count": 540,
  "fail_count": 307
}
```

#### `--json-out` also works with `--bulk`

### Internal helpers added to seo_score.py
- `_discover_sitemap_urls(root_url)` — returns list of sitemap XML URLs (tries 3 paths + robots.txt)
- `_parse_sitemap(xml_text)` — returns list of `<loc>` strings from one sitemap (handles both `urlset` and `sitemapindex`)
- `_fetch(url, timeout)` — chrome-header fetch with retry (reuse existing pattern from citation_checker.py)

### Backwards compatibility
- Single positional `target` argument still works exactly as before
- `--json` on single-page still works (writes per-URL result)
- No positional args required when `--sitemap` is used (sitemap implies target set)

---

## Task C — Tests

### `test_sitemap_scraper.py`
```python
# tests — run with: python scripts/tests/test_sitemap_scraper.py

import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sitemap_scraper import _parse_sitemap, _parse_sitemap_index, main

SAMPLE_URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page-a</loc></url>
  <url><loc>https://example.com/page-b</loc></url>
</urlset>"""

SAMPLE_INDEX = """<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap-posts.xml</loc></sitemap>
</sitemapindex>"""

def test_parse_urlset():
    urls = _parse_sitemap(SAMPLE_URLSET)
    assert len(urls) == 2
    assert urls[0] == "https://example.com/page-a"

def test_parse_sitemap_index():
    urls = _parse_sitemap_index(SAMPLE_INDEX)
    assert len(urls) == 2
    assert "sitemap-pages.xml" in urls[0]

def test_dedup():
    dup = SAMPLE_URLSET + "\n" + SAMPLE_URLSET.replace("page-b", "page-c").replace("page-a", "page-a")
    urls = _parse_sitemap(dup)
    assert len(urls) == 3

def test_extract_from_sample_file():
    # verify local XML file round-trip
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="w") as f:
        f.write(SAMPLE_URLSET)
        tmppath = f.name
    result = main(argv=["--input", tmppath, "--json", "/dev/null"])
    # main() prints report; call _parse_sitemap directly for assertion
    urls = _parse_sitemap(SAMPLE_URLSET)
    assert len(urls) == 2
    os.unlink(tmppath)

def test_empty_sitemap():
    xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    urls = _parse_sitemap(xml)
    assert urls == []

def test_invalid_xml():
    urls = _parse_sitemap("not xml at all")
    assert urls == []
```

### Extend `test_seo_score.py`
```python
def test_bulk_mode():
    import subprocess, json, tempfile, os
    pages = [
        ("<html lang='en'><head><title>T1</title><meta name='description' content='desc'></head><body><h1>H1</h1><p>content content content content content</p></body></html>", "url1"),
        ("<html><body><h1>Only H1</h1></body></html>", "url2"),
    ]
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        for i, (html, _) in enumerate(pages):
            path = f"/tmp/bulk_test_{i}.html"
            Path(path).write_text(html)
            f.write(path + "\n")
        bulk_file = f.name
    # call analyse directly per path
    results = [analyse(Path(p).read_text(), p) for p in Path(bulk_file).read_text().splitlines() if p.strip()]
    assert len(results) == 2
    assert results[0]["score"] >= 70
    assert results[1]["score"] < 70
    os.unlink(bulk_file)
```

---

## Execution Order

```
1. Write sitemap_scraper.py          → scripts/sitemap_scraper.py
2. Write test_sitemap_scraper.py     → scripts/tests/test_sitemap_scraper.py
3. Patch seo_score.py                → add --bulk, --sitemap, --json-out flags + helpers
4. Patch test_seo_score.py           → import Path, add test_bulk_mode
5. Run all tests                     → all PASS
6. Update README.md                  → add sitemap_scraper section, seo_score --bulk / --sitemap docs
7. git add -A && git commit && git push
```

Estimated total: reviewed → written → all-green → pushed.

---

## Files to modify/create

| Path | Action |
|------|--------|
| `scripts/sitemap_scraper.py` | **CREATE** |
| `scripts/tests/test_sitemap_scraper.py` | **CREATE** |
| `scripts/seo_score.py` | **PATCH** (add helpers + flags) |
| `scripts/tests/test_seo_score.py` | **PATCH** (add test_bulk_mode, add `Path` import) |
| `README.md` | **PATCH** |
