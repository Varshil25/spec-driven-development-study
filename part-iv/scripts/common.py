"""Shared paths and helpers for the SD-KDP pipeline (see ai_specs/batch-process.md)."""

import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "ai_specs"
CORPUS = ROOT / "corpus" / "sources.csv"
RAW = ROOT / "raw"
STATE = ROOT / "state"
WIKI = ROOT / "wiki"
MANIFEST = STATE / "manifest.json"

# The spec files every distillation reads (distillation-techniques.md, "Inputs").
DISTILL_SPECS = ["oracle.md", "domain-knowledge.md", "output-format.md", "distillation-techniques.md"]


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def spec_text(names=DISTILL_SPECS, root=None):
    root = Path(root) if root else SPECS
    return "\n\n".join("<<< ai_specs/%s >>>\n%s" % (n, (root / n).read_text(encoding="utf-8")) for n in names)


def spec_hash(names=DISTILL_SPECS, root=None):
    return sha256_text(spec_text(names, root))


def sources(path=None, verdict="trusted"):
    with open(path or CORPUS, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [r for r in rows if verdict is None or r["verdict"] == verdict]


def load_manifest(path=None):
    path = Path(path or MANIFEST)
    return json.loads(path.read_text()) if path.exists() else {"sources": {}}


def save_manifest(data, path=None):
    path = Path(path or MANIFEST)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def read_front_matter(text):
    """Parse the simple `key: value` front matter written by this pipeline."""
    match = FRONT.match(text)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip() for v in value[1:-1].split(",") if v.strip()]
            meta[key.strip()] = value
    return meta, text[match.end():]


def write_front_matter(meta, body):
    lines = []
    for key, value in meta.items():
        if isinstance(value, (list, tuple)):
            value = "[%s]" % ", ".join(value)
        lines.append("%s: %s" % (key, value))
    return "---\n%s\n---\n\n%s" % ("\n".join(lines), body.lstrip())
