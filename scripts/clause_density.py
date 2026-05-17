#!/usr/bin/env python3
"""
clause_density.py — Sentence and clause density checker for on-page content.

Detects paragraphs where a sentence is too long or a sentence contains too many
clauses (separated by semicolons, colons, or coordinating conjunctions).

Usage:
    python scripts/clause_density.py /path/to/your_doc.html
    python scripts/clause_density.py /path/to/your_doc.html --max-sentence-len 120 --max-clauses 3

Installs: pip install beautifulsoup4
"""

import argparse
import re
from pathlib import Path
from typing import List, Dict

from bs4 import BeautifulSoup  # type: ignore

COORDINATING_CONJUNCTIONS = {
    "and", "but", "or", "nor", "for", "yet", "so",
    "also", "however", "therefore", "moreover", "furthermore",
    "nonetheless", "nevertheless",
}


def split_sentences(text: str) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s{2,}", text)
    return [s.strip() for s in sentences if s.strip()]


def count_clauses(sentence: str) -> int:
    lowered = sentence.lower()
    count = lowered.count(":") + lowered.count(";")
    for conj in COORDINATING_CONJUNCTIONS:
        count += len(re.findall(r",\s+" + re.escape(conj) + r"\s+", lowered))
    return count


def extract_paragraphs(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    paragraphs = []
    for tag in soup.find_all(["p", "div"]):
        text = tag.get_text(strip=True)
        if len(text) > 20:
            paragraphs.append({"text": text, "tag": tag.name})
    return paragraphs


def analyse(paragraphs: List[Dict],
            max_sentence_len: int = 140,
            max_clauses: int = 4) -> List[Dict]:
    issues = []
    for para in paragraphs:
        sentences = split_sentences(para["text"])
        for i, sentence in enumerate(sentences, 1):
            word_count = len(sentence.split())
            clause_count = count_clauses(sentence)
            problems = []
            if word_count > max_sentence_len:
                problems.append(f"{word_count} words (>{max_sentence_len})")
            if clause_count > max_clauses:
                problems.append(f"{clause_count} clauses (>{max_clauses})")
            if problems:
                issues.append({
                    "para_tag": para["tag"],
                    "sentence": i,
                    "preview": sentence[:120] + ("..." if len(sentence) > 120 else ""),
                    "word_count": word_count,
                    "clause_count": clause_count,
                    "problems": problems,
                })
    return issues


def print_report(issues: List[Dict]) -> None:
    total = len(issues)
    print()
    print("=" * 60)
    s_word = 's' if total != 1 else ''
    print(f'  Clause Density Report  ({total} issue{s_word} found)')
    print("=" * 60)
    print()
    if not issues:
        print('  No issues found -- content looks clean.')
    for issue in issues:
        print(f"  [sentence {issue['sentence']:3d}] [{issue['para_tag']}] {', '.join(issue['problems'])}")
        print(f"         {issue['preview']}")
    if not issues:
        print("  No issues found — content looks clean.")


def main():
    parser = argparse.ArgumentParser(description="Sentence & clause density checker")
    parser.add_argument("html_file", help="HTML file to analyse")
    parser.add_argument("--max-sentence-len", type=int, default=140,
                        help="Max words per sentence (default 140)")
    parser.add_argument("--max-clauses", type=int, default=4,
                        help="Max clauses per sentence (default 4)")
    args = parser.parse_args()
    filepath = Path(args.html_file)
    if not filepath.exists():
        print(f"File not found: {args.html_file}")
        raise SystemExit(1)
    html = filepath.read_text(encoding="utf-8", errors="replace")
    paragraphs = extract_paragraphs(html)
    issues = analyse(paragraphs, args.max_sentence_len, args.max_clauses)
    print_report(issues)


if __name__ == "__main__":
    main()
