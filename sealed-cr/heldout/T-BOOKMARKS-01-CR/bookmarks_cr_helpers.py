"""Helpers shared by the T-BOOKMARKS-01-CR suites."""

import json
from html.parser import HTMLParser


class Page(HTMLParser):
    """Collects every element and every link (with its text) in a page."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.links = []
        self.smalls = []
        self._link = None
        self._small = None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "a":
            self._link = {"attrs": dict(attrs), "text": ""}
            self.links.append(self._link)
        elif tag == "small":
            self._small = []

    def handle_endtag(self, tag):
        if tag == "a":
            self._link = None
        elif tag == "small" and self._small is not None:
            self.smalls.append("".join(self._small))
            self._small = None

    def handle_data(self, data):
        if self._link is not None:
            self._link["text"] += data
        if self._small is not None:
            self._small.append(data)


def write_json(path, entries):
    path.write_text(json.dumps(entries))


def rows(result):
    return [line.split("\t") for line in result.stdout.splitlines()]
