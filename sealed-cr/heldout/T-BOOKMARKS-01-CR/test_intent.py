"""T-BOOKMARKS-01-CR tier B (intent): answers in operator/answer-sheets/T-BOOKMARKS-01-CR.md."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bookmarks_cr_helpers import Page, rows, write_json  # noqa: E402


def test_i1_duplicates_are_skipped_and_not_counted(bm, workdir):
    bm("add", "https://example.com", "--title", "Old")
    write_json(workdir / "in.json", [
        {"url": "https://example.com", "title": "New", "tags": ["x"]},
        {"url": "https://a.test", "title": "A", "tags": []},
        {"url": "https://a.test", "title": "A again", "tags": []},
    ])
    r = bm("import", "in.json", "--format", "json")
    assert r.stdout == "imported 1\n", r
    assert rows(bm("list")) == [["1", "https://example.com", "Old", ""], ["2", "https://a.test", "A", ""]]


def test_i2_invalid_entry_is_skipped_with_a_warning_and_status_2(bm, workdir):
    write_json(workdir / "in.json", [
        {"url": "https://a.test", "title": "A", "tags": []},
        {"url": "ftp://b.test", "title": "B", "tags": []},
        {"url": "https://c.test", "title": "C", "tags": []},
    ])
    r = bm("import", "in.json", "--format", "json")
    assert r.returncode == 2, r
    assert r.stderr.strip(), r
    assert r.stdout == "imported 2\n", r
    assert [row[1] for row in rows(bm("list"))] == ["https://a.test", "https://c.test"]


def test_i3_empty_title_uses_the_url_as_link_text(bm):
    bm("add", "https://untitled.test")
    page = Page(bm("export", "--format", "html").stdout)
    assert page.links[0]["text"] == "https://untitled.test"
