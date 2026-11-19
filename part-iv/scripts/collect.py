"""collect.py: fetch or import every trusted source, extract text, record hashes.

Usage: python3 scripts/collect.py [--from-dir DIR] [--only S01,S02]
Exit status: 0 all collected, 1 some failed, 2 nothing could run.
See ai_specs/collection-techniques.md.
"""

import argparse
import html.parser
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

MIN_CHARS = 500
SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg", "button"}
BLOCK_TAGS = {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "pre", "blockquote"}


class _Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)


def html_to_text(raw_html):
    """Main text of a page: scripts, navigation, headers and footers dropped; whitespace tidied."""
    parser = _Text()
    parser.feed(raw_html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*(\n\s*)+", "\n\n", text)
    return parser.title.strip(), text.strip()


def fetch_url(url):
    """Return the URL to fetch and how to extract it."""
    m = re.match(r"https?://arxiv\.org/abs/([\w.]+)", url)
    if m:
        return "https://arxiv.org/pdf/%s" % m.group(1), "pdf"
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/blob/(.+)", url)
    if m:
        return "https://raw.githubusercontent.com/%s/%s/%s" % m.groups(), "text"
    return url, "html"


def extract(data, kind):
    if kind == "pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
            handle.write(data)
            handle.flush()
            out = subprocess.run(["pdftotext", "-layout", handle.name, "-"], capture_output=True, check=True)
        return "", out.stdout.decode("utf-8", "replace")
    text = data.decode("utf-8", "replace")
    if kind == "html":
        return html_to_text(text)
    first = next((l.lstrip("# ").strip() for l in text.splitlines() if l.startswith("#")), "")
    return first, text


def get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": "sdkdp-collect/1.0 (research use)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def collect_one(row, from_dir=None, fetcher=get):
    """Return (record, text) for one source; raises on failure."""
    url = row["url"]
    if from_dir:
        for ext, kind in ((".pdf", "pdf"), (".md", "text"), (".txt", "text"), (".html", "html")):
            path = Path(from_dir) / (row["id"] + ext)
            if path.exists():
                title, text = extract(path.read_bytes(), kind)
                return {"fetched_via": "import", "import_file": path.name}, title, text
    target, kind = fetch_url(url)
    try:
        data = fetcher(target)
    except Exception:
        data = fetcher(target)  # one retry (collection-techniques.md, failure handling)
    title, text = extract(data, kind)
    return {"fetched_via": "http", "fetched_from": target}, title, text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-dir", help="import <id>.pdf/.md/.txt/.html files from this folder")
    ap.add_argument("--only", help="comma-separated source IDs")
    ap.add_argument("--corpus", default=str(common.CORPUS))
    args = ap.parse_args(argv)

    rows = common.sources(args.corpus)
    if args.only:
        wanted = set(args.only.split(","))
        rows = [r for r in rows if r["id"] in wanted]
    manifest = common.load_manifest()
    common.RAW.mkdir(exist_ok=True)
    failed = changed = 0
    for row in rows:
        sid = row["id"]
        old = manifest["sources"].get(sid, {})
        try:
            record, title, text = collect_one(row, args.from_dir)
            if len(text) < MIN_CHARS:
                raise ValueError("extracted text under %d characters" % MIN_CHARS)
        except Exception as exc:  # recorded, run continues
            manifest["sources"][sid] = dict(old, status="failed", error=str(exc)[:300], tried_at=common.now())
            print("%s FAILED: %s" % (sid, exc))
            failed += 1
            continue
        digest = common.sha256_text(text)
        (common.RAW / ("%s.txt" % sid)).write_text(text, encoding="utf-8")
        is_new = digest != old.get("sha256")
        if is_new and old.get("sha256") and row["url"].startswith("https://arxiv.org"):
            print("%s WARNING: paper text changed (new arXiv version?)" % sid)
        changed += is_new
        manifest["sources"][sid] = dict(record, id=sid, url=row["url"], status="ok", sha256=digest,
                                        bytes=len(text.encode()), title_seen=title[:200],
                                        fetched_at=common.now() if is_new else old.get("fetched_at", common.now()))
        print("%s %s (%d chars, %s)" % (sid, "changed" if is_new else "unchanged", len(text), record["fetched_via"]))
    common.save_manifest(manifest)
    print("collect: %d sources, %d changed, %d failed" % (len(rows), changed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
