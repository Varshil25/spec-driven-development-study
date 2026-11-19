"""Collect reviewed local source text, without fetching unverified URLs."""
import hashlib
import json
from pathlib import Path
from paths import ROOT, KDB, STATE

def collect():
    entries = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("sources.json must be a list")
    old_path = STATE / "manifest.json"
    old = json.loads(old_path.read_text()) if old_path.exists() else {}
    new, changed, errors = {}, [], []
    (KDB / "raw").mkdir(parents=True, exist_ok=True)
    for item in entries:
        try:
            sid = item["id"]
            filename = item["file"]
            if not isinstance(sid, str) or not sid or not all(c.isalnum() or c in "-_" for c in sid):
                raise ValueError("invalid source id")
            if not isinstance(filename, str) or Path(filename).name != filename or Path(filename).suffix not in (".md", ".txt"):
                raise ValueError("invalid local filename")
            if item.get("trusted") is not True:
                raise ValueError("not an approved source")
            if not item.get("url") or not item.get("license") or item.get("evidence_class") not in ("measured", "reported case", "observed", "documented", "claimed", "argued"):
                raise ValueError("missing metadata")
            path = KDB / "links" / filename
            if path.is_symlink() or not path.is_file():
                raise ValueError("missing or symlink source")
            data = path.read_bytes()
            data.decode("utf-8")
            digest = hashlib.sha256(data).hexdigest()
            if sid in new:
                raise ValueError("duplicate id")
            new[sid] = {**item, "sha256": digest}
            target = KDB / "raw" / (sid + ".txt")
            if old.get(sid, {}).get("sha256") != digest or not target.exists():
                target.write_bytes(data)
                changed.append(sid)
        except (KeyError, OSError, ValueError, UnicodeError, TypeError) as exc:
            errors.append(f"{item.get('id', '?') if isinstance(item, dict) else '?'}: {exc}")
    STATE.mkdir(exist_ok=True)
    old_path.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"collected": len(new), "changed": changed, "errors": errors}
