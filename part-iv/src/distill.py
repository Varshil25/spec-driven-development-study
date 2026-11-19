"""Attribution-first extractive baseline; NOT an LLM Oracle voice check."""
import hashlib
import json
import re
from paths import ROOT, KDB, WIKI, STATE

def distill(force=False):
    manifest = json.loads((STATE / "manifest.json").read_text())
    state_path = STATE / "distilled.json"
    prior = json.loads(state_path.read_text()) if state_path.exists() else {}
    spec_files = ["oracle.md", "domain_knowledge.md", "distillation_techniques.md", "output_format.md"]
    spec_hash = hashlib.sha256(b"".join((ROOT / "ai_specs" / x).read_bytes() for x in spec_files)).hexdigest()
    articles = WIKI / "articles"
    articles.mkdir(parents=True, exist_ok=True)
    current, processed, errors = {}, [], []
    for sid, entry in manifest.items():
        target = articles / (sid + ".md")
        signature = entry["sha256"] + ":" + spec_hash
        current[sid] = signature
        if not force and prior.get(sid) == signature and target.exists():
            continue
        try:
            source = (KDB / "raw" / (sid + ".txt")).read_text(encoding="utf-8")
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", source) if len(s.strip()) > 20]
            if not sentences:
                raise ValueError("no extractable sentences")
            # Short excerpts minimize copying; provenance remains explicit.
            snippets = [s[:180].replace("\n", " ") for s in sentences[:3]]
            title = str(entry.get("title", sid)).replace("\n", " ")
            url = str(entry["url"])
            evidence = str(entry["evidence_class"])
            def q(v): return json.dumps(v, ensure_ascii=False)
            body = ("---\nsource_id: " + q(sid) + "\ntitle: " + q(title) +
                    "\nevidence_class: " + q(evidence) + "\nsource_url: " + q(url) +
                    "\nsource_sha256: " + q(entry["sha256"]) + "\n---\n\n# " + title +
                    "\n\n## Leader\nAttributed extractive baseline; not an Oracle-reviewed conclusion. [" + sid + "]\n\n" +
                    snippets[0] + " [" + sid + "]\n\n## Overview\n" +
                    "\n\n".join(s + " [" + sid + "]" for s in snippets[1:]) +
                    "\n\n## Limitations\nExtractive baseline only; no LLM voice validation or independent fact checking.\n\n" +
                    "## Sources\n- [" + sid + "] " + url + "\n")
            target.write_text(body, encoding="utf-8")
            processed.append(sid)
        except (OSError, ValueError, UnicodeError) as exc:
            errors.append(f"{sid}: {exc}")
            current.pop(sid, None)
    for old_id in set(prior) - set(manifest):
        (articles / (old_id + ".md")).unlink(missing_ok=True)
    state_path.write_text(json.dumps({**{k:v for k,v in prior.items() if k in current and k not in processed}, **{k:current[k] for k in processed}}, indent=2) + "\n")
    return {"redistilled": processed, "errors": errors}
