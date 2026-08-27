from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from claude_behavior_eval.judge import ClaudeRubricJudge, _SYSTEM_PROMPT
from claude_behavior_eval.judge_prompt import assemble_prompt, prompt_sha256
from claude_behavior_eval.schemas import DatasetItem, MRBenchEvaluation

_JUDGE_DIMENSIONS = list(MRBenchEvaluation.model_fields.keys())
_EXCERPT_LENGTH = 120

_TRUE_LABELS = {"Yes", "yes", "TRUE", "true", "1"}
_FALSE_LABELS = {"No", "no", "FALSE", "false", "0"}


def parse_human_label(value: str) -> bool:
    """Parse a boolean Yes/No human annotation label to bool."""
    normalized = value.strip()
    if normalized in _TRUE_LABELS:
        return True
    if normalized in _FALSE_LABELS:
        return False
    raise ValueError(f"Unknown human label: {value!r}")


def parse_tone_label(value: str) -> bool:
    """Convert a MRBench categorical Tutor_Tone label to bool for quantitative evaluation.

    MRBench Tutor_Tone is categorical rather than boolean. We preserve the pedagogical
    distinction between Neutral and Encouraging by reformulating tone as a binary
    Encouraging-vs-Neutral metric. The single/rare Offensive class is excluded from the
    quantitative split because it has insufficient support for reliable Macro-F1 evaluation.
    Therefore: Encouraging=True (active encouragement), Neutral=False (not encouraging).
    False does NOT mean bad or offensive — it means the tone is neutral/not encouraging.

    Offensive labels must be filtered out by 01_create_splits.py before reaching this function.
    """
    v = value.strip()
    if v == "Encouraging":
        return True
    if v == "Neutral":
        return False
    raise ValueError(
        f"Unknown or excluded tutor_tone label: {value!r}. "
        "Offensive examples must be filtered out before running validate_judge."
    )


def compute_binary_metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, float]:
    n = len(y_true)
    if n == 0:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)

    accuracy = (tp + tn) / n * 100.0
    precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}


# Each entry: (human_val, judge_val, item_id, judge_reason, tutor_response_excerpt)
_DimEntry = tuple[bool, bool, str, str, str]


def _parse_dim_label(dim: str, value: str) -> bool:
    """Dispatch to the correct label parser based on dimension name."""
    if dim == "tutor_tone":
        return parse_tone_label(value)
    return parse_human_label(value)


