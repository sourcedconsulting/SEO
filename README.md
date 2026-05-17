# SEO — Python CLI Tools for On-Page & Local SEO

Python scripts for on-page SEO audits, local business verification, keyword research, and structured data validation. Built for quick, repeatable client audits.

---

## Install

```bash
uv pip install beautifulsoup4 lxml requests scikit-learn
```

Dependency-free tools: `clause_density.py`, `seo_score.py` run without installs.

---

## Scripts

### `seo_score.py` — On-Page SEO Scorecard
Extracts title, meta description, H1, H2s, image alt-text and scores each section 0–100. Flags low word-count pages and missing alt attributes.

```bash
python scripts/seo_score.py https://example.com
python scripts/seo_score.py /path/to/local/file.html --json score.json
```

---

### `clause_density.py` — Readability / Clause Density
Spot walls of text before they become UX or keyword-stuffing problems. Flags sentences with 10+ consecutive short clauses.

```bash
python scripts/clause_density.py https://example.com/blog/post
```

---

### `keyword_clusterer.py` — Keyword Topic Clusterer
TF-IDF + K-Means clustering. Group keywords into content silos and assign canonical target pages.

```bash
python scripts/keyword_clusterer.py data/sample_keywords.csv --clusters 5 --json clusters.json
```

Requires `scikit-learn`. Input CSV must have `keyword,volume` columns.

---

### `citation_checker.py` — AU Business Directory Auditor
Checks NAP (Name/Address/Phone) consistency across Yellow Pages, TrueLocal, HotFrog AU, StartLocal. Essential for GMB local SEO.

```bash
python scripts/citation_checker.py "CleanPro Plumbing" "Brisbane QLD"
python scripts/citation_checker.py "CleanPro Plumbing" "Brisbane QLD" --json citations.json
```

Requires `requests` and `beautifulsoup4`.

---

### `schema_checker.py` — JSON-LD / Structured Data Validator
Parses JSON-LD blocks and flags missing required fields for `LocalBusiness`, `Service`, `Organization`, `WebSite`, `FAQPage` and more.

```bash
python scripts/schema_checker.py https://example.com --check local-business service
python scripts/schema_checker.py data/sample_local_business.html --json blocks.json
```

Requires `beautifulsoup4`.

---

### `backlink_checker.py` — Domain Index / Backlink Signals
Quick Wayback Machine and Google index signal check. Not a full backlink scraper (for that use Ahrefs/Semrush APIs). Good for monitoring whether a client domain is being indexed at all.

```bash
python scripts/backlink_checker.py https://example.com
python scripts/backlink_checker.py https://example.com --json signals.json
```

---

## Data

- `data/sample_keywords.csv` — 20 tradie keywords with search volume (for `keyword_clusterer.py`)
- `data/sample_local_business.html` — mock tradie website with LocalBusiness + Service JSON-LD (for `schema_checker.py`)

---

## Tests

Each script ships with a self-contained test file in `scripts/tests/`. No `pytest` required — run directly:

```bash
python scripts/tests/test_keyword_clusterer.py
python scripts/tests/test_schema_checker.py
python scripts/tests/test_citation_checker.py
python scripts/tests/test_backlink_checker.py
python scripts/tests/test_seo_score.py
python scripts/tests/test_clause_density.py
```

---

## Typical Workflow (tradie audit)

```
1. python scripts/citation_checker.py "XYZ Tradies" "Brisbane QLD"
2. python scripts/schema_checker.py https://xyztradies.com.au --check local-business service
3. python scripts/seo_score.py https://xyztradies.com.au --json audit.json
4. python scripts/clause_density.py https://xyztradies.com.au/services
5. python scripts/backlink_checker.py https://xyztradies.com.au
```

---

## License — Apache 2.0

Built by [Jamie Munro / Sourced Consulting](https://sourcedconsulting.com.au) for client SEO audits and internal lead-generation workflows in Brisbane, Australia.
