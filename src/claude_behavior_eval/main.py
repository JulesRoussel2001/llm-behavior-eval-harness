from __future__ import annotations

import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from claude_behavior_eval.config import DEFAULT_ACTOR_MODEL, DEFAULT_JUDGE_MODEL
from claude_behavior_eval.dataset import CSVDatasetLoader
from claude_behavior_eval.judge import ClaudeRubricJudge
from claude_behavior_eval.orchestrator import PipelineOrchestrator

ACTOR_SYSTEM_PROMPT = (
    "You are an expert, helpful academic AI tutor. Please respond to the student."
)


def run_evaluation(
    input_csv: Path,
    output_jsonl: Path,
    actor_model: str,
    judge_model: str,
    actor_system_prompt: str = ACTOR_SYSTEM_PROMPT,
) -> None:
    judge = ClaudeRubricJudge(model=judge_model)
    orchestrator = PipelineOrchestrator(judge=judge, actor_model=actor_model)
    loader = CSVDatasetLoader(input_csv)

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    with output_jsonl.open("w", encoding="utf-8") as out:
        for item in loader.load():
            result = orchestrator.evaluate_single_item(item, actor_system_prompt=actor_system_prompt)
            out.write(result.model_dump_json() + "\n")
            print(f"Processed {item.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run MRBench-style evaluation over a CSV dataset."
    )
    parser.add_argument("input_csv", help="Path to the input CSV dataset.")
    parser.add_argument("output_jsonl", help="Path to write the output JSONL results.")
    parser.add_argument(
        "--actor-model",
        default=DEFAULT_ACTOR_MODEL,
        help="Model ID for the actor (tutor response generator).",
    )
    parser.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help="Model ID for the rubric judge.",
    )
    parser.add_argument(
        "--actor-system-prompt-file",
        default=None,
        help="Path to a text file whose contents will be used as the actor system prompt.",
    )

    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_jsonl = Path(args.output_jsonl)

    if args.actor_system_prompt_file is not None:
        actor_system_prompt = Path(args.actor_system_prompt_file).read_text(encoding="utf-8")
    else:
        actor_system_prompt = ACTOR_SYSTEM_PROMPT

    run_evaluation(
        input_csv=input_csv,
        output_jsonl=output_jsonl,
        actor_model=args.actor_model,
        judge_model=args.judge_model,
        actor_system_prompt=actor_system_prompt,
    )
