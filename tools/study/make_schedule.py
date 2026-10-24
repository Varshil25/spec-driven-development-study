#!/usr/bin/env python3
"""Generate the pre-registered run schedule (reproducible from the seed).

Design: 5 tasks x 3 conditions = 15 study runs, preceded by 2 mechanics
checks on the pilot task (excluded from analysis).

  * Condition order within each task is one of the 6 permutations of
    (unstructured, sdd, sdd_clarify). Five distinct permutations are drawn,
    so every condition appears in every serial position once or twice.
  * Runs are grouped into three rounds. Round k holds the k-th condition of
    every task, with tasks in the same drawn order each round. A task's three
    runs are therefore at least four runs apart, which limits how much the
    operator's memory of one run of a task carries into the next.
  * Optional replication (R021-R023): one task, drawn now, is re-run under all
    three conditions after the main study if time allows, to estimate
    run-to-run variability within a cell. R019-R020 are spare IDs for reruns.

Usage: python3 tools/study/make_schedule.py [--seed 20261023] > schedule/schedule.csv
"""

import argparse
import csv
import itertools
import random
import sys
from collections import Counter

TASKS = ["T-REDACT-01", "T-TARX-01", "T-BOOKMARKS-01", "T-ACCOUNTS-01", "T-PASTE-01"]
CONDITIONS = ["unstructured", "sdd", "sdd_clarify"]
MECHANICS = [("R002", "T-SPLIT-01", "unstructured", "mechanics"),
             ("R003", "T-SPLIT-01", "sdd_clarify", "mechanics")]


def build(seed):
    rng = random.Random(seed)
    tasks = TASKS[:]
    rng.shuffle(tasks)
    perms = list(itertools.permutations(CONDITIONS))
    rng.shuffle(perms)
    chosen = dict(zip(tasks, perms[:5]))
    rows = [dict(run_id=r, task_id=t, condition=c, round="0", purpose=p) for r, t, c, p in MECHANICS]
    number = 4
    for round_index in range(3):
        for task in tasks:
            rows.append(dict(run_id="R%03d" % number, task_id=task,
                             condition=chosen[task][round_index], round=str(round_index + 1),
                             purpose="study"))
            number += 1
    replicate = rng.choice(TASKS)
    order = list(rng.choice(perms))
    for offset, condition in enumerate(order):
        rows.append(dict(run_id="R%03d" % (21 + offset), task_id=replicate, condition=condition,
                         round="R", purpose="replication-optional"))
    return rows, tasks, chosen


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20261023)
    args = parser.parse_args(argv)
    rows, tasks, chosen = build(args.seed)
    writer = csv.DictWriter(sys.stdout, fieldnames=["run_id", "task_id", "condition", "round", "purpose"],
                            lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    # balance report on stderr, so stdout stays a clean CSV
    study = [r for r in rows if r["purpose"] == "study"]
    print("seed %d; task order %s" % (args.seed, ", ".join(tasks)), file=sys.stderr)
    for position in range(3):
        counts = Counter(chosen[t][position] for t in tasks)
        print("position %d: %s" % (position + 1, dict(sorted(counts.items()))), file=sys.stderr)
    print("%d study runs" % len(study), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
