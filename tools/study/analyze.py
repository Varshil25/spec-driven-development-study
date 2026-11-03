#!/usr/bin/env python3
"""Part III analysis: the pre-registered comparisons (PREREGISTRATION.md section 8).

  python3 tools/study/analyze.py --scores DIR [--runs DIR] [--coding DIR] [--out DIR]

Reads, for every Python study run in schedule/schedule.csv:
  DIR/<run>.json, DIR/<run>C.json, DIR/<run>C-regression.json   score_run.py output
  RUNS/<run>/metrics.json, RUNS/<run>C/metrics.json             sddlog metrics (optional)
  CODING/<run>-traceability.csv, -security.csv, -principles.csv  coded sheets (optional)

Writes OUT/results.json and OUT/results.md. A measure with no data is reported
as missing, never guessed. Standard library only; frozen with the
pre-registration, so the analysis cannot be chosen after seeing the data.

The rules it applies (section 8):
  * every measure is compared for all six condition pairs, task by task;
  * a difference is "consistent" when at least 4 tasks differ in the same
    direction (ties count against) and the median paired difference reaches the
    minimum: 10 percentage points for pass rates and traceability coverage, a
    ratio of 1.25 (or 0.8) for time, turns and tokens, 1 for confirmed findings;
  * exact Friedman test across the four conditions, exact two-sided Wilcoxon
    signed-rank tests for the pairs (zero differences dropped) with Holm's
    correction across the six pairs, matched-pairs rank-biserial correlation;
  * exact Spearman correlation between the complexity rank and the measure
    within each condition.
"""

import argparse
import csv
import itertools
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
CONDITIONS = ["unstructured", "sdd", "sdd_clarify", "sdd_secure"]
PAIRS = list(itertools.combinations(CONDITIONS, 2))
# Pre-registered complexity index (section 4): rank of the reference implementation's SLOC.
COMPLEXITY_RANK = {"T-REDACT-01": 1, "T-TARX-01": 2, "T-BOOKMARKS-01": 3, "T-ACCOUNTS-01": 4,
                   "T-PASTE-01": 5}
TASKS = sorted(COMPLEXITY_RANK, key=COMPLEXITY_RANK.get)
YES = {"y", "yes", "1", "true"}

# name: (kind, label, registered comparison and main contrast, or None if descriptive only)
# kind "rate" -> difference in percentage points; "ratio" -> per-task ratio; "count" -> difference.
MEASURES = {
    "tier_a": ("rate", "Tier A pass rate", "P1", ("sdd", "unstructured")),
    "tier_c": ("rate", "Tier C pass rate", "P2", ("sdd", "unstructured")),
    "findings": ("count", "Confirmed findings", "P2", ("sdd", "unstructured")),
    "findings_high_medium": ("count", "Confirmed High+Medium findings", "P2", ("sdd", "unstructured")),
    "trace_coverage": ("rate", "Traceability coverage", "P3", ("sdd", "unstructured")),
    "explicit_link_rate": ("rate", "Explicit-link rate", "P3", ("sdd", "unstructured")),
    "active_seconds": ("ratio", "Active time (s)", "P4", ("sdd", "unstructured")),
    "human_turns": ("ratio", "Human turns", "P4", ("sdd", "unstructured")),
    "tokens": ("ratio", "Tokens (input incl. cache + output)", "P4", ("sdd", "unstructured")),
    "tier_b": ("rate", "Tier B pass rate", "P5", ("sdd_clarify", "sdd")),
    "post_plan_revisions": ("count", "Post-plan revisions", "P6", None),
    "principles_met": ("count", "Principles met (0-3)", "P7", None),
    "cr_tier_a": ("rate", "Change request tier A", "P9", ("sdd", "unstructured")),
    "regression": ("rate", "Regression: original tiers A and C after the change", "P9",
                   ("sdd", "unstructured")),
    "cr_tier_b": ("rate", "Change request tier B", "P9", ("sdd", "unstructured")),
    "cr_tier_c": ("rate", "Change request tier C", "P10", ("sdd_secure", "sdd")),
    "cr_findings": ("count", "Confirmed findings in the change", "P10", ("sdd_secure", "sdd")),
    "cr_active_seconds": ("ratio", "Change request active time (s)", "P9", ("sdd", "unstructured")),
    "cr_tokens": ("ratio", "Change request tokens", "P9", ("sdd", "unstructured")),
    "cr_human_turns": ("ratio", "Change request human turns", "P9", ("sdd", "unstructured")),
    "cr_edits_original_spec": ("count", "Change request edits the original spec (0/1)", "P11", None),
}
# P8 (sdd_secure vs sdd on tier C, findings and active time) and the second P10 contrast are
# read from the all-pairs tables; they are listed here so the report names them.
EXTRA_CONTRASTS = {"tier_c": [("sdd_secure", "sdd")], "findings": [("sdd_secure", "sdd")],
                   "findings_high_medium": [("sdd_secure", "sdd")],
                   "active_seconds": [("sdd_secure", "sdd")],
                   "cr_tier_c": [("sdd", "unstructured")], "cr_findings": [("sdd", "unstructured")]}
