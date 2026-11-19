"""Four-stage OpenOwls-style orchestrator with durable logs."""
import argparse
import json
import traceback
from datetime import datetime, timezone
from paths import ROOT, STATE
from collect import collect
from distill import distill
from build_index import build_index
from backup import backup

def run(force=False):
    results = {}
    for name, fn in (("collect", collect), ("distill", lambda: distill(force)), ("index", build_index), ("backup", backup)):
        try:
            results[name] = {"ok": True, **fn()}
            if results[name].get("errors"):
                results[name]["ok"] = False
        except Exception as exc:
            results[name] = {"ok": False, "error": str(exc), "traceback": traceback.format_exc()}
    now = datetime.now(timezone.utc).isoformat()
    STATE.joinpath("runs").mkdir(parents=True, exist_ok=True)
    STATE.joinpath("runs", now.replace(":", "-") + ".json").write_text(json.dumps(results, indent=2) + "\n")
    progress = ROOT / "progress.md"
    outcome = "ok" if all(v["ok"] for v in results.values()) else "review"
    with progress.open("a", encoding="utf-8") as out:
        out.write("| " + now + " | " + " | ".join("ok" if results[n]["ok"] else "error" for n in ("collect", "distill", "index", "backup")) + " | " + outcome + " |\n")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run(args.force)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(v["ok"] for v in result.values()) else 1)
