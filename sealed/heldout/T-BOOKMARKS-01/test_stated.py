"""T-BOOKMARKS-01 tier A (stated): behaviour written explicitly in the task description."""

import csv
import io
import json

import pytest


def rows(result):
    return result.stdout.splitlines()


def test_s1_add_prints_increasing_ids_from_1(bm):
    assert bm.add("https://a.example").stdout.strip() == "1"
    assert bm.add("https://b.example").stdout.strip() == "2"
    assert bm.add("http://c.example").stdout.strip() == "3"


@pytest.mark.parametrize("url", ["ftp://example.com", "javascript:alert(1)", "example.com",
                                 "mailto:a@b.co"])
def test_s2_non_http_urls_rejected(bm, url):
    r = bm.add(url)
    assert r.returncode == 2, r
    assert r.stderr.strip()
    assert rows(bm("list")) == []


def test_s3_list_format(bm):
    bm.add("https://docs.python.org", "Python docs", "python,docs")
    bm.add("https://example.com")
    r = bm("list")
    assert r.returncode == 0, r
    assert rows(r) == ["1\thttps://docs.python.org\tPython docs\tdocs,python",
                       "2\thttps://example.com\t\t"]


def test_s4_list_filtered_by_tag(bm):
    bm.add("https://a.example", "A", "x,y")
    bm.add("https://b.example", "B", "y")
    bm.add("https://c.example", "C", "z")
    assert rows(bm("list", "--tag", "y")) == ["1\thttps://a.example\tA\tx,y",
                                             "2\thttps://b.example\tB\ty"]
    assert rows(bm("list", "--tag", "nope")) == []


def test_s5_search_title_and_url_case_insensitive_in_id_order(bm):
    bm.add("https://zeta.example/python", "Misc")
    bm.add("https://a.example", "Learning PYTHON")
    bm.add("https://b.example", "Other")
    r = bm("search", "Python")
    assert r.returncode == 0, r
    assert [line.split("\t")[0] for line in rows(r)] == ["1", "2"]


def test_s5_search_does_not_match_tags_only(bm):
    bm.add("https://a.example", "Plain", "python")
    assert rows(bm("search", "python")) == []


def test_s6_delete_removes_bookmark(bm):
    bm.add("https://a.example")
    bm.add("https://b.example")
    r = bm("delete", "1")
    assert r.returncode == 0, r
    assert rows(bm("list")) == ["2\thttps://b.example\t\t"]


def test_s7_delete_unknown_id_exits_3(bm):
    bm.add("https://a.example")
    r = bm("delete", "42")
    assert r.returncode == 3, r
    assert r.stderr.strip()


def test_s8_export_csv(bm):
    bm.add("https://a.example", "Alpha, the first", "b,a")
    bm.add("https://b.example")
    r = bm("export", "--format", "csv")
    assert r.returncode == 0, r
    parsed = list(csv.reader(io.StringIO(r.stdout)))
    assert parsed[0] == ["id", "url", "title", "tags"]
    assert parsed[1] == ["1", "https://a.example", "Alpha, the first", "a,b"]
    assert parsed[2] == ["2", "https://b.example", "", ""]


def test_s9_export_json(bm):
    bm.add("https://a.example", "Alpha", "b,a")
    bm.add("https://b.example")
    r = bm("export", "--format", "json")
    assert r.returncode == 0, r
    data = json.loads(r.stdout)
    assert [d["id"] for d in data] == [1, 2]
    assert data[0]["url"] == "https://a.example" and data[0]["title"] == "Alpha"
    assert sorted(data[0]["tags"]) == ["a", "b"]
    assert data[1]["title"] == "" and data[1]["tags"] == []
    assert set(data[0]) == {"id", "url", "title", "tags"}


def test_s10_default_database_in_cwd_persists(run, workdir):
    assert run("add", "https://a.example").returncode == 0
    assert (workdir / "bookmarks.db").exists()
    assert run("list").stdout.splitlines() == ["1\thttps://a.example\t\t"]


def test_s11_task_example_sequence(bm):
    assert bm.add("https://docs.python.org", "Python docs", "python,docs").stdout.strip() == "1"
    assert bm.add("https://example.com").stdout.strip() == "2"
    assert rows(bm("search", "PYTHON")) == ["1\thttps://docs.python.org\tPython docs\tdocs,python"]
    assert bm.add("ftp://example.com").returncode == 2
