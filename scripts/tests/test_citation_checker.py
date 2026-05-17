\
# tests/test_citation_checker.py
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from citation_checker import looks_like_match, format_report, AUS_DIRECTORIES

def test_normalise():
    assert looks_like_match("CleanPro Plumbing Brisbane", "Clean Pro Plumbing", "Brisbane")
    assert not looks_like_match("Dogs for adoption", "Clean Pro Plumbing", "Brisbane")

def test_has_directories():
    assert len(AUS_DIRECTORIES) >= 3
    names = [d["name"] for d in AUS_DIRECTORIES]
    assert "Yellow Pages" in names

def test_format_report_structure():
    results = [
        {"name": "YP", "found": True,  "match": True,  "error": None, "url": None},
        {"name": "TL", "found": True,  "match": False, "error": None, "url": None},
    ]
    out = format_report("Test Co", "Brisbane QLD", results)
    assert "CITATION AUDIT" in out
    assert "YP" in out
    assert "TL" in out
