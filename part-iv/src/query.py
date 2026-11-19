"""Simple ranked lookup over the extractive wiki."""
import json
import sys
from build_index import tokenize
from paths import INDEX

def query(question, limit=5):
    path = INDEX / "index.json"
    if not path.exists():
        return []
    docs = json.loads(path.read_text(encoding="utf-8"))
    words = set(tokenize(question))
    ranked = sorted(((sum(doc["terms"].get(w, 0) for w in words), sid, doc["path"]) for sid, doc in docs.items()), reverse=True)
    return [{"source_id": sid, "path": p, "score": score} for score, sid, p in ranked if score > 0][:limit]

if __name__ == "__main__":
    print(json.dumps(query(" ".join(sys.argv[1:])), indent=2))
