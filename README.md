# SEO

> Practical SEO tools and resources by [Sourced Consulting](https://sourcedconsulting.com.au).

This repo is the code companion to [sourcedconsulting/seo-academic-reference](https://github.com/sourcedconsulting/seo-academic-reference) — a 63-page academic guide to 50 actionable SEO tactics for Australian small businesses.

---

## What's Here

| Tool | Description |
|------|-------------|
| [`scripts/seo_score.py`](scripts/seo_score.py) | Single-page SEO scorecard — audits title, meta, headings, keywords, internal links |
| [`scripts/clause_density.py`](scripts/clause_density.py) | Sentence/clause density analyser — flags walls of text per paragraph |
| `resources/` | Quick-reference sheets (word counts, meta tag templates) |

---

## Requirements

Python 3.8+ — `pip install beautifulsoup4 lxml requests`

Optional: `pip install pytest` to run the test files.

---

## Quick Start

```bash
git clone https://github.com/sourcedconsulting/SEO.git
cd SEO
pip install beautifulsoup4 lxml requests
python scripts/seo_score.py https://example.com
```

---

## About the Author

**Sourced Consulting** — lead generation for Australian tradies via the Sourced & Booked system.

- [sourcedconsulting.com.au](https://sourcedconsulting.com.au)
- 0424 951 408
- [@sourcedconsult](https://twitter.com/sourcedconsult) on X/Twitter

---

## License

Apache 2.0 — see [LICENSE.md](LICENSE.md).
