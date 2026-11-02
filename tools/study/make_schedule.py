#!/usr/bin/env python3
"""Generate the pre-registered run schedule (reproducible from the seed).

Design (Week 7, before freezing): 5 tasks x 4 conditions = 20 study builds,
each followed in the same clone by the task's change request (run ID + "C",
for example R004C), preceded by 2 mechanics checks on the pilot task
(excluded from analysis). The fourth condition, sdd_secure, was added in
Week 7; the Python rows were regenerated from the same seed at that point,
before any study run.

  * Condition order within each task is one of the 24 permutations of
    (unstructured, sdd, sdd_clarify, sdd_secure). Five distinct permutations
    are drawn such that every condition appears in every serial position at
    least once (and so once or twice).
  * Runs are grouped into four rounds. Round k holds the k-th condition of
    every task, with tasks in the same drawn order each round. A task's
    builds are therefore at least five runs apart.
  * Run IDs: rounds 1-3 are R004-R018 and round 4 is R034-R038 (R019-R033
    were already assigned). Change requests take the build's ID plus "C".
  * Optional replication (R021-R023, R039): one task, drawn now, is re-run
    under all four conditions after the main study if time allows, to
    estimate run-to-run variability within a cell. R019-R020 are spare IDs.

Java/Quarkus extension (added in Week 7, before freezing; see
docs/PREREGISTRATION-JAVA.md): 2 tasks x 3 conditions = 6 runs (R026-R031),
preceded by 2 mechanics checks on T-QCOUNT-01 (R024-R025, excluded from
analysis). The Python rows above are generated exactly as before; the Java
draw uses its own random stream, so adding it changes no Python row.

  * The two Java tasks get two condition orders that differ in every serial
    position, so no condition is first (or second, or third) for both.
  * A Java task's k-th run is placed after Python round k, so each round is
    run as 5 Python runs followed by 2 Java runs. R032-R033 are Java spares.

Usage: python3 tools/study/make_schedule.py [--seed 20261023] > schedule/schedule.csv
"""

import argparse
import csv
import itertools
import random
import sys
from collections import Counter

TASKS = ["T-REDACT-01", "T-TARX-01", "T-BOOKMARKS-01", "T-ACCOUNTS-01", "T-PASTE-01"]
CONDITIONS = ["unstructured", "sdd", "sdd_clarify", "sdd_secure"]
JAVA_CONDITIONS = ["unstructured", "sdd", "sdd_clarify"]  # the Java addendum keeps three
ROUND_IDS = {1: range(4, 9), 2: range(9, 14), 3: range(14, 19), 4: range(34, 39)}
REPLICATION_IDS = ["R021", "R022", "R023", "R039"]
MECHANICS = [("R002", "T-SPLIT-01", "unstructured", "mechanics"),
             ("R003", "T-SPLIT-01", "sdd_clarify", "mechanics")]
JAVA_TASKS = ["T-QNOTES-01", "T-QIMPORT-01"]
JAVA_MECHANICS = [("R024", "T-QCOUNT-01", "unstructured", "mechanics-java"),
                  ("R025", "T-QCOUNT-01", "sdd_clarify", "mechanics-java")]
JAVA_FIRST_ID = 26


def balanced(perm_set):
    """True if every condition appears in every serial position at least once."""
    for position in range(len(CONDITIONS)):
        if set(p[position] for p in perm_set) != set(CONDITIONS):
            return False
    return True


def build(seed):
    rng = random.Random(seed)
    tasks = TASKS[:]
    rng.shuffle(tasks)
    perms = list(itertools.permutations(CONDITIONS))
    rng.shuffle(perms)
    chosen_perms = next(c for c in itertools.combinations(perms, len(tasks)) if balanced(c))
    chosen = dict(zip(tasks, chosen_perms))
    rows = [dict(run_id=r, task_id=t, condition=c, round="0", purpose=p) for r, t, c, p in MECHANICS]
    for round_index in range(len(CONDITIONS)):
        for task, number in zip(tasks, ROUND_IDS[round_index + 1]):
            rows.append(dict(run_id="R%03d" % number, task_id=task,
                             condition=chosen[task][round_index], round=str(round_index + 1),
                             purpose="study"))
    replicate = rng.choice(TASKS)
    order = list(rng.choice(perms))
    for run_id, condition in zip(REPLICATION_IDS, order):
        rows.append(dict(run_id=run_id, task_id=replicate, condition=condition,
                         round="R", purpose="replication-optional"))
    return rows, tasks, chosen


def build_java(seed):
    """Java extension draw, from its own random stream (string seeds are stable)."""
    rng = random.Random("java-%d" % seed)
    tasks = JAVA_TASKS[:]
    rng.shuffle(tasks)
    perms = list(itertools.permutations(JAVA_CONDITIONS))
    rng.shuffle(perms)
    first = perms[0]
    second = next(p for p in perms[1:] if all(a != b for a, b in zip(first, p)))
    chosen = {tasks[0]: first, tasks[1]: second}
    rounds = {}
    number = JAVA_FIRST_ID
    for round_index in range(3):
        for task in tasks:
            rounds.setdefault(round_index + 1, []).append(dict(
                run_id="R%03d" % number, task_id=task, condition=chosen[task][round_index],
                round=str(round_index + 1), purpose="study-java"))
            number += 1
    mechanics = [dict(run_id=r, task_id=t, condition=c, round="0", purpose=p)
                 for r, t, c, p in JAVA_MECHANICS]
    return mechanics, rounds, tasks, chosen


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20261023)
    parser.add_argument("--python-only", action="store_true",
                        help="emit only the Python rows")
    args = parser.parse_args(argv)
    rows, tasks, chosen = build(args.seed)
    if not args.python_only:
        java_mechanics, java_rounds, java_tasks, java_chosen = build_java(args.seed)
        python_rows = rows
        rows = []
        round_seen = None
        for row in python_rows:
            # close a Python round: append that round's Java runs before the next round starts
            if round_seen and row["round"] != round_seen and round_seen in ("1", "2", "3"):
                rows += java_rounds.pop(int(round_seen), [])
            rows.append(row)
            round_seen = row["round"]
            if row["run_id"] == MECHANICS[-1][0]:
                rows += java_mechanics
        for key in sorted(java_rounds):
            rows += java_rounds[key]
    writer = csv.DictWriter(sys.stdout, fieldnames=["run_id", "task_id", "condition", "round", "purpose"],
                            lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    # balance report on stderr, so stdout stays a clean CSV
    study = [r for r in rows if r["purpose"] == "study"]
    print("seed %d; task order %s" % (args.seed, ", ".join(tasks)), file=sys.stderr)
    for position in range(len(CONDITIONS)):
        counts = Counter(chosen[t][position] for t in tasks)
        print("position %d: %s" % (position + 1, dict(sorted(counts.items()))), file=sys.stderr)
    print("%d study runs" % len(study), file=sys.stderr)
    if not args.python_only:
        print("java seed stream 'java-%d'; task order %s" % (args.seed, ", ".join(java_tasks)),
              file=sys.stderr)
        for task in java_tasks:
            print("  %s: %s" % (task, " -> ".join(java_chosen[task])), file=sys.stderr)
        print("%d java study runs" % sum(1 for r in rows if r["purpose"] == "study-java"),
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
