#!/usr/bin/env bash
# Fetch the pinned SpotBugs + FindSecBugs jars into tools/study/java-sast/lib/.
# Run once before scoring the Java runs (RUNBOOK.md, section 6).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
mvn -q -B -f "$HERE/pom.xml" dependency:copy-dependencies \
    -DoutputDirectory="$HERE/lib" -DincludeScope=runtime
ls "$HERE/lib" | grep -E '^(spotbugs|findsecbugs-plugin)-[0-9]'
