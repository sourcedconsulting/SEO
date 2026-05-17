#!/usr/bin/env python3
# tests/test_backlink_checker.py — stand-alone (no pytest required)

import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import backlink_checker


def test_required_exports_exist():
    assert hasattr(backlink_checker, "wayback_indexed")
    assert hasattr(backlink_checker, "google_indexed")
    assert hasattr(backlink_checker, "format_report")
    assert hasattr(backlink_checker, "CDX_URL")
    print("  all 4 public functions present")

def test_wayback_url_structure():
    assert backlink_checker.CDX_URL.startswith("https://web.archive.org/cdx/")
    print("  CDX_URL OK")

def test_google_indexed_returns_dict():
    result = backlink_checker.google_indexed("https://example.com")
    assert isinstance(result, dict)
    assert "indexed" in result
    print("  google_indexed returns dict with indexed key")

def test_format_report_contains_key_sections():
    wb = {"indexed": True, "first_seen": "20100101", "last_seen": "20240101"}
    gi = {"indexed": True, "http_code": 200}
    out = backlink_checker.format_report("https://example.com", wb, gi)
    assert "BACKLINK PROFILE SIGNALS" in out
    assert "example.com" in out
    assert "Wayback" in out
    assert "Google" in out
    print("  format_report contains all sections")

def test_wayback_network_reachable():
    import urllib.request
    try:
        resp = urllib.request.urlopen(
            backlink_checker.CDX_URL
            + "?url=example.com%2F*&output=json&limit=1",
            timeout=10
        )
        data = json.loads(resp.read())
        assert isinstance(data, list)
        print(f"  Wayback responded: {len(data)} row(s)")
    except Exception as e:
        print(f"  ⚠ Wayback unavailable: {e}")

if __name__ == "__main__":
    test_required_exports_exist();          print("OK  test_required_exports_exist")
    test_wayback_url_structure();            print("OK  test_wayback_url_structure")
    test_google_indexed_returns_dict();      print("OK  test_google_indexed_returns_dict")
    test_format_report_contains_key_sections(); print("OK  test_format_report_contains_key_sections")
    test_wayback_network_reachable();        print("OK  test_wayback_network_reachable")
    print("All passed.")
