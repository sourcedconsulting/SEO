# tests — run with: python -m pytest scripts/tests/

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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

def test_perfect_score():
    ok_html = '<html lang="en"><head><title>SEO Title Here</title><meta name="description" content="desc"></head><body><h1>Heading</h1><p>text</p></body></html>'
    r = analyse(ok_html, "http://test.com")
    assert r["score"] >= 80, f"Expected >= 80 got {r['score']}"

def test_missing_title():
    bad = '<html lang="en"><body><h1>H1</h1><p>text</p></body></html>'
    r = analyse(bad, "http://test.com")
    assert r["score"] < 100

def test_alt_coverage():
    ok_html = '<html lang="en"><head><title>SEO Title</title><meta name="description" content="d"><body><h1>H1</h1><img src="a.jpg" alt="ok"><img src="b.jpg" alt="ok"></body></html>'
    r = analyse(ok_html, "http://test.com")
    assert r["alt_coverage_pct"] == 100.0