def _truncated_count(judge: object) -> int:
    """Read a judge's truncated-reason count, tolerating test doubles (→ 0)."""
    value = getattr(judge, "truncated_reason_count", 0)
    return value if isinstance(value, int) else 0


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def validate_judge(
    input_csv: Path,
    output_jsonl: Path,
    report_md: Path,
    judge: ClaudeRubricJudge | None = None,
    judge_prompt_version: str | None = None,
    resume: bool = False,
) -> dict[str, object]:
    # Resolve the prompt actually used, its version label, and its SHA-256.
    # With a version: assemble judge_prompts/<version>.txt (regardless of FROZEN)
    #   and use it, so DEV runs of candidate versions need not edit judge.py.
    # Without a version: behaviour is unchanged — the frozen judge.py prompt.
    if judge_prompt_version is not None:
        prompt_text = assemble_prompt(judge_prompt_version)
    else:
        prompt_text = _SYSTEM_PROMPT
    judge_prompt_sha256 = prompt_sha256(prompt_text)

    if judge is None:
        judge = (
            ClaudeRubricJudge(system_prompt=prompt_text)
            if judge_prompt_version is not None
            else ClaudeRubricJudge()
        )

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    # --resume: keep already-completed rows and skip their item_ids.
    existing_ids: set[str] = set()
    write_mode = "w"
    if resume and output_jsonl.exists():
        existing_ids = {r["item_id"] for r in _read_jsonl(output_jsonl)}
        write_mode = "a"

    # Stream each new row to disk and flush per row, so a crash keeps completed rows
    # instead of losing the whole run.
    with input_csv.open(encoding="utf-8", newline="") as f, \
            output_jsonl.open(write_mode, encoding="utf-8") as out:
        for row in csv.DictReader(f):
            item_id = row["id"]
            if item_id in existing_ids:
                continue

            raw_constraints = row.get("instruction_constraints", "").strip()
            instruction_constraints = json.loads(raw_constraints) if raw_constraints else []

            raw_rubric = row.get("expected_rubric", "").strip()
            expected_rubric = json.loads(raw_rubric) if raw_rubric else {}

            item = DatasetItem(
                id=item_id,
                student_question=row["student_question"],
                target_learner_level=row["target_learner_level"],
                instruction_constraints=instruction_constraints,
                expected_rubric=expected_rubric,
            )

            tutor_response = row["tutor_response"]
            evaluation = judge.evaluate_response(item, tutor_response)
            excerpt = tutor_response[:_EXCERPT_LENGTH]

            human_labels: dict[str, bool] = {}
            judge_labels: dict[str, bool] = {}
            judge_reasons: dict[str, str] = {}
            matches: dict[str, bool] = {}

            for dim in _JUDGE_DIMENSIONS:
                human_val = _parse_dim_label(dim, row[f"human_{dim}"])
                judgment = getattr(evaluation, dim)
                human_labels[dim] = human_val
                judge_labels[dim] = judgment.passed
                judge_reasons[dim] = judgment.reason
                matches[dim] = human_val == judgment.passed

            out.write(json.dumps({
                "item_id": item_id,
                "judge_prompt_version": judge_prompt_version,
                "judge_prompt_sha256": judge_prompt_sha256,
                "human_labels": human_labels,
                "judge_labels": judge_labels,
                "judge_reasons": judge_reasons,
                "matches": matches,
                "tutor_response_excerpt": excerpt,
            }) + "\n")
            out.flush()

    # Compute metrics and the report from the FULL file (resumed + newly written rows).
    dim_data: dict[str, list[_DimEntry]] = {dim: [] for dim in _JUDGE_DIMENSIONS}
    for r in _read_jsonl(output_jsonl):
        for dim in _JUDGE_DIMENSIONS:
            dim_data[dim].append((
                bool(r["human_labels"][dim]),
                bool(r["judge_labels"][dim]),
                r["item_id"],
                r["judge_reasons"][dim],
                r.get("tutor_response_excerpt", ""),
            ))

    per_dimension: dict[str, dict[str, float]] = {}
    for dim in _JUDGE_DIMENSIONS:
        entries = dim_data[dim]
        per_dimension[dim] = compute_binary_metrics(
            [e[0] for e in entries],
            [e[1] for e in entries],
        )

    macro_f1 = sum(per_dimension[dim]["f1"] for dim in _JUDGE_DIMENSIONS) / len(_JUDGE_DIMENSIONS)
    macro_accuracy = sum(per_dimension[dim]["accuracy"] for dim in _JUDGE_DIMENSIONS) / len(_JUDGE_DIMENSIONS)

    metrics: dict[str, object] = {
        "macro_f1": macro_f1,
        "macro_accuracy": macro_accuracy,
        "per_dimension": per_dimension,
        "judge_prompt_version": judge_prompt_version,
        "judge_prompt_sha256": judge_prompt_sha256,
        "truncated_reason_count": _truncated_count(judge),
    }

    _write_report(report_md, metrics, dim_data)

    print("Judge Reliability Report")
    print(f"  Macro F1:       {macro_f1:.1f}%")
    print(f"  Macro Accuracy: {macro_accuracy:.1f}%")
    print("  Per-dimension F1:")
    for dim in _JUDGE_DIMENSIONS:
        vals = [e[0] for e in dim_data[dim]]
        n_true = sum(vals)
        n_false = len(vals) - n_true
        balance_warn = "  ⚠️  single-class" if n_true == 0 or n_false == 0 else ""
        print(f"    {dim}: {per_dimension[dim]['f1']:.1f}%{balance_warn}")

    return metrics