MINIMUM = {"rate": 0.10, "ratio": 1.25, "count": 1}


# ---------------------------------------------------------------------------
# exact tests
# ---------------------------------------------------------------------------


def midranks(values):
    """Ranks 1..n, ties sharing the mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def wilcoxon_exact(diffs):
    """Two-sided exact signed-rank p and the rank-biserial r; zeros dropped. None if no data."""
    nonzero = [d for d in diffs if d != 0]
    if not nonzero:
        return None, None
    ranks = midranks([abs(d) for d in nonzero])
    t_plus = sum(r for r, d in zip(ranks, nonzero) if d > 0)
    total = sum(ranks)
    sums = [sum(r for r, s in zip(ranks, signs) if s) for signs in
            itertools.product((0, 1), repeat=len(ranks))]
    eps = 1e-9
    low = sum(1 for s in sums if s <= t_plus + eps) / len(sums)
    high = sum(1 for s in sums if s >= t_plus - eps) / len(sums)
    rank_biserial = (2 * t_plus - total) / total
    return min(1.0, 2 * min(low, high)), rank_biserial


def friedman_exact(blocks):
    """Exact (conditional on each block's ranks) Friedman p over blocks of k values."""
    if len(blocks) < 2:
        return None, None
    k = len(blocks[0])
    ranked = [midranks(b) for b in blocks]
    n = len(ranked)

    def statistic(rank_sums):
        return 12 / (n * k * (k + 1)) * sum(r * r for r in rank_sums) - 3 * n * (k + 1)

    observed = statistic([sum(col) for col in zip(*ranked)])
    dist = Counter({tuple([0.0] * k): 1})
    for ranks in ranked:
        perms = set(itertools.permutations(ranks))
        new = Counter()
        for sums, count in dist.items():
            for p in perms:
                new[tuple(round(a + b, 6) for a, b in zip(sums, p))] += count
        dist = new
    total = sum(dist.values())
    tail = sum(c for sums, c in dist.items() if statistic(sums) >= observed - 1e-9)
    return tail / total, observed


def spearman_exact(xs, ys):
    """Spearman rho and its exact two-sided p (all permutations of ys)."""
    if len(xs) < 3 or len(set(ys)) < 2:
        return None, None
    rx, ry = midranks(xs), midranks(ys)

    def rho(a, b):
        ma, mb = statistics.mean(a), statistics.mean(b)
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
        return num / den if den else 0.0

    observed = rho(rx, ry)
    perms = list(itertools.permutations(ry))
    extreme = sum(1 for p in perms if abs(rho(rx, list(p))) >= abs(observed) - 1e-9)
    return observed, extreme / len(perms)


def holm(pvalues):
    """Holm-adjusted p-values, same order; None stays None."""
    present = sorted((p, i) for i, p in enumerate(pvalues) if p is not None)
    adjusted = [None] * len(pvalues)
    running = 0.0
    for rank, (p, i) in enumerate(present):
        running = max(running, min(1.0, (len(present) - rank) * p))
        adjusted[i] = running
    return adjusted


def decide(kind, a_values, b_values):
    """Section 8.4 for one pair: (verdict, direction, same-direction count, median effect, n)."""
    pairs = [(a, b) for a, b in zip(a_values, b_values) if a is not None and b is not None]
    if not pairs:
        return "no data", None, 0, None, 0
    if kind == "ratio":
        effects = [a / b if b else (math.inf if a else 1.0) for a, b in pairs]
        ups = sum(1 for e in effects if e > 1)
        downs = sum(1 for e in effects if e < 1)
        median = statistics.median(effects)
        big = median >= MINIMUM["ratio"] or median <= 1 / MINIMUM["ratio"]
    else:
        effects = [a - b for a, b in pairs]
        ups = sum(1 for e in effects if e > 0)
        downs = sum(1 for e in effects if e < 0)
        median = statistics.median(effects)
        big = abs(median) >= MINIMUM[kind] - 1e-9
    direction = "higher" if ups > downs else "lower" if downs > ups else "none"
    same = max(ups, downs)
    median_agrees = (direction == "higher" and (median > 1 if kind == "ratio" else median > 0)) or \
                    (direction == "lower" and (median < 1 if kind == "ratio" else median < 0))
    consistent = same >= 4 and big and median_agrees
    return ("consistent difference" if consistent else "no consistent difference",
            direction, same, median, len(pairs))


# ---------------------------------------------------------------------------
# reading the data
# ---------------------------------------------------------------------------


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def read_csv(path):
    if not path.exists():
        return None
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def pass_rate(score, tiers):
    if not score:
        return None
    passed = sum(score["tiers"][t]["passed"] for t in tiers if t in score["tiers"])
    total = sum(score["tiers"][t]["total"] for t in tiers if t in score["tiers"])
    return passed / total if total else None


def findings(rows, severities=None):
    """Confirmed findings; several confirmed rows with the same CWE and location count once."""
    if rows is None:
        return None
    seen, count = set(), 0
    for row in rows:
        if (row.get("confirmed") or "").strip().lower() not in YES:
            continue
        if severities and (row.get("severity") or "").strip().lower() not in severities:
            continue
        key = ((row.get("cwe") or "").strip(), (row.get("location") or "").strip())
        if key[1] and key in seen:
            continue
        seen.add(key)
        count += 1
    return count


def traceability(rows):
    if not rows:
        return None, None
    coded = [r for r in rows if (r.get("score") or "").strip() != ""]
    if not coded:
        return None, None
    coverage = sum(float(r["score"]) for r in coded) / (2 * len(coded))
    links = sum(1 for r in coded if (r.get("explicit_link") or "").strip().lower() in YES)
    return coverage, links / len(coded)


def principles(rows):
    if not rows:
        return None
    coded = [r for r in rows if (r.get("met") or "").strip() != ""]
    return sum(1 for r in coded if r["met"].strip().lower() in YES) if coded else None


def revisions(metrics, artifacts=("constitution", "spec", "plan", "data-model"),
              phases=("plan", "tasks", "implement")):
    """Section 7.5: distinct hashes of each upstream artifact across plan, tasks and implement, minus 1."""
    if not metrics or not metrics.get("artifacts"):
        return None
    total = 0
    for name in artifacts:
        snaps = metrics["artifacts"].get(name) or {}
        hashes = {snaps[p]["sha256"] for p in phases if p in snaps}
        total += max(0, len(hashes) - 1)
    return total


def edits_original(metrics):
    """1 if a change request changed any snapshot of an earlier feature folder (prior:...), else 0."""
    if not metrics or not metrics.get("artifacts"):
        return None
    prior = {k: v for k, v in metrics["artifacts"].items() if k.startswith("prior:")}
    if not prior:
        return None
    return int(any(len({s["sha256"] for s in snaps.values()}) > 1 for snaps in prior.values()))


def metric(metrics, field):
    if not metrics:
        return None
    totals = metrics.get("totals", {})
    if field == "tokens":
        if "input_tokens_all" not in totals:
            return None
        return totals["input_tokens_all"] + totals.get("output_tokens", 0)
    return totals.get(field)


def run_values(run_id, scores, runs, coding):
    """Every measure for one build and its change request."""
    build = read_json(scores / ("%s.json" % run_id))
    change = read_json(scores / ("%sC.json" % run_id))
    regression = read_json(scores / ("%sC-regression.json" % run_id))
    m_build = read_json(runs / run_id / "metrics.json") if runs else None
    m_change = read_json(runs / ("%sC" % run_id) / "metrics.json") if runs else None
    sec = read_csv(coding / ("%s-security.csv" % run_id)) if coding else None
    sec_c = read_csv(coding / ("%sC-security.csv" % run_id)) if coding else None
    trace = read_csv(coding / ("%s-traceability.csv" % run_id)) if coding else None
    prin = read_csv(coding / ("%s-principles.csv" % run_id)) if coding else None
    coverage, links = traceability(trace)
    return {
        "tier_a": pass_rate(build, ["stated"]),
        "tier_b": pass_rate(build, ["intent"]),
        "tier_c": pass_rate(build, ["security"]),
        "findings": findings(sec),
        "findings_high_medium": findings(sec, {"high", "medium"}),
        "trace_coverage": coverage,
        "explicit_link_rate": links,
        "active_seconds": metric(m_build, "active_seconds"),
        "human_turns": metric(m_build, "human_prompts"),
        "tokens": metric(m_build, "tokens"),
        "post_plan_revisions": revisions(m_build),
        "principles_met": principles(prin),
        "cr_tier_a": pass_rate(change, ["stated"]),
        "cr_tier_b": pass_rate(change, ["intent"]),
        "cr_tier_c": pass_rate(change, ["security"]),
        "regression": pass_rate(regression, ["stated", "security"]),
        "cr_findings": findings(sec_c),
        "cr_active_seconds": metric(m_change, "active_seconds"),
        "cr_tokens": metric(m_change, "tokens"),
        "cr_human_turns": metric(m_change, "human_prompts"),
        "cr_edits_original_spec": edits_original(m_change),
    }


def schedule(kit):
    with open(kit / "schedule" / "schedule.csv", newline="") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# the analysis
# ---------------------------------------------------------------------------


def analyse(kit, scores, runs=None, coding=None):
    rows = schedule(kit)
    study = [r for r in rows if r["purpose"] == "study" and r["task_id"] in COMPLEXITY_RANK]
    replication = [r for r in rows if r["purpose"].startswith("replication")]
    cells = {}
    for row in study:
        cells[(row["task_id"], row["condition"])] = dict(
            run_id=row["run_id"], **run_values(row["run_id"], scores, runs, coding))
    result = {"measures": {}, "replication": []}
    for name, (kind, label, registered, main) in MEASURES.items():
        table = {task: {c: cells.get((task, c), {}).get(name) for c in CONDITIONS} for task in TASKS}
        entry = {"label": label, "kind": kind, "registered": registered, "main_contrast": main,
                 "table": table, "pairs": [], "friedman": None, "spearman": {}}
        complete = [[table[t][c] for c in CONDITIONS] for t in TASKS
                    if all(table[t][c] is not None for c in CONDITIONS)]
        p, q = friedman_exact(complete) if len(complete) >= 2 else (None, None)
        entry["friedman"] = {"p": p, "statistic": q, "tasks": len(complete)}
        raw = []
        for a, b in PAIRS:
            av = [table[t][a] for t in TASKS]
            bv = [table[t][b] for t in TASKS]
            verdict, direction, same, median, n = decide(kind, av, bv)
            diffs = [x - y for x, y in zip(av, bv) if x is not None and y is not None]
            p_w, r_rb = wilcoxon_exact(diffs) if diffs else (None, None)
            raw.append(p_w)
            entry["pairs"].append({"a": a, "b": b, "verdict": verdict, "direction": direction,
                                   "same_direction": same, "median_effect": median, "tasks": n,
                                   "wilcoxon_p": p_w, "rank_biserial": r_rb})
        for pair, adjusted in zip(entry["pairs"], holm(raw)):
            pair["wilcoxon_p_holm"] = adjusted
        for c in CONDITIONS:
            xs = [COMPLEXITY_RANK[t] for t in TASKS if table[t][c] is not None]
            ys = [table[t][c] for t in TASKS if table[t][c] is not None]
            rho, p_s = spearman_exact(xs, ys)
            entry["spearman"][c] = {"rho": rho, "p": p_s, "tasks": len(xs)}
        result["measures"][name] = entry
    for row in replication:
        original = cells.get((row["task_id"], row["condition"]))
        again = run_values(row["run_id"], scores, runs, coding)
        result["replication"].append({
            "run_id": row["run_id"], "task_id": row["task_id"], "condition": row["condition"],
            "original_run": original["run_id"] if original else None,
            "differences": {name: (again[name] - original[name])
                            if original and again[name] is not None and original[name] is not None
                            else None for name in MEASURES}})
    return result


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------


def fmt(kind, value):
    if value is None:
        return "-"
    if kind == "rate":
        return "%.0f%%" % (100 * value)
    if kind == "ratio" and isinstance(value, float) and value != int(value):
        return "%.2f" % value
    return "%g" % value


def fmt_effect(kind, value):
    if value is None:
        return "-"
    if kind == "rate":
        return "%+.0f pp" % (100 * value)
    if kind == "ratio":
        return "%.2fx" % value
    return "%+g" % value


def fmt_p(p):
    return "-" if p is None else ("%.4f" % p if p >= 0.0001 else "%.1e" % p)


def report(result):
    lines = ["# Results (Part III)", "",
             "Generated by `tools/study/analyze.py` from the scores, metrics and coding sheets. "
             "Rules: PREREGISTRATION.md section 8. A dash means no data.", ""]
    for name, m in result["measures"].items():
        kind = m["kind"]
        lines += ["## %s (%s)" % (m["label"], m["registered"]), "",
                  "| Task | " + " | ".join(CONDITIONS) + " |",
                  "| --- |" + " --- |" * len(CONDITIONS)]
        for task in TASKS:
            lines.append("| %s | %s |" % (task, " | ".join(fmt(kind, m["table"][task][c]) for c in CONDITIONS)))
        lines.append("")
        if m["main_contrast"] is None:
            lines += ["Descriptive only (section 8.2).", ""]
        else:
            main = tuple(m["main_contrast"])
            extra = [tuple(x) for x in EXTRA_CONTRASTS.get(name, [])]
            lines += ["| Pair | Verdict | Same direction | Median effect | Wilcoxon p (Holm) | Rank-biserial |",
                      "| --- | --- | --- | --- | --- | --- |"]
            for pair in m["pairs"]:
                key = (pair["a"], pair["b"])
                mark = " (main)" if key == main else " (registered)" if key in extra else ""
                lines.append("| %s vs %s%s | %s | %s of %s | %s | %s (%s) | %s |" % (
                    pair["a"], pair["b"], mark, pair["verdict"], pair["same_direction"], pair["tasks"],
                    fmt_effect(kind, pair["median_effect"]), fmt_p(pair["wilcoxon_p"]),
                    fmt_p(pair["wilcoxon_p_holm"]),
                    "-" if pair["rank_biserial"] is None else "%.2f" % pair["rank_biserial"]))
            f = m["friedman"]
            lines += ["", "Friedman (exact, %d tasks): p = %s." % (f["tasks"], fmt_p(f["p"])), ""]
        spear = ", ".join("%s rho %s (p %s)" % (c, "-" if s["rho"] is None else "%.2f" % s["rho"], fmt_p(s["p"]))
                          for c, s in m["spearman"].items())
        lines += ["Complexity scaling (Spearman, exact): %s." % spear, ""]
    if result["replication"]:
        lines += ["## Replication: second run minus first run, T-REDACT-01", "",
                  "| Measure | " + " | ".join(r["condition"] for r in result["replication"]) + " |",
                  "| --- |" + " --- |" * len(result["replication"])]
        for name, (kind, label, _, _) in MEASURES.items():
            lines.append("| %s | %s |" % (label, " | ".join(
                fmt_effect("count" if kind == "ratio" else kind, r["differences"][name])
                for r in result["replication"])))
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scores", required=True, help="folder of score_run.py JSON files")
    parser.add_argument("--runs", default=None, help="folder of run log folders (logs/runs)")
    parser.add_argument("--coding", default=None, help="folder of coded sheets (coding/runs)")
    parser.add_argument("--out", default="results", help="output folder")
    parser.add_argument("--kit", default=str(KIT))
    args = parser.parse_args(argv)
    result = analyse(Path(args.kit), Path(args.scores),
                     Path(args.runs) if args.runs else None, Path(args.coding) if args.coding else None)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    (out / "results.md").write_text(report(result))
    print("wrote %s and %s" % (out / "results.json", out / "results.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
