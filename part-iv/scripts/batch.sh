#!/usr/bin/env bash
# batch.sh: the unattended nightly run (ai_specs/batch-process.md).
# collect -> distill -> synthesize -> index -> backup. Stops at the first exit status 2.
set -u
cd "$(dirname "$0")/.."
RUN="run-$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p state backups
echo "== $RUN start $(date -u +%FT%TZ)"
status=0; counts=""
for step in collect distill synthesize index; do
  out=$(python3 scripts/$step.py "$@" 2>&1); rc=$?
  echo "$out"; counts="$counts $(echo "$out" | tail -1)."
  [ $rc -eq 2 ] && { echo "== $RUN stopped at $step (exit 2)"; status=2; break; }
  [ $rc -eq 1 ] && status=1
  set --   # extra args (e.g. --from-dir) apply to collect only
done
if [ $status -ne 2 ]; then
  if [ -n "$(git status --porcelain -- wiki corpus)" ]; then
    git add wiki corpus && git commit -qm "part-iv: batch $RUN" -- wiki corpus || status=2
    tar czf "backups/wiki-$RUN.tgz" wiki state/manifest.json
    ls -1t backups/wiki-*.tgz | tail -n +8 | xargs -r rm --
  fi
fi
line="| $(date -u +%F) | $RUN | exit $status |$counts |"
python3 - "$line" <<'PY'
import sys, re
p = "progress.md"; s = open(p).read()
s = re.sub(r"(## Latest batch run\n\n)(.*?)(\n\n## )", lambda m: m.group(1) + sys.argv[1] + m.group(3), s, count=1, flags=re.S)
open(p, "w").write(s)
PY
echo "== $RUN end status $status"
exit $status
