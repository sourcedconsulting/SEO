\
#!/usr/bin/env python3
"""
keyword_clusterer.py — Group keywords into topical clusters.

Usage:
    python scripts/keyword_clusterer.py keywords.csv
    python scripts/keyword_clusterer.py keywords.csv --clusters 8 --json out.json

CSV format: keyword,volume (optional)
Output: cluster summary with centroid keywords + total volume.

Installs: pip install scikit-learn
"""

import argparse
import csv
import sys
from pathlib import Path
from collections import defaultdict

try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    from sklearn.cluster import KMeans                      # type: ignore
    HAS_SK = True
except ImportError:
    HAS_SK = False


def load_keywords(path: str) -> list[dict]:
    items = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kw = row.get("keyword", row.get("Keyword", "")).strip()
            vol_raw = row.get("volume", row.get("Volume", "0")).strip().replace(",", "")
            try:
                vol = int(vol_raw)
            except ValueError:
                vol = 0
            if kw:
                items.append({"keyword": kw, "volume": vol})
    return items


def cluster_keywords(items: list[dict], n_clusters: int) -> dict[int, list[dict]]:
    if not HAS_SK:
        print("ERROR: scikit-learn not installed. Run: uv pip install scikit-learn")
        sys.exit(1)
    if len(items) < n_clusters:
        n_clusters = max(1, len(items) // 2)
    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w\s&]+\b",
                                 stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([i["keyword"] for i in items])
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(matrix)
    clusters: dict[int, list[dict]] = defaultdict(list)
    for item, label in zip(items, labels):
        clusters[int(label)].append(item)
    return dict(sorted(clusters.items()))


def sorted_cluster_name(cluster_items: list[dict], vectorizer, km) -> str:
    if not HAS_SK or not cluster_items:
        return "cluster"
    idx = vectorizer.vocabulary_
    # pick the centroid's nearest real keyword
    cluster_idx = [i for i, kw in enumerate(
        [x["keyword"] for x in cluster_items]
    ) if kw in idx]
    return cluster_items[0]["keyword"][:60]


def format_report(clusters: dict[int, list[dict]]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("KEYWORD CLUSTER REPORT")
    lines.append("=" * 60)
    total = sum(sum(i["volume"] for i in c) for c in clusters.values())
    for cid, c_items in clusters.items():
        vol = sum(i["volume"] for i in c_items)
        centroid = c_items[0]["keyword"]
        lines.append(f"\nCluster {cid + 1} — centroid: \"{centroid}\"")
        lines.append(f"  Keywords: {len(c_items)}  |  Total volume: {vol:,}")
        for item in sorted(c_items, key=lambda x: -x["volume"])[:10]:
            lines.append(f"    {item['keyword']:<60s}  vol={item['volume']:,}")
        if len(c_items) > 10:
            lines.append(f"    ... +{len(c_items) - 10} more")
    lines.append(f"\n{'=' * 60}")
    lines.append(f"Total clusters : {len(clusters)}")
    lines.append(f"Total keywords : {sum(len(c) for c in clusters.values())}")
    lines.append(f"Total volume   : {total:,}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Cluster keywords into topical groups.")
    ap.add_argument("csv_file", help="CSV: keyword,volume columns")
    ap.add_argument("--clusters", type=int, default=5, help="Target cluster count")
    ap.add_argument("--json", help="Save JSON output to path")
    args = ap.parse_args()
    items = load_keywords(args.csv_file)
    if not items:
        print("No keywords found.")
        sys.exit(1)
    clusters = cluster_keywords(items, args.clusters)
    print(format_report(clusters))
    if args.json:
        out = {
            "total_keywords": len(items),
            "total_volume": sum(i["volume"] for i in items),
            "clusters": [
                {
                    "id": k + 1,
                    "centroid": v[0]["keyword"],
                    "total_volume": sum(i["volume"] for i in v),
                    "keywords": sorted(v, key=lambda x: -x["volume"]),
                }
                for k, v in clusters.items()
            ]
        }
        Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nJSON saved → {args.json}")


if __name__ == "__main__":
    main()
