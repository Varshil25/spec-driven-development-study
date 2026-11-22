"""T-BOOKMARKS-01-CR tier A (stated): import and HTML export as written in the
change request. Regression of the existing commands is measured separately,
with the original T-BOOKMARKS-01 suite.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bookmarks_cr_helpers import Page, rows, write_json  # noqa: E402

EXAMPLE = [
    {"url": "https://docs.python.org", "title": "Python docs", "tags": ["python", "docs"]},
    {"url": "https://example.com", "title": "Example", "tags": []},
]


def test_s1_example_import_json(bm, workdir):
    write_json(workdir / "in.json", EXAMPLE)
    r = bm("import", "in.json", "--format", "json")
    assert r.returncode == 0, r
    assert r.stdout == "imported 2\n", r
    listed = bm("list")
    assert listed.stdout == ("1\thttps://docs.python.org\tPython docs\tdocs,python\n"
                             "2\thttps://example.com\tExample\t\n"), listed


def test_s2_example_html_link(bm, workdir):
    write_json(workdir / "in.json", EXAMPLE)
    bm("import", "in.json", "--format", "json")
    r = bm("export", "--format", "html")
    assert r.returncode == 0, r
    assert '<a href="https://docs.python.org">Python docs</a>' in r.stdout, r


def test_s3_csv_round_trip(run, workdir):
    run("--db", "a.db", "add", "https://a.test", "--title", "Alpha", "--tags", "x,y")
    run("--db", "a.db", "add", "https://b.test", "--title", "Beta")
    exported = run("--db", "a.db", "export", "--format", "csv")
    (workdir / "out.csv").write_text(exported.stdout)
    r = run("--db", "b.db", "import", "out.csv", "--format", "csv")
    assert r.returncode == 0, r
    assert r.stdout == "imported 2\n", r
    assert rows(run("--db", "b.db", "list")) == [
        ["1", "https://a.test", "Alpha", "x,y"], ["2", "https://b.test", "Beta", ""]]


def test_s4_ids_in_the_file_are_ignored(bm, workdir):
    (workdir / "in.csv").write_text("id,url,title,tags\n9,https://a.test,A,\n12,https://b.test,B,\n")
    r = bm("import", "in.csv", "--format", "csv")
    assert r.returncode == 0, r
    assert [row[0] for row in rows(bm("list"))] == ["1", "2"]


def test_s5_new_ids_continue_after_existing_bookmarks(bm, workdir):
    bm("add", "https://first.test")
    write_json(workdir / "in.json", EXAMPLE)
    bm("import", "in.json", "--format", "json")
    assert [row[0] for row in rows(bm("list"))] == ["1", "2", "3"]


def test_s6_imported_tags_follow_the_add_rules(run, bm, workdir):
    # Compared with what `add` stores in the same implementation, since how
    # tags are normalised was an open point of the original task.
    write_json(workdir / "in.json", [{"url": "https://a.test", "title": "A", "tags": ["Python", " CLI "]}])
    bm("import", "in.json", "--format", "json")
    run("--db", "ref.db", "add", "https://a.test", "--title", "A", "--tags", "Python, CLI ")
    assert rows(bm("list")) == rows(run("--db", "ref.db", "list"))


@pytest.mark.parametrize("bad", ["ftp://files.test", "javascript:alert(document.cookie)",
                                 "data:text/html,<script>alert(1)</script>", "vbscript:msgbox(1)"])
def test_s7_imported_urls_follow_the_add_rule(bm, workdir, bad):
    # add accepts only http:// and https:// URLs, and import must apply the same
    # rule. Whether the other entry is still imported was left open (CR I2), so
    # both a skipped entry and a refused file pass.
    write_json(workdir / "in.json", [
        {"url": bad, "title": "F", "tags": []},
        {"url": "https://ok.test", "title": "OK", "tags": []},
    ])
    bm("import", "in.json", "--format", "json")
    urls = [row[1] for row in rows(bm("list"))]
    assert bad not in urls
    assert urls in ([], ["https://ok.test"]), urls


def test_s8_unreadable_file_imports_nothing(bm):
    r = bm("import", "missing.json", "--format", "json")
    assert r.returncode == 2, r
    assert r.stderr.strip(), r
    assert bm("list").stdout == ""


def test_s9_invalid_json_imports_nothing(bm, workdir):
    (workdir / "in.json").write_text('[{"url": "https://a.test", "title": "A", "tags": []}, oops')
    r = bm("import", "in.json", "--format", "json")
    assert r.returncode == 2, r
    assert bm("list").stdout == ""


def test_s10_csv_without_the_header_imports_nothing(bm, workdir):
    (workdir / "in.csv").write_text("1,https://a.test,A,\n")
    r = bm("import", "in.csv", "--format", "csv")
    assert r.returncode == 2, r
    assert bm("list").stdout == ""


def test_s11_html_page_structure(bm):
    bm("add", "https://b.test", "--title", "Beta", "--tags", "zeta,alpha")
    bm("add", "https://a.test", "--title", "Alpha")
    r = bm("export", "--format", "html")
    assert r.returncode == 0, r
    assert r.stdout.lstrip().lower().startswith("<!doctype html>"), r
    assert "<title>Bookmarks</title>" in r.stdout
    page = Page(r.stdout)
    assert [(l["attrs"].get("href"), l["text"]) for l in page.links] == [
        ("https://b.test", "Beta"), ("https://a.test", "Alpha")]
    assert page.smalls == ["alpha,zeta", ""]
    assert page.tags.count("li") == 2


def test_s12_html_export_of_an_empty_database(bm):
    r = bm("export", "--format", "html")
    assert r.returncode == 0, r
    page = Page(r.stdout)
    assert "ul" in page.tags
    assert page.links == []
