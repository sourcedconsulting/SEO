# tests — run with: python scripts/tests/test_sitemap_scraper.py
# Invokes the stub-level helper functions directly; no network required.

import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sitemap_scraper import (
    _parse_sitemap_xml,
    parse_sitemap,
    parse_sitemap_index,
    _strip_ns,
    format_report,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page-a</loc></url>
  <url><loc>https://example.com/page-b</loc></url>
  <url><loc>https://example.com/page-c</loc></url>
</urlset>"""

SAMPLE_INDEX = """<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap-posts.xml</loc></sitemap>
</sitemapindex>"""

SAMPLE_URLSET_WITH_LASTMOD = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/blog/hello</loc>
    <lastmod>2024-01-15</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>"""

EMPTY_SITEMAP = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>"""

INVALID_XML = "this is not xml at all"


# ── _strip_ns ────────────────────────────────────────────────────────────────

class TestStripNs:
    def test_simple(self): assert _strip_ns("urlset") == "urlset"
    def test_ns(self):    assert _strip_ns("{http://www.sitemaps.org/schemas/sitemap/0.9}urlset") == "urlset"
    def test_colon(self): assert _strip_ns("smp:loc") == "smp:loc"


# ── _parse_sitemap_xml ───────────────────────────────────────────────────────

class TestParseSitemapXml:
    def setup_method(self):
        # reset dedup OR call directly
        pass

    def test_urlset_returns_locs(self):
        urls, children = _parse_sitemap_xml(SAMPLE_URLSET)
        assert len(urls) == 3
        assert "https://example.com/page-a" in urls
        assert children == []

    def test_index_returns_children(self):
        urls, children = _parse_sitemap_xml(SAMPLE_INDEX)
        assert children == [
            "https://example.com/sitemap-pages.xml",
            "https://example.com/sitemap-posts.xml",
        ]
        assert urls == []

    def test_extra_elements_ignored(self):
        urls, children = _parse_sitemap_xml(SAMPLE_URLSET_WITH_LASTMOD)
        assert urls == ["https://example.com/blog/hello"]
        assert children == []

    def test_empty_sitemap(self):
        urls, children = _parse_sitemap_xml(EMPTY_SITEMAP)
        assert urls == []
        assert children == []

    def test_invalid_xml(self):
        urls, children = _parse_sitemap_xml(INVALID_XML)
        assert urls == []
        assert children == []

    def test_dedup_across_merge(self):
        """Merge two urlset chunks — dedup should be handled at collect level."""
        _, _ = _parse_sitemap_xml(SAMPLE_URLSET)
        u2, _ = _parse_sitemap_xml(SAMPLE_URLSET.replace("page-c", "page-a"))
        # Both parsers return parsed output; dedupe is caller's job
        combined = set(_parse_sitemap_xml(SAMPLE_URLSET)[0]) | set(u2)
        assert len(combined) == 3


# ── parse_sitemap / parse_sitemap_index (thin wrappers) ─────────────────────

class TestThinWrappers:
    def test_parse_sitemap(self):
        urls = parse_sitemap(SAMPLE_URLSET)
        assert set(urls) == {
            "https://example.com/page-a",
            "https://example.com/page-b",
            "https://example.com/page-c",
        }

    def test_parse_sitemap_index(self):
        children = parse_sitemap_index(SAMPLE_INDEX)
        assert sorted(children) == [
            "https://example.com/sitemap-pages.xml",
            "https://example.com/sitemap-posts.xml",
        ]

    def test_parse_sitemap_empty(self):
        assert parse_sitemap(EMPTY_SITEMAP) == []


# ── load_input — local file path ─────────────────────────────────────────────

class TestLoadInputFile:
    def test_local_xml_file(self):
        with tempfile.NamedTemporaryFile(
            suffix=".xml", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(SAMPLE_URLSET)
            tmppath = f.name
        try:
            from sitemap_scraper import load_input
            urls, mode, fetched, errors = load_input(tmppath)
            assert mode == "file"
            assert len(urls) == 3
            assert errors == []
        finally:
            os.unlink(tmppath)

    def test_missing_file(self):
        from sitemap_scraper import load_input
        import argparse
        try:
            load_input("/tmp/does_not_exist_abc123.xml")
        except SystemExit:
            pass  # load_input exits 1 on non-existent path

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(
            suffix=".xml", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(""); tmppath = f.name
        try:
            from sitemap_scraper import load_input
            urls, mode, fetched, errors = load_input(tmppath)
            assert urls == []
        finally:
            os.unlink(tmppath)


# ── format_report ────────────────────────────────────────────────────────────

class TestFormatReport:
    def test_basic(self):
        r = format_report(
            "https://example.com",
            ["https://example.com/a", "https://example.com/b"],
            "discovered",
            ["https://example.com/sitemap.xml"],
            [],
        )
        assert "Total URLs : 2" in r
        assert "Unique URLs: 2" in r

    def test_with_errors(self):
        r = format_report(
            "https://example.com",
            [],
            "discovered",
            ["https://example.com/sitemap.xml"],
            ["https://example.com/bad.xml"],
        )
        assert "bad.xml" in r

    def test_limit(self):
        r = format_report(
            "https://example.com",
            ["a"] * 5,
            "direct",
            ["https://example.com/sitemap.xml"],
            [],
            limit=5,
        )
        assert "limited to 5" in r
