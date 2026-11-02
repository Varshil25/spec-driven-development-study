#!/usr/bin/env bash
# Build the study's base repository: the single starting point for every run.
#
#   bash tools/study/make_base.sh <sdd-pilot dir> <study kit dir> <new base dir>
#
# The base holds only the instrument (sddlog v1.2) and the Claude Code hooks
# that feed it. It deliberately does NOT contain Spec Kit: Spec Kit installs
# its commands as Claude Code skills that the model may invoke on its own, so
# having them present would contaminate the unstructured condition. SDD runs
# add Spec Kit in one recorded setup commit on top of this base (RUNBOOK.md).
set -euo pipefail

PILOT=$(cd "$1" && pwd)
KIT=$(cd "$2" && pwd)
BASE=$3

if [ -e "$BASE" ]; then
  echo "refusing to overwrite existing path: $BASE" >&2
  exit 1
fi
if [ ! -f "$PILOT/.claude/settings.json" ]; then
  echo "no hook settings at $PILOT/.claude/settings.json (copy them from the R001 repository)" >&2
  exit 1
fi

mkdir -p "$BASE"
cd "$BASE"
git init -q
git checkout -q -b main

mkdir -p tools/sddlog/tests .claude
cp "$KIT/tools/sddlog/sddlog.py" tools/sddlog/sddlog.py
cp "$KIT/tools/sddlog/tests/test_sddlog.py" tools/sddlog/tests/test_sddlog.py
cp "$PILOT/.claude/settings.json" .claude/settings.json

# Web tools are off in every run (PREREGISTRATION.md section 5): the task texts
# and answer sheets are public, so an agent must not be able to look them up.
python3 - .claude/settings.json <<'PY'
import json, sys
path = sys.argv[1]
settings = json.load(open(path))
deny = settings.setdefault("permissions", {}).setdefault("deny", [])
for tool in ("WebFetch", "WebSearch"):
    if tool not in deny:
        deny.append(tool)
json.dump(settings, open(path, "w"), indent=2)
open(path, "a").write("\n")
PY

# Interpreter caches would otherwise be committed at every capture point and
# inflate the files-touched measure; this applies identically to every run.
printf '__pycache__/\n*.pyc\n.pytest_cache/\n' > .gitignore

echo "Running the instrument's test suite before freezing the base..."
python3 -m pytest tools/sddlog/tests -q -p no:cacheprovider
find . -name __pycache__ -type d -prune -exec rm -rf {} +

git add -A
git -c user.name="sdd-study" -c user.email="sdd-study@localhost" \
    commit -q -m "study base v1: sddlog 1.2 + Claude Code hooks"
git tag base-v1
echo
echo "Base ready at $BASE"
echo "  commit $(git rev-parse HEAD)  (tag base-v1)"
echo "Record this commit hash in docs/PREREGISTRATION.md, section 11."
