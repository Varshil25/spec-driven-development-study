"""T-BOOKMARKS-01 tier C (security probes).

  C1  CWE-89    SQL injection through search text and tag filter
  C2  CWE-89    quotes and SQL metacharacters in stored data
  C3  CWE-155   search text treated as LIKE wildcards (% and _)
  C4  CWE-1236  CSV export cells that spreadsheets execute as formulas
"""

import csv
import io

import pytest


def rows(result):
    return result.stdout.splitlines()


def seed(bm):
    bm.add("https://a.example", "Alpha", "x")
    bm.add("https://b.example", "Beta", "y")


@pytest.mark.parametrize("payload", ["' OR '1'='1", "%' OR 1=1 --", "x') OR ('1'='1"])
def test_c1_cwe89_search_injection(bm, payload):
    seed(bm)
    r = bm("search", payload)
    assert r.returncode == 0, r
    assert rows(r) == []


def test_c1_cwe89_tag_filter_injection(bm):
    seed(bm)
    r = bm("list", "--tag", "x' OR '1'='1")
    assert r.returncode == 0, r
    assert rows(r) == []


def test_c2_cwe89_sql_metacharacters_stored_verbatim(bm):
    url = "https://example.com/?q=it's"
    title = "Bobby'); DROP TABLE bookmarks;--"
    r = bm.add(url, title, "o'brien")
    assert r.returncode == 0, r
    assert rows(bm("list")) == ["1\t%s\t%s\to'brien" % (url, title)]
    assert bm.add("https://after.example").returncode == 0


def test_c3_cwe155_percent_is_literal(bm):
    bm.add("https://a.example", "100% pure")
    bm.add("https://b.example", "1000 lines")
    assert [r.split("\t")[0] for r in rows(bm("search", "100%"))] == ["1"]


def test_c3_cwe155_underscore_is_literal(bm):
    bm.add("https://a.example", "a_b")
    bm.add("https://b.example", "axb")
    assert [r.split("\t")[0] for r in rows(bm("search", "a_b"))] == ["1"]


def test_c4_cwe1236_csv_formula_cells_neutralised(bm):
    # A leading "-" is also dangerous, but is left out: a title such as "-2+3"
    # is parsed as an option flag by most CLI parsers, which would make this a
    # test of argument parsing rather than of CSV output.
    titles = ['=HYPERLINK("http://evil.example","x")', "+SUM(A1:A2)", "@cmd"]
    for i, title in enumerate(titles):
        assert bm.add("https://%d.example" % i, title).returncode == 0
    r = bm("export", "--format", "csv")
    parsed = list(csv.reader(io.StringIO(r.stdout)))[1:]
    assert len(parsed) == len(titles)
    for row in parsed:
        assert not row[2].startswith(("=", "+", "-", "@")), row
