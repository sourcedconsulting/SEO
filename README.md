# SEO — Python CLI Tools for On-Page & Local SEO

Python scripts for on-page SEO audits, local business verification, keyword research, and structured data validation. Built by **[Sourced Consulting](https://sourcedconsulting.com.au)** for quick, repeatable tradie SEO audits across Brisbane and greater Queensland.

---

## Install

```bash
uv pip install beautifulsoup4 lxml requests scikit-learn
```

Dependency-free tools: `clause_density.py`, `seo_score.py` (single page) run without installs.

---

## Scripts

### `seo_score.py` — On-Page SEO Scorecard

Extracts title, meta description, H1, H2s, image alt-text and scores each section 0–100.

**Single page:**
```bash
python scripts/seo_score.py https://example.com
python scripts/seo_score.py /path/to/local/file.html
python scripts/seo_score.py https://example.com --json score.json
```

**Bulk audit (file of URLs, one per line):**
```bash
python scripts/seo_score.py --bulk urls.txt --json-out results.json
```

**Sitemap audit (auto-discover sitemap + audit every page):**
```bash
python scripts/seo_score.py --sitemap https://example.com --limit 25
python scripts/seo_score.py --sitemap https://example.com --json-out sitemap-audit.json
```

Combined: `--sitemap` + `--limit` + `--json-out`.

---

### `sitemap_scraper.py` — XML Sitemap URL Discovery

Extract every `<url><loc>` URL from a live sitemap, sitemap index, or local XML file.

```bash
# From a site root — auto-discovers /sitemap.xml, /sitemap_index.xml, robots.txt
python scripts/sitemap_scraper.py https://example.com

# From a direct sitemap URL
python scripts/sitemap_scraper.py https://example.com/sitemap-posts.xml

# From a local file
python scripts/sitemap_scraper.py /path/to/sitemap.xml --json urls.json

# Sample first 25 URLs
python scripts/sitemap_scraper.py https://example.com --limit 25
```

Outputs newline-delimited URL list to stdout (pipe into `seo_score.py --bulk -` for a one-liner).

---

### `clause_density.py` — Readability / Clause Density

Spot walls of text before they become UX or keyword-stuffing problems.

```bash
python scripts/clause_density.py https://example.com/blog/post
```

---

### `keyword_clusterer.py` — Keyword Topic Clusterer

TF-IDF + K-Means clustering. Group keywords into content silos.

```bash
python scripts/keyword_clusterer.py data/sample_keywords.csv --clusters 5 --json clusters.json
```

Requires `scikit-learn`.

---

### `citation_checker.py` — AU Business Directory Auditor

NAP (Name/Address/Phone) consistency check — Yellow Pages, TrueLocal, HotFrog, StartLocal.

```bash
python scripts/citation_checker.py "Sourced Consulting" "Brisbane QLD"
python scripts/citation_checker.py "Sourced Consulting" "Brisbane QLD" --json citations.json
```

Requires `requests` and `beautifulsoup4`.

---

### `schema_checker.py` — JSON-LD / Structured Data Validator

Parses JSON-LD blocks and validates required fields for `LocalBusiness`, `Service`, `Organization`, `WebSite`, `FAQPage`.

```bash
python scripts/schema_checker.py https://example.com --check local-business service
python scripts/schema_checker.py data/sample_local_business.html --json blocks.json
```

Requires `beautifulsoup4`.

---

### `wayback_checker.py` — Multi-Wayback Archival Check

Quick check across Internet Archive (CDX + `/availability`), Archive.today, and Google `site:`.

```bash
python scripts/wayback_checker.py https://example.com
python scripts/wayback_checker.py https://example.com --json signals.json
```

---

## Data

- `data/sample_keywords.csv` — 20 tradie keywords with search volume
- `data/sample_local_business.html` — mock tradie website with JSON-LD

---

## Tests

Each script ships with a self-contained test file in `scripts/tests/`. No `pytest` required — run directly:

```bash
python scripts/tests/test_sitemap_scraper.py
python scripts/tests/test_seo_score.py
python scripts/tests/test_clause_density.py
python scripts/tests/test_keyword_clusterer.py
python scripts/tests/test_schema_checker.py
python scripts/tests/test_citation_checker.py
python scripts/tests/test_wayback_checker.py
```

---

## Typical Workflow (tradie audit)

```
1. python scripts/citation_checker.py "XYZ Tradies" "Brisbane QLD"
2. python scripts/schema_checker.py https://xyztradies.com.au --check local-business service
3. python scripts/seo_score.py --sitemap https://xyztradies.com.au --json-out sitemap-audit.json --limit 25
4. python scripts/clause_density.py https://xyztradies.com.au/services
5. python scripts/wayback_checker.py https://xyztradies.com.au
```

---

## License — Apache 2.0

Built by [Jamie Munro / Sourced Consulting](https://sourcedconsulting.com.au) for client SEO audits and internal lead-generation workflows in Brisbane, Australia.
