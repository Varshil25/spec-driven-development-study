"""Tests for the SD-KDP pipeline that need no network and no LLM."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect  # noqa: E402
import common  # noqa: E402
import distill  # noqa: E402
import index  # noqa: E402
import synthesize  # noqa: E402
import voice_check  # noqa: E402

GOOD = """# METR productivity trial [S03]

**In one sentence:** A randomized trial found experienced developers took longer with AI tools [S03].

## What it is
A randomized controlled trial with 16 experienced open-source developers and 246 tasks [S03].

## What it shows
- **measured**: Allowing AI tools increased completion time by 19% in an RCT of 16 developers [S03].
- **measured**: Developers believed afterwards that AI had saved them 20% of the time [S03].

## What it claims (without measurement)
Nothing beyond what it shows.

## Method and limits
The authors note that experimental artefacts cannot be fully ruled out [S03].

## Bearing on the key questions
- **Q4:** It measures the gap between perceived and actual speed, for AI tools in general [S03].

## Quotes
> "AI tooling slowed developers down" [S03]
"""


@pytest.fixture
def kb(tmp_path, monkeypatch):
    """A throwaway knowledge base with the real spec files."""
    root = tmp_path / "kb"
    (root / "ai_specs").mkdir(parents=True)
    for spec in common.SPECS.glob("*.md"):
        (root / "ai_specs" / spec.name).write_text(spec.read_text())
    (root / "corpus").mkdir()
    (root / "corpus" / "sources.csv").write_text(common.CORPUS.read_text())
    for name, sub in [("ROOT", ""), ("SPECS", "ai_specs"), ("RAW", "raw"), ("STATE", "state"), ("WIKI", "wiki")]:
        monkeypatch.setattr(common, name, root / sub if sub else root)
    monkeypatch.setattr(common, "CORPUS", root / "corpus" / "sources.csv")
    monkeypatch.setattr(common, "MANIFEST", root / "state" / "manifest.json")
    monkeypatch.setattr(index, "INDEX", root / "state" / "index.pkl")
    return root


def test_good_article_passes_the_voice_check():
    assert voice_check.check(GOOD, "S03") == []


@pytest.mark.parametrize("change, expected", [
    (("increased completion time by 19% in an RCT of 16 developers [S03]", "increased completion time by 19% in an RCT of 16 developers"), "untagged sentence"),
    (("- **measured**: Developers believed", "- Developers believed"), "without an evidence class"),
    (("A randomized controlled trial", "A revolutionary randomized controlled trial"), "hype word: revolutionary"),
    (("## Quotes\n", ""), "missing section: Quotes"),
    (('"AI tooling slowed developers down"', '"' + "word " * 30 + '"'), "quote over 25 words"),
])
def test_voice_check_catches_drift(change, expected):
    bad = GOOD.replace(*change)
    assert any(expected in p for p in voice_check.check(bad, "S03"))


def test_hedging_is_limited():
    hedged = GOOD.replace("found experienced developers took longer", "may perhaps suggest developers could possibly arguably take longer")
    assert any("hedge density" in p for p in voice_check.check(hedged, "S03"))


def test_html_extraction_drops_navigation_and_scripts():
    title, text = collect.html_to_text("<html><head><title>T</title><script>x()</script></head><body>"
                                       "<nav>Home | About</nav><article><p>Real text.</p><p>More.</p></article>"
                                       "<footer>(c) site</footer></body></html>")
    assert title == "T" and "Real text." in text and "Home" not in text and "x()" not in text and "(c)" not in text


@pytest.mark.parametrize("url, target, kind", [
    ("https://arxiv.org/abs/2507.09089", "https://arxiv.org/pdf/2507.09089", "pdf"),
    ("https://github.com/github/spec-kit/blob/main/spec-driven.md",
     "https://raw.githubusercontent.com/github/spec-kit/main/spec-driven.md", "text"),
    ("https://example.org/a", "https://example.org/a", "html"),
])
def test_fetch_targets(url, target, kind):
    assert collect.fetch_url(url) == (target, kind)


def test_rejected_sources_are_never_collected(kb):
    assert {r["id"] for r in common.sources()} == {"S%02d" % i for i in range(1, 18)}
    assert all(not r["id"].startswith("X") for r in common.sources())


def test_collect_is_incremental(kb, tmp_path, capsys):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "S08.md").write_text("# SDD\n" + "Specs first. " * 100)
    assert collect.main(["--from-dir", str(inbox), "--only", "S08"]) == 0
    first = json.loads((kb / "state" / "manifest.json").read_text())["sources"]["S08"]
    assert first["fetched_via"] == "import" and first["title_seen"] == "SDD"
    assert collect.main(["--from-dir", str(inbox), "--only", "S08"]) == 0
    assert "1 sources, 0 changed" in capsys.readouterr().out
    (inbox / "S08.md").write_text("# SDD\n" + "Specs first. " * 100 + "One more line.")
    collect.main(["--from-dir", str(inbox), "--only", "S08"])
    assert "1 sources, 1 changed" in capsys.readouterr().out


def test_short_extractions_fail_and_are_recorded(kb, tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "S12.md").write_text("too short")
    assert collect.main(["--from-dir", str(inbox), "--only", "S12"]) == 1
    assert json.loads((kb / "state" / "manifest.json").read_text())["sources"]["S12"]["status"] == "failed"


def test_distill_runs_only_on_new_changed_or_respecified_sources(kb):
    row = next(r for r in common.sources() if r["id"] == "S03")
    manifest = {"sources": {"S03": {"status": "ok", "sha256": "abc"}}}
    digest = common.spec_hash()
    assert distill.needs_distill(row, manifest, digest) == (True, "new")
    path = kb / "wiki" / "sources" / "S03.md"
    path.parent.mkdir(parents=True)
    path.write_text(common.write_front_matter({"id": "S03", "source_sha256": "abc", "spec_sha256": digest}, GOOD))
    assert distill.needs_distill(row, manifest, digest) == (False, "unchanged")
    manifest["sources"]["S03"]["sha256"] = "def"
    assert distill.needs_distill(row, manifest, digest) == (True, "source changed")
    manifest["sources"]["S03"]["sha256"] = "abc"
    (kb / "ai_specs" / "distillation-techniques.md").write_text("changed")
    assert distill.needs_distill(row, manifest, common.spec_hash()) == (True, "spec changed")


def test_front_matter_round_trip():
    meta = {"id": "S03", "questions": ["Q4", "Q8"], "url": "https://x.org/a:b"}
    back, body = common.read_front_matter(common.write_front_matter(meta, "# Body"))
    assert back == meta and body.strip() == "# Body"


def test_key_questions_and_question_tags():
    qs = synthesize.key_questions()
    assert list(qs) == ["Q%d" % i for i in range(1, 9)]
    assert distill.questions_in(GOOD) == ["Q4"]


def test_faq_index_and_vector_query(kb):
    (kb / "wiki" / "sources").mkdir(parents=True)
    (kb / "wiki" / "sources" / "S03.md").write_text(common.write_front_matter(
        {"id": "S03", "title": "METR", "tier": "T1", "evidence_type": "RCT", "questions": ["Q4"]}, GOOD))
    (kb / "wiki" / "questions").mkdir()
    (kb / "wiki" / "questions" / "Q4.md").write_text(common.write_front_matter(
        {"question": "Q4"}, "# Q4\n\n**Short answer:** Slower in one RCT [S03].\n\n## What has been measured\n"))
    synthesize.write_faq_and_index(synthesize.articles(), synthesize.key_questions())
    assert "Slower in one RCT [S03]." in (kb / "wiki" / "faq.md").read_text()
    assert "[S03](sources/S03.md)" in (kb / "wiki" / "index.md").read_text()
    assert index.build()[0] is True and index.build()[0] is False
    assert index.query("completion time developers")[0][0] == "sources/S03.md"
