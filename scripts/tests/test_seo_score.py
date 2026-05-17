# tests — run with: python scripts/tests/test_seo_score.py

import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from seo_score import analyse

SAMPLE_HTML = """
<html lang="en">
<head><title>SEO Test Page Title</title>
<meta name="description" content="This is a test description."></head>
<body>
<h1>Main Heading</h1>
<p>This paragraph has a title that is 22 characters long which is slightly below the ideal range and still gives us something to test.</p>
<img src="pic1.jpg" alt="description here">
<img src="pic2.jpg" alt="">
</body></html>
"""

GOOD_HTML = '<html lang="en"><head><title>SEO Title Here</title><meta name="description" content="desc"></head><body><h1>Heading</h1><p>content content content content content</p></body></html>'
BAD_HTML  = '<html><body><h1>Only H1</h1></body></html>'


class TestPerPage:
    def test_perfect_score(self):
        r = analyse(GOOD_HTML, "http://test.com")
        assert r["score"] >= 80, f"Expected >= 80 got {r['score']}"

    def test_missing_title(self):
        r = analyse(BAD_HTML, "http://test.com")
        assert r["score"] < 100

    def test_alt_coverage(self):
        r = analyse(SAMPLE_HTML, "http://test.com")
        assert r["alt_coverage_pct"] < 100.0

    def test_key_present(self):
        r = analyse(SAMPLE_HTML, "http://test.com")
        assert r["title"] == "SEO Test Page Title"
        assert r["h1_hits"] == 1


class TestBulkMode:
    def test_bulk_results_count(self):
        pages = [GOOD_HTML, BAD_HTML]
        results = [analyse(p, f"http://test-{i}") for i, p in enumerate(pages)]
        assert results[0]["score"] >= 70
        assert results[1]["score"] < 70
        assert len(results) == 2

    def test_json_serialisable(self):
        result = analyse(GOOD_HTML, "http://test.com")
        blob = json.dumps(result)
        assert "\"url\"" in blob or '"url"' in blob

    def test_issue_severities(self):
        r = analyse(BAD_HTML, "http://test.com")
        for issue in r["issues"]:
            assert issue["severity"] in ("critical", "warning", "info")

    def test_local_file(self):
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w"
        ) as f:
            f.write(SAMPLE_HTML)
            tmppath = f.name
        r = analyse(Path(tmppath).read_text(), tmppath)
        assert isinstance(r["score"], int)
        os.unlink(tmppath)
