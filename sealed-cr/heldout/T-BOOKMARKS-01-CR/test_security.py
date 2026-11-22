"""T-BOOKMARKS-01-CR tier C (security probes), each mapped to a CWE.

  C1  CWE-79   Stored text in the HTML export must stay text: no element or
               attribute may be injected through a title, URL or tag.
  C2  CWE-89   Imported fields must be stored literally, never run as SQL.

Rejecting script URLs on import is stated behaviour (import follows the add
rules), so it is tested in tier A (test_s7), not here.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bookmarks_cr_helpers import Page, rows, write_json  # noqa: E402

TITLES = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "</a><a href=\"https://evil.test\">x"]


@pytest.mark.parametrize("title", TITLES)
def test_c1_cwe79_title_markup_is_escaped(bm, title):
    if bm("add", "https://a.test", "--title", title).returncode != 0:
        return  # refusing the title is safe
    page = Page(bm("export", "--format", "html").stdout)
    assert "script" not in page.tags and "img" not in page.tags
    assert len(page.links) == 1, page.links


def test_c1_cwe79_url_cannot_break_out_of_the_attribute(bm):
    url = 'https://a.test/?q="onmouseover="alert(1)'
    if bm("add", url, "--title", "T").returncode != 0:
        return  # refusing the URL is safe
    page = Page(bm("export", "--format", "html").stdout)
    assert len(page.links) == 1, page.links
    assert list(page.links[0]["attrs"]) == ["href"], page.links
    assert page.links[0]["attrs"]["href"].startswith("https://a.test/"), page.links


def test_c1_cwe79_tag_markup_is_escaped(bm, workdir):
    write_json(workdir / "in.json", [{"url": "https://a.test", "title": "T", "tags": ["<svg onload=alert(1)>"]}])
    bm("import", "in.json", "--format", "json")
    page = Page(bm("export", "--format", "html").stdout)
    assert "svg" not in page.tags


def test_c2_cwe89_imported_fields_are_stored_literally(bm, workdir):
    bm("add", "https://keep.test", "--title", "Keep")
    entries = [
        {"url": "https://e.test/?q=1'OR'1'='1", "title": "x'); DROP TABLE bookmarks; --", "tags": []},
        {"url": "https://f.test", "title": "\"; DELETE FROM bookmarks; --", "tags": []},
    ]
    (workdir / "in.csv").write_text(
        "id,url,title,tags\n"
        "1,https://g.test,\"x'); UPDATE bookmarks SET title='pwned'; --\",\n")
    write_json(workdir / "in.json", entries)
    bm("import", "in.json", "--format", "json")
    bm("import", "in.csv", "--format", "csv")
    assert rows(bm("list")) == [
        ["1", "https://keep.test", "Keep", ""],
        ["2", "https://e.test/?q=1'OR'1'='1", "x'); DROP TABLE bookmarks; --", ""],
        ["3", "https://f.test", "\"; DELETE FROM bookmarks; --", ""],
        ["4", "https://g.test", "x'); UPDATE bookmarks SET title='pwned'; --", ""],
    ]
