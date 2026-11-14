"""index.py: TF-IDF vector index over wiki/ (ai_specs/batch-process.md, step 4); query() for query.py.

Usage: python3 scripts/index.py         build state/index.pkl if any wiki page changed
"""

import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

INDEX = common.STATE / "index.pkl"


def pages():
    return sorted(p for p in common.WIKI.rglob("*.md"))


def chunks(path, size=180):
    """Split a page into paragraph-aligned chunks of about `size` words."""
    _, body = common.read_front_matter(path.read_text(encoding="utf-8"))
    out, buf = [], []
    for para in body.split("\n\n"):
        buf.append(para)
        if sum(len(b.split()) for b in buf) >= size:
            out.append("\n\n".join(buf))
            buf = []
    if buf:
        out.append("\n\n".join(buf))
    return out


def build(force=False):
    from sklearn.feature_extraction.text import TfidfVectorizer
    files = pages()
    digest = common.sha256_text("".join(p.read_text(encoding="utf-8") for p in files))
    if INDEX.exists() and not force:
        with open(INDEX, "rb") as handle:
            if pickle.load(handle)["digest"] == digest:
                return False, len(files)
    docs, refs = [], []
    for path in files:
        for i, chunk in enumerate(chunks(path)):
            docs.append(chunk)
            refs.append((str(path.relative_to(common.WIKI)), i))
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    matrix = vec.fit_transform(docs)
    common.STATE.mkdir(exist_ok=True)
    with open(INDEX, "wb") as handle:
        pickle.dump({"digest": digest, "vectorizer": vec, "matrix": matrix, "docs": docs, "refs": refs}, handle)
    return True, len(files)


def query(text, k=6):
    with open(INDEX, "rb") as handle:
        data = pickle.load(handle)
    scores = (data["matrix"] @ data["vectorizer"].transform([text]).T).toarray().ravel()
    best = scores.argsort()[::-1][:k]
    return [(data["refs"][i][0], float(scores[i]), data["docs"][i]) for i in best if scores[i] > 0]


def main():
    built, n = build("--force" in sys.argv)
    print("index: %s over %d pages" % ("rebuilt" if built else "unchanged", n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
