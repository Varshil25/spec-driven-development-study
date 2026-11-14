#!/usr/bin/env bash
# Fetch the pinned SpotBugs + FindSecBugs jars into tools/study/java-sast/lib/.
# Run once before scoring the Java runs (RUNBOOK.md, section 7).
# Uses `mvn` if it is installed, otherwise the Maven wrapper in the Java skeleton.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
if command -v mvn >/dev/null 2>&1; then
  MVN=(mvn)
else
  MVN=(sh "$HERE/../java-skeleton/mvnw")
fi
"${MVN[@]}" -q -B -f "$HERE/pom.xml" dependency:copy-dependencies \
    -DoutputDirectory="$HERE/lib" -DincludeScope=runtime
ls "$HERE/lib" | grep -E '^(spotbugs|findsecbugs-plugin)-[0-9]'
