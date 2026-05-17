#!/usr/bin/env python3
# tests/test_keyword_clusterer.py — stand-alone (no pytest required)

import csv, io, os, tempfile, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from keyword_clusterer import load_keywords, cluster_keywords, format_report

SAMPLE = "keyword,volume\nplumber brisbane,1100\nplumber sunshine coast,600\nbrisbane plumber,900\nbrisbane electrician,500\nelectrician gold coast,700\ngold coast sparky,300\nbrisbane electrician 24 hour,200\nsolar panel cleaning brisbane,400\n"


def test_load_keywords():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE)
        fname = f.name
    try:
        items = load_keywords(fname)
        assert len(items) >= 7, f"Expected >=7 items, got {len(items)}"
    finally:
        os.unlink(fname)


def test_cluster_count():
    items = []
    for row in csv.DictReader(io.StringIO(SAMPLE)):
        kw = row["keyword"]
        vol = int(row["volume"])
        if kw:
            items.append({"keyword": kw, "volume": vol})
    clusters = cluster_keywords(items, 3)
    assert len(clusters) <= 3, f"Expected <=3 clusters, got {len(clusters)}"
    total_kw = sum(len(c) for c in clusters.values())
    assert total_kw == len(items), "Items dropped during clustering"


def test_format_report_structure():
    clusters = {
        0: [{"keyword": "plumber brisbane", "volume": 1000}],
        1: [{"keyword": "brisbane electrician", "volume": 500}],
    }
    out = format_report(clusters)
    assert "KEYWORD CLUSTER REPORT" in out
    assert "Total keywords" in out


def test_zero_volume_propagates():
    items = [{"keyword": "jurassic park soundtrack", "volume": 0}]
    clusters = cluster_keywords(items, 1)
    assert sum(i["volume"] for c in clusters.values() for i in c) == 0


if __name__ == "__main__":
    test_load_keywords();   print("OK  test_load_keywords")
    test_cluster_count();   print("OK  test_cluster_count")
    test_format_report_structure(); print("OK  test_format_report_structure")
    test_zero_volume_propagates();  print("OK  test_zero_volume_propagates")
    print("All passed.")