def _write_report(
    report_md: Path,
    metrics: dict[str, object],
    dim_data: dict[str, list[_DimEntry]],
) -> None:
    macro_f1: float = metrics["macro_f1"]  # type: ignore[assignment]
    macro_accuracy: float = metrics["macro_accuracy"]  # type: ignore[assignment]
    per_dimension: dict[str, dict[str, float]] = metrics["per_dimension"]  # type: ignore[assignment]
    version = metrics.get("judge_prompt_version")
    sha = metrics.get("judge_prompt_sha256")
    truncated = metrics.get("truncated_reason_count", 0)

    lines: list[str] = [
        "# Judge Validation Report",
        "",
        f"**Judge prompt version:** {version if version is not None else 'judge.py (frozen)'}  ",
        f"**Judge prompt SHA-256:** {sha}  ",
        f"**Reasons truncated (>25 words):** {truncated}  ",
        f"**Macro F1:** {macro_f1:.1f}%  ",
        f"**Macro Accuracy:** {macro_accuracy:.1f}%",
        "",
        "## Dimension Metrics",
        "",
        "| Dimension | Accuracy | Precision | Recall | F1 |",
        "|---|---|---|---|---|",
    ]

    for dim in _JUDGE_DIMENSIONS:
        m = per_dimension[dim]
        lines.append(
            f"| {dim} | {m['accuracy']:.1f}% | {m['precision']:.1f}% "
            f"| {m['recall']:.1f}% | {m['f1']:.1f}% |"
        )

    lines += ["", "## Weakest Dimensions", ""]

    sorted_dims = sorted(_JUDGE_DIMENSIONS, key=lambda d: per_dimension[d]["f1"])

    for dim in sorted_dims:
        f1 = per_dimension[dim]["f1"]
        lines.append(f"### {dim} (F1: {f1:.1f}%)")
        lines.append("")

        disagreements = [
            (item_id, human, judge_val, reason, excerpt)
            for (human, judge_val, item_id, reason, excerpt) in dim_data[dim]
            if human != judge_val
        ]

        if not disagreements:
            lines.append("No disagreements.")
            lines.append("")
            continue

        for item_id, human, judge_val, reason, excerpt in disagreements[:3]:
            lines += [
                f"- **Item:** {item_id}",
                f"  - **Human:** {human}",
                f"  - **Judge:** {judge_val}",
                f"  - **Reason:** {reason}",
                f"  - **Excerpt:** {excerpt!r}",
                "",
            ]

    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate ClaudeRubricJudge alignment against MRBench human annotations."
    )
    parser.add_argument("--input-csv", required=True, help="Path to validation CSV.")
    parser.add_argument(
        "--output-jsonl", default="judge_validation_results.jsonl",
        help="Path to write per-row JSONL results.",
    )
    parser.add_argument(
        "--report-md", default="judge_validation_report.md",
        help="Path to write the Markdown report.",
    )
    parser.add_argument(
        "--judge-prompt-version", default=None,
        help=(
            "Assemble the judge prompt from judge_prompts/<version>.txt + calibration "
            "examples and use it instead of judge.py's _SYSTEM_PROMPT. Convention: name "
            "candidate outputs judge_dev_results_<version>.jsonl / "
            "judge_dev_report_<version>.md. Omit to use the frozen judge.py prompt."
        ),
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="If the output JSONL already exists, keep its rows and skip item_ids "
             "already present (re-evaluate only the remaining items).",
    )

    args = parser.parse_args()

    validate_judge(
        input_csv=Path(args.input_csv),
        output_jsonl=Path(args.output_jsonl),
        report_md=Path(args.report_md),
        judge_prompt_version=args.judge_prompt_version,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
