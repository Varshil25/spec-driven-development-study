"""distill.py: one article per new or changed source, in the Oracle's voice, voice-checked.

Usage: python3 scripts/distill.py [--only S03] [--force]
Exit status: 0 ok, 1 some articles failed the voice check, 2 the LLM was unavailable.
See ai_specs/distillation-techniques.md and ai_specs/output-format.md.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import llm  # noqa: E402
import voice_check  # noqa: E402

SYSTEM = """You are the distillation agent of an OpenOwls SD-KDP knowledge base.
Follow the specification files you are given exactly. They define whose view you write in (the Oracle),
the terms and evidence classes, the article template, and the distillation rules.
Write ONE source article about ONE source, from that source's text only.
Output only the article body in Markdown, starting with the '# ' title line.
Do not write front matter; the pipeline adds it."""

REVIEW = """Here is the Oracle and one article written in its name.
Would the evidence-first software engineer sign this article as written?
Answer with the single word PASS, or with FAIL followed by the sentences that drift
(vendor framing, unearned certainty, needless hedging, a claim placed in a stronger evidence class than the source supports)."""

MAX_SOURCE_CHARS = 120_000


def needs_distill(row, manifest, spec_digest, force=False):
    entry = manifest["sources"].get(row["id"], {})
    if entry.get("status") != "ok":
        return False, "not collected"
    path = common.WIKI / "sources" / ("%s.md" % row["id"])
    if force or not path.exists():
        return True, "new" if not path.exists() else "forced"
    meta, _ = common.read_front_matter(path.read_text(encoding="utf-8"))
    if meta.get("source_sha256") != entry["sha256"]:
        return True, "source changed"
    if meta.get("spec_sha256") != spec_digest:
        return True, "spec changed"
    return False, "unchanged"


def build_prompt(row, text, feedback=None):
    row_text = "\n".join("%s: %s" % (k, v) for k, v in row.items())
    prompt = ("%s\n\n<<< corpus/sources.csv row >>>\n%s\n\n<<< source text: raw/%s.txt >>>\n%s"
              % (common.spec_text(), row_text, row["id"], text[:MAX_SOURCE_CHARS]))
    if len(text) > MAX_SOURCE_CHARS:
        prompt += "\n[source text truncated at %d characters]" % MAX_SOURCE_CHARS
    if feedback:
        prompt += ("\n\n<<< your previous draft failed the voice check >>>\n%s\n"
                   "Write the article again so that it passes." % feedback)
    return prompt


def questions_in(body):
    return sorted(set(re.findall(r"\*\*(Q[1-8])[:*]", body)), key=lambda q: int(q[1:]))


def distill_one(row, manifest, spec_digest, review=True):
    """Return (ok, path, problems)."""
    text = (common.RAW / ("%s.txt" % row["id"])).read_text(encoding="utf-8")
    feedback, problems = None, []
    for _ in range(2):  # one retry with the checker's feedback
        body, model = llm.complete(SYSTEM, build_prompt(row, text, feedback))
        body = body.strip()
        body = re.sub(r"\A```(?:markdown)?\n|\n```\Z", "", body).strip()
        problems = voice_check.check(body, row["id"])
        if not problems and review:
            verdict, _ = llm.complete("You review knowledge-base articles against a declared perspective.",
                                      "%s\n\n<<< ai_specs/oracle.md >>>\n%s\n\n<<< article >>>\n%s"
                                      % (REVIEW, (common.SPECS / "oracle.md").read_text(), body), max_tokens=800)
            if not verdict.strip().upper().startswith("PASS"):
                problems = ["LLM review: " + verdict.strip()[:1500]]
        if not problems:
            break
        feedback = "\n".join(problems)
    if problems:
        return False, None, problems
    meta = {
        "id": row["id"], "title": manifest["sources"][row["id"]].get("title_seen") or row["title"],
        "authors": row["authors_or_publisher"], "date": row["date"], "url": row["url"],
        "licence": row["licence"], "tier": row["tier"], "evidence_type": row["evidence_type"],
        "questions": questions_in(body), "source_sha256": manifest["sources"][row["id"]]["sha256"],
        "spec_sha256": spec_digest, "model": model, "distilled_at": common.now(),
    }
    path = common.WIKI / "sources" / ("%s.md" % row["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(common.write_front_matter(meta, body) + "\n", encoding="utf-8")
    return True, path, []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="comma-separated source IDs")
    ap.add_argument("--force", action="store_true", help="re-distil even if unchanged")
    ap.add_argument("--no-review", action="store_true", help="skip the LLM half of the voice check")
    args = ap.parse_args(argv)
    manifest = common.load_manifest()
    digest = common.spec_hash()
    rows = common.sources()
    if args.only:
        rows = [r for r in rows if r["id"] in set(args.only.split(","))]
    done = failed = skipped = 0
    log = common.STATE / "distill-failures.log"
    for row in rows:
        go, why = needs_distill(row, manifest, digest, args.force)
        if not go:
            skipped += 1
            print("%s skipped (%s)" % (row["id"], why))
            continue
        try:
            ok, path, problems = distill_one(row, manifest, digest, review=not args.no_review)
        except llm.LLMError as exc:
            print("%s LLM unavailable: %s" % (row["id"], exc))
            print("distill: stopped; %d written, %d failed, %d skipped" % (done, failed, skipped))
            return 2
        if ok:
            done += 1
            print("%s distilled (%s) -> %s" % (row["id"], why, path.relative_to(common.ROOT)))
        else:
            failed += 1
            common.STATE.mkdir(exist_ok=True)
            with open(log, "a", encoding="utf-8") as handle:
                handle.write("%s %s\n  %s\n" % (common.now(), row["id"], "\n  ".join(problems)))
            print("%s FAILED the voice check twice (see state/distill-failures.log)" % row["id"])
    print("distill: %d written, %d failed, %d skipped" % (done, failed, skipped))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
