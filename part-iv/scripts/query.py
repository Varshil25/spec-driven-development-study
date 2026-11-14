"""query.py: answer a question from the distilled wiki, in the Oracle's voice (the acceptance test).

Usage: python3 scripts/query.py "Does SDD improve security?"   |   python3 scripts/query.py --key Q3
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import index  # noqa: E402
import llm  # noqa: E402
import synthesize  # noqa: E402

SYSTEM = """Answer the question from the knowledge-base excerpts only, in the Oracle's voice (oracle.md).
Cite every claim with its source tag such as [S03] and keep evidence-class labels.
If the excerpts do not answer it, say so."""


def answer(question, k=8):
    hits = index.query(question, k)
    context = "\n\n".join("<<< wiki/%s (score %.2f) >>>\n%s" % (ref, s, doc) for ref, s, doc in hits)
    oracle = (common.SPECS / "oracle.md").read_text(encoding="utf-8")
    text, model = llm.complete(SYSTEM, "<<< ai_specs/oracle.md >>>\n%s\n\n%s\n\nQuestion: %s" % (oracle, context, question))
    return text, model, [ref for ref, _, _ in hits]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("question", nargs="?")
    ap.add_argument("--key", help="ask one of the Oracle's key questions, e.g. Q3")
    args = ap.parse_args(argv)
    question = synthesize.key_questions()[args.key] if args.key else args.question
    text, model, refs = answer(question)
    print(text)
    print("\n-- retrieved: %s | model: %s" % (", ".join(refs), model))
    return 0


if __name__ == "__main__":
    sys.exit(main())
