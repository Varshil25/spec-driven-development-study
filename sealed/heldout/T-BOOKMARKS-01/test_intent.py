"""T-BOOKMARKS-01 tier B (intent): points the task description leaves open.
Answers: operator/answer-sheets/T-BOOKMARKS-01.md."""


def rows(result):
    return result.stdout.splitlines()


def test_i1_duplicate_url_returns_existing_id(bm):
    assert bm.add("https://a.example", "First").stdout.strip() == "1"
    r = bm.add("https://a.example", "Second", "t")
    assert r.returncode == 0, r
    assert r.stdout.strip() == "1"
    assert rows(bm("list")) == ["1\thttps://a.example\tFirst\t"]


def test_i2_tags_trimmed_lowercased_deduplicated(bm):
    bm.add("https://a.example", "A", " Python , CLI,python")
    assert rows(bm("list")) == ["1\thttps://a.example\tA\tcli,python"]
    assert rows(bm("list", "--tag", "PYTHON")) == ["1\thttps://a.example\tA\tcli,python"]


def test_i3_title_with_tab_or_newline_rejected(bm):
    r = bm.add("https://a.example", "bad\ttitle")
    assert r.returncode == 2, r
    r = bm.add("https://b.example", "bad\ntitle")
    assert r.returncode == 2, r
    assert rows(bm("list")) == []
