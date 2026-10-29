#!/usr/bin/env bash
# Build the Java base repository: the single starting point for every Java run
# (R024-R033, docs/PREREGISTRATION-JAVA.md).
#
#   bash tools/study/make_base_java.sh <sdd-pilot dir> <study kit dir> <new base dir>
#
# It is the Python base (make_base.sh: sddlog 1.2 + Claude Code hooks, web
# tools denied, no Spec Kit) plus ONE commit that adds the pinned Quarkus
# project skeleton from tools/study/java-skeleton:
#   Java 21 · Quarkus platform 3.40.1.1 · Maven 3.9.11 via the Maven wrapper 3.3.4
#   extensions: rest, rest-jackson, hibernate-orm-panache, jdbc-h2,
#               hibernate-validator; tests: quarkus-junit, rest-assured
# The skeleton has no Java sources, so every line of product code in a run is
# the agent's. Build output (target/) is ignored, so it never reaches the
# capture commits or the files-touched measure.
set -euo pipefail

KIT=$(cd "$2" && pwd)
BASE=$3

bash "$KIT/tools/study/make_base.sh" "$1" "$2" "$BASE"

cd "$BASE"
cp -R "$KIT/tools/study/java-skeleton/." .
printf 'target/\n.quarkus/\n' >> .gitignore
git add -A
git -c user.name="sdd-study" -c user.email="sdd-study@localhost" \
    commit -q -m "java base v1: Quarkus 3.40.1.1 skeleton (Java 21, Maven wrapper 3.3.4 / Maven 3.9.11)"
git tag base-java-v1

echo
echo "Java base ready at $BASE"
echo "  commit $(git rev-parse HEAD)  (tag base-java-v1)"
echo "Record this commit hash in docs/PREREGISTRATION-JAVA.md, section 9."
echo "Check that it builds and starts before R024:"
echo "  (cd $BASE && ./mvnw -q -B -DskipTests package && ls target/quarkus-app/quarkus-run.jar)"
