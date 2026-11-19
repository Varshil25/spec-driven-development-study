"""voice_check.py: deterministic checks of a source article (ai_specs/distillation-techniques.md).

Usage: python3 scripts/voice_check.py wiki/sources/S03.md [...]
Prints one line per problem; exit 1 if any article fails.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HYPE = ["revolutionary", "game-changer", "game-changing", "10x", "paradigm shift", "unlock",
        "supercharge", "seamless", "cutting-edge"]
HEDGES = ["may", "might", "could", "potentially", "arguably", "perhaps", "somewhat"]
CLASSES = ["measured", "reported case", "observed", "documented", "claimed", "argued"]
SECTIONS = ["What it is", "What it shows", "What it claims (without measurement)", "Method and limits",
            "Bearing on the key questions", "Quotes"]
TAGGED_SECTIONS = ["What it shows", "What it claims (without measurement)"]
WORDS_PER_HEDGE = 60
MAX_QUOTES, MAX_QUOTE_WORDS = 2, 25


def sections(body):
    """Map '## Heading' -> text under it."""
    out, current = {}, None
    for line in body.splitlines():
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            current = m.group(1)
            out[current] = []
        elif current:
            out[current].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def sentences(text):
    text = re.sub(r"\s+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z*\"(-])", text) if s.strip()]


def check(text, source_id=None):
    problems = []
    meta, body = common.read_front_matter(text)
    sid = source_id or meta.get("id", "")
    parts = sections(body)
    for name in SECTIONS:
        if name not in parts:
            problems.append("missing section: %s" % name)
    tag = re.compile(r"\[S\d{2}\]")
    for name in TAGGED_SECTIONS:
        content = parts.get(name, "")
        if re.fullmatch(r"\(?nothing( beyond what it shows| in the source)?\.?\)?", content.strip(), re.I):
            continue
        for item in re.split(r"\n(?=- )", content):
            item = item.strip()
            if not item or item.lower().startswith("nothing"):
                continue
            for s in sentences(item.lstrip("- ")):
                if not tag.search(s) and len(s.split()) > 3:
                    problems.append("untagged sentence in '%s': %s" % (name, s[:90]))
            if item.startswith("-") and not re.match(r"-\s+\*\*(%s)\*\*" % "|".join(CLASSES), item, re.I):
                problems.append("statement without an evidence class in '%s': %s" % (name, item[:90]))
    lower = body.lower()
    for word in HYPE:
        if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(word), lower):
            problems.append("hype word: %s" % word)
    prose = re.sub(r"^>.*$", "", body, flags=re.M)  # quotes are the source's words, not ours
    words = len(re.findall(r"\b\w+\b", prose))
    hedges = sum(len(re.findall(r"\b%s\b" % h, prose.lower())) for h in HEDGES)
    if words and hedges > max(1, words // WORDS_PER_HEDGE):
        problems.append("hedge density: %d hedges in %d words (limit 1 per %d)" % (hedges, words, WORDS_PER_HEDGE))
    quotes = re.findall(r'^>\s*"(.+?)"', parts.get("Quotes", ""), flags=re.M)
    if len(quotes) > MAX_QUOTES:
        problems.append("%d quotes (limit %d)" % (len(quotes), MAX_QUOTES))
    for q in quotes:
        if len(q.split()) > MAX_QUOTE_WORDS:
            problems.append("quote over %d words: %s" % (MAX_QUOTE_WORDS, q[:60]))
    if sid and ("[%s]" % sid) not in body:
        problems.append("the article never cites its own source tag [%s]" % sid)
    return problems


def main(argv=None):
    paths = argv if argv is not None else sys.argv[1:]
    bad = 0
    for path in paths:
        for problem in check(Path(path).read_text(encoding="utf-8")):
            print("%s: %s" % (path, problem))
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
