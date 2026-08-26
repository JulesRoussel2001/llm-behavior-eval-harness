"""Local statistics for the paper. No API calls.

Usage (from repo root):

  PYTHONPATH=src .venv/bin/python scripts/06_stats.py \
    --judge-dev judge_dev_results.jsonl \
    --judge-test judge_test_results.jsonl \
    --baseline actor_baseline_run1.jsonl actor_baseline_run2.jsonl actor_baseline_run3.jsonl \
    --optimized actor_optimized_run1.jsonl actor_optimized_run2.jsonl actor_optimized_run3.jsonl \
    --output-md stats_report.md

Judge validation rows must have: item_id, human_labels{dim: bool}, judge_labels{dim: bool}.
Actor rows must have: item_id, judge_scores{dim: {"passed": bool, ...}} (judge_scores may be null).

Outputs, per dimension:
  Judge: n, prevalence of human=True, accuracy, precision, recall, F1, Cohen's kappa,
         Clopper-Pearson 95% CI on accuracy.
  Actor: pass rate per run with Clopper-Pearson 95% CI, mean/min/max across runs,
         exact McNemar p-value on paired items (baseline run k vs optimized run k),
         pooled discordant counts across runs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scipy.stats import beta, binomtest

DIMS = [
    "mistake_identification",
    "mistake_location",
    "answer_revealing_appropriate",
    "providing_guidance",
    "actionability",
    "coherence",
    "tutor_tone",
    "human_likeness",
]


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    return (float(lo), float(hi))


def safe_div(a: float, b: float) -> float:
    return a / b if b else float("nan")


def cohen_kappa(tp: int, fp: int, fn: int, tn: int) -> float:
    n = tp + fp + fn + tn
    if n == 0:
        return float("nan")
    po = (tp + tn) / n
    p_yes = ((tp + fp) / n) * ((tp + fn) / n)
    p_no = ((fn + tn) / n) * ((fp + tn) / n)
    pe = p_yes + p_no
    return safe_div(po - pe, 1 - pe) if pe != 1 else float("nan")


def fmt_pct(x: float) -> str:
    return "nan" if x != x else f"{100 * x:.1f}"


def fmt_ci(ci: tuple[float, float]) -> str:
    return f"[{fmt_pct(ci[0])}, {fmt_pct(ci[1])}]"


# ---------------------------------------------------------------- judge ----


def _obj_mark(dim: str, objective: set[str] | None) -> str:
    """Trailing objective-marker cell ('| ✓ |' / '| — |') or '' when no objective given."""
    if objective is None:
        return ""
    return " ✓ |" if dim in objective else " — |"


def judge_section(name: str, rows: list[dict], objective: set[str] | None = None) -> str:
    n_conv = len({r["item_id"].rsplit("_", 1)[0] for r in rows})
    obj_h = " obj |" if objective is not None else ""
    obj_s = "---|" if objective is not None else ""
    out = [f"## Judge validation: {name}", "",
           f"Rows: {len(rows)} (conversations: {n_conv})", "",
           "| Dimension | n | Human=True % | Acc % | 95% CI (acc) | P % | R % | F1 % | kappa |" + obj_h,
           "|---|---|---|---|---|---|---|---|---|" + obj_s]
    accs, f1s, kappas = [], [], []
    for d in DIMS:
        tp = fp = fn = tn = 0
        for r in rows:
            h = bool(r["human_labels"][d])
            j = bool(r["judge_labels"][d])
            if h and j:
                tp += 1
            elif (not h) and j:
                fp += 1
            elif h and (not j):
                fn += 1
            else:
                tn += 1
        n = tp + fp + fn + tn
        acc = safe_div(tp + tn, n)
        prec = safe_div(tp, tp + fp)
        rec = safe_div(tp, tp + fn)
        f1 = safe_div(2 * prec * rec, prec + rec) if (prec == prec and rec == rec) else float("nan")
        kap = cohen_kappa(tp, fp, fn, tn)
        prev = safe_div(tp + fn, n)
        ci = clopper_pearson(tp + tn, n)
        accs.append(acc); f1s.append(f1); kappas.append(kap)
        out.append(
            f"| {d} | {n} | {fmt_pct(prev)} | {fmt_pct(acc)} | {fmt_ci(ci)} | "
            f"{fmt_pct(prec)} | {fmt_pct(rec)} | {fmt_pct(f1)} | {kap:.2f} |"
            + _obj_mark(d, objective)
        )
    mean = lambda xs: sum(x for x in xs if x == x) / max(1, sum(1 for x in xs if x == x))
    out += ["",
            f"Macro accuracy: {fmt_pct(mean(accs))}%  ·  Macro F1: {fmt_pct(mean(f1s))}%  ·  "
            f"Mean kappa: {mean(kappas):.2f}", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- actor ----


def passed(row: dict, d: str) -> bool:
    s = row.get("judge_scores")
    return bool(s and s.get(d, {}).get("passed", False))


def actor_section(
    baseline_runs: list[list[dict]],
    optimized_runs: list[list[dict]],
    objective: set[str] | None = None,
) -> str:
    k_runs = min(len(baseline_runs), len(optimized_runs))
    out = ["## Actor evaluation: baseline vs optimized", ""]
    out.append(f"Runs: {len(baseline_runs)} baseline, {len(optimized_runs)} optimized; "
               f"items per run: {[len(r) for r in baseline_runs]} / {[len(r) for r in optimized_runs]}")
    obj_h = " obj |" if objective is not None else ""
    obj_s = "---|" if objective is not None else ""
    out += ["",
            "| Dimension | Baseline % (mean [min, max]) | 95% CI run 1 | Optimized % (mean [min, max]) | 95% CI run 1 | Delta (pts) | Discordant b→o / o→b (pooled) | McNemar p (per run) |" + obj_h,
            "|---|---|---|---|---|---|---|---|" + obj_s]

    def rates(runs: list[list[dict]], d: str):
        vals = []
        cis = []
        for rows in runs:
            n = len(rows)
            k = sum(passed(r, d) for r in rows)
            vals.append(safe_div(k, n))
            cis.append(clopper_pearson(k, n))
        return vals, cis

    macro_b, macro_o = [], []
    for d in DIMS + ["__macro__"]:
        if d == "__macro__":
            continue
        vb, cb = rates(baseline_runs, d)
        vo, co = rates(optimized_runs, d)
        macro_b.append(sum(vb) / len(vb)); macro_o.append(sum(vo) / len(vo))
        # paired McNemar per run
        pvals, disc_bo, disc_ob = [], 0, 0
        for i in range(k_runs):
            b = {r["item_id"]: passed(r, d) for r in baseline_runs[i]}
            o = {r["item_id"]: passed(r, d) for r in optimized_runs[i]}
            common = sorted(set(b) & set(o))
            n01 = sum(1 for it in common if (not b[it]) and o[it])   # improved
            n10 = sum(1 for it in common if b[it] and (not o[it]))   # regressed
            disc_bo += n01; disc_ob += n10
            m = n01 + n10
            pvals.append(binomtest(n01, m, 0.5).pvalue if m > 0 else float("nan"))
        mb, mo = sum(vb) / len(vb), sum(vo) / len(vo)
        out.append(
            f"| {d} | {fmt_pct(mb)} [{fmt_pct(min(vb))}, {fmt_pct(max(vb))}] | {fmt_ci(cb[0])} | "
            f"{fmt_pct(mo)} [{fmt_pct(min(vo))}, {fmt_pct(max(vo))}] | {fmt_ci(co[0])} | "
            f"{100 * (mo - mb):+.1f} | {disc_bo} / {disc_ob} | "
            + ", ".join("nan" if p != p else f"{p:.2g}" for p in pvals) + " |"
            + _obj_mark(d, objective)
        )
    mb, mo = sum(macro_b) / len(macro_b), sum(macro_o) / len(macro_o)
    out += ["", f"Macro pass rate (mean over runs): baseline {fmt_pct(mb)}% → optimized {fmt_pct(mo)}% "
                f"({100 * (mo - mb):+.1f} pts)", "",
            "McNemar: exact binomial test on discordant pairs (item passes under exactly one prompt), "
            "paired by item_id within run k. Intervals are Clopper–Pearson 95%.", ""]
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--judge-dev", type=Path)
    p.add_argument("--judge-test", type=Path)
    p.add_argument("--baseline", type=Path, nargs="*", default=[])
    p.add_argument("--optimized", type=Path, nargs="*", default=[])
    p.add_argument("--output-md", type=Path, default=Path("stats_report.md"))
    p.add_argument("--objective-dims-file", type=Path, default=None,
                   help="Optional judge_validated_dimensions.json; adds an 'obj' marker column "
                        "showing which dimensions were in the optimization objective (all 8 still shown).")
    a = p.parse_args()

    objective: set[str] | None = None
    if a.objective_dims_file is not None:
        spec = json.loads(a.objective_dims_file.read_text(encoding="utf-8"))
        objective = set(spec.get("validated", []))

    parts = ["# Statistics report", ""]
    if a.judge_dev:
        parts.append(judge_section("dev", read_jsonl(a.judge_dev), objective))
    if a.judge_test:
        parts.append(judge_section("held-out test", read_jsonl(a.judge_test), objective))
    if a.baseline and a.optimized:
        parts.append(actor_section([read_jsonl(x) for x in a.baseline],
                                   [read_jsonl(x) for x in a.optimized], objective))
    text = "\n".join(parts)
    a.output_md.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
