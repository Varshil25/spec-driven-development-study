"""Deterministic local inverted index; not a vector embedding index."""
import json
import re
from collections import Counter
from paths import WIKI, INDEX

def tokenize(text):
    return re.findall(r"[a-z0-9]{3,}", text.lower())

def build_index():
    docs = {}
    for p in sorted((WIKI / "articles").glob("*.md")) if (WIKI / "articles").exists() else []:
        content = p.read_text(encoding="utf-8")
        docs[p.stem] = {"path": str(p.relative_to(WIKI)), "terms": dict(Counter(tokenize(content)))}
    INDEX.mkdir(parents=True, exist_ok=True)
    (INDEX / "index.json").write_text(json.dumps(docs, indent=2) + "\n", encoding="utf-8")
    return {"indexed": len(docs)}
