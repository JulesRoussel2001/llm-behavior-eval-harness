from __future__ import annotations

import argparse
import json
from pathlib import Path

from anthropic import Anthropic

from claude_behavior_eval.config import (
    DEFAULT_ACTOR_MODEL,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_OPTIMIZER_MODEL,
)
from claude_behavior_eval.judge import _SYSTEM_PROMPT as _JUDGE_SYSTEM_PROMPT
from claude_behavior_eval.judge_prompt import prompt_sha256
from claude_behavior_eval.main import ACTOR_SYSTEM_PROMPT, run_evaluation
from claude_behavior_eval.schemas import MRBenchEvaluation

_JUDGE_DIMENSIONS = list(MRBenchEvaluation.model_fields.keys())

_OPTIMIZER_SYSTEM_PROMPT = (
    "You are an expert AI prompt engineer. Your job is to improve a tutor system prompt "
    "based on evaluation metrics while preserving clarity and avoiding prompt bloat."
)


def calculate_metrics(
    jsonl_path: Path,
    objective_dims: list[str] | None = None,
) -> dict[str, float]:
    """Compute pass-rate metrics from an evaluation JSONL.

    When ``objective_dims`` is given, the returned dict contains ONLY
    deterministic_pass_rate, a <dim>_pass_rate for each objective dimension, and a
    judge_macro_pass_rate recomputed as the mean over those dimensions only —
    excluded dimensions do not appear under any key. When omitted, all eight
    dimensions are reported (unchanged behaviour).
    """
    rows: list[dict] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    if not rows:
        return {}

    total = len(rows)
    dims = objective_dims if objective_dims is not None else _JUDGE_DIMENSIONS

    det_pass = sum(1 for r in rows if r.get("deterministic_passed", False))
    metrics: dict[str, float] = {
        "deterministic_pass_rate": (det_pass / total) * 100.0,
    }

    for dim in dims:
        count = 0
        for r in rows:
            scores = r.get("judge_scores")
            if scores is not None and scores.get(dim, {}).get("passed", False):
                count += 1
        metrics[f"{dim}_pass_rate"] = (count / total) * 100.0

    dim_rates = [metrics[f"{dim}_pass_rate"] for dim in dims]
    metrics["judge_macro_pass_rate"] = (sum(dim_rates) / len(dim_rates)) if dim_rates else 0.0

    return metrics


def load_objective_dims(path: Path) -> tuple[list[str], dict]:
    """Load judge_validated_dimensions.json → (validated_dims, full_spec)."""
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    return list(spec.get("validated", [])), spec


def generate_improved_prompt(
    client: Anthropic,
    current_prompt: str,
    metrics: dict[str, float],
    model: str = DEFAULT_OPTIMIZER_MODEL,
) -> str:
    user_message = (
        f"Current actor system prompt:\n{current_prompt}\n\n"
        f"Evaluation metrics:\n{json.dumps(metrics, indent=2)}\n\n"
        "Identify the weakest dimensions from the metrics. "
        "Propose a revised tutor system prompt that addresses those weaknesses. "
        "Output ONLY the rewritten system prompt text, with no markdown, no commentary, "
        "and no explanation."
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0.2,
        system=_OPTIMIZER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    for block in response.content:
        if block.type == "text":
            return block.text

    raise ValueError("Optimizer returned no text block.")


def run_optimization_loop(
    input_csv: Path,
    initial_prompt: str,
    iterations: int,
    output_dir: Path,
    objective_dims: list[str] | None = None,
    objective_spec: dict | None = None,
) -> str:
    client = Anthropic()
    output_dir.mkdir(parents=True, exist_ok=True)
    current_prompt = initial_prompt

    # Resolve the optimization objective. Excluded dimensions are still scored and
    # written to each iteration JSONL; they are simply hidden from the optimizer.
    active_dims = objective_dims if objective_dims is not None else list(_JUDGE_DIMENSIONS)
    excluded_dims = [d for d in _JUDGE_DIMENSIONS if d not in active_dims]

    print("=== Optimization objective ===")
    print(f"  In objective ({len(active_dims)}): {active_dims}")
    if excluded_dims:
        dim_detail = (objective_spec or {}).get("dimensions", {})
        for d in excluded_dims:
            reasons = dim_detail.get(d, {}).get("reasons", [])
            why = ", ".join(reasons) if reasons else "not in validated set"
            print(f"  Excluded: {d} ({why})")
    else:
        print("  Excluded: none")

    judge_prompt_sha256 = prompt_sha256(_JUDGE_SYSTEM_PROMPT)
    manifest = {
        "input_csv": str(input_csv),
        "iterations": iterations,
        "objective_dims": active_dims,
        "excluded_dims": excluded_dims,
        "judge_prompt_sha256": judge_prompt_sha256,
        "objective_source": (objective_spec or {}).get("source"),
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    for i in range(iterations):
        output_path = output_dir / f"iteration_{i}_results.jsonl"
        run_evaluation(
            input_csv=input_csv,
            output_jsonl=output_path,
            actor_model=DEFAULT_ACTOR_MODEL,
            judge_model=DEFAULT_JUDGE_MODEL,
            actor_system_prompt=current_prompt,
        )

        # Metrics shown to the optimizer are restricted to the objective dimensions.
        metrics = calculate_metrics(output_path, objective_dims=active_dims)
        print(f"Iteration {i}: {metrics}")

        (output_dir / f"iteration_{i}_prompt.txt").write_text(current_prompt, encoding="utf-8")

        current_prompt = generate_improved_prompt(client, current_prompt, metrics)

    (output_dir / "optimized_prompt.txt").write_text(current_prompt, encoding="utf-8")
    return current_prompt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run iterative prompt optimization over a CSV dataset."
    )
    parser.add_argument("--input-csv", required=True, help="Path to the input CSV dataset.")
    parser.add_argument("--iterations", type=int, default=3, help="Number of optimization iterations.")
    parser.add_argument(
        "--output-dir", default="optimization_runs", help="Directory to write iteration outputs."
    )
    parser.add_argument(
        "--initial-prompt-file",
        default=None,
        help="Path to a text file whose contents will be used as the initial actor system prompt.",
    )
    parser.add_argument(
        "--objective-dims-file",
        default=None,
        help=(
            "Path to judge_validated_dimensions.json. When given, only its validated "
            "dimensions are shown to the optimizer; excluded dimensions are still scored "
            "and written to each iteration JSONL but hidden from the objective."
        ),
    )

    args = parser.parse_args()

    if args.initial_prompt_file is not None:
        initial_prompt = Path(args.initial_prompt_file).read_text(encoding="utf-8")
    else:
        initial_prompt = ACTOR_SYSTEM_PROMPT

    objective_dims = None
    objective_spec = None
    if args.objective_dims_file is not None:
        objective_dims, objective_spec = load_objective_dims(Path(args.objective_dims_file))

    run_optimization_loop(
        input_csv=Path(args.input_csv),
        initial_prompt=initial_prompt,
        iterations=args.iterations,
        output_dir=Path(args.output_dir),
        objective_dims=objective_dims,
        objective_spec=objective_spec,
    )
