# tests — run with: python -m pytest scripts/tests/

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clause_density import extract_paragraphs, count_clauses, split_sentences

SAMPLE_HTML = """
<html><body>
<p>The quick brown fox jumps over the lazy dog; it was a bright cold day.</p>
<p>Short.</p>
<div>This sentence is exactly one hundred and fifty words long which is significantly more than the default maximum sentence length threshold and therefore should be flagged as an issue.</div>
</body></html>"""


def test_extract_paragraphs():
    paras = extract_paragraphs(SAMPLE_HTML)
    assert len(paras) == 2, f"Expected 2 paragraphs, got {len(paras)}"


def test_clause_count():
    assert count_clauses("A and B, also C") >= 2
    assert count_clauses("Simple sentence.") == 0


def test_split_sentences():
    sents = split_sentences("First sentence. Second one! Third?")
    assert len(sents) == 3
