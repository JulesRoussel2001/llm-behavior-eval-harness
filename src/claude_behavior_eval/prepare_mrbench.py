from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

_CSV_FIELDNAMES = ["id", "student_question", "target_learner_level", "instruction_constraints", "expected_rubric"]

_RUBRIC: dict[str, str] = {
    "mistake_identification": (
        "Does the tutor correctly identify whether the student made a mistake?"
    ),
    "mistake_location": (
        "Does the tutor correctly locate where in the student's reasoning the mistake occurred?"
    ),
    "answer_revealing_appropriate": (
        "Is the tutor's level of answer revelation appropriate given pedagogical goals?"
    ),
    "providing_guidance": (
        "Does the tutor provide actionable guidance to help the student improve?"
    ),
    "actionability": (
        "Are the tutor's suggestions specific and actionable for the student?"
    ),
    "coherence": (
        "Is the tutor's response coherent and well-structured?"
    ),
    "tutor_tone": (
        "Is the tutor's tone appropriate — neutral or encouraging, not discouraging?"
    ),
    "human_likeness": (
        "Does the tutor's response feel natural and human-like, not robotic or formulaic?"
    ),
}

_RUBRIC_JSON = json.dumps(_RUBRIC)
_EMPTY_CONSTRAINTS_JSON = json.dumps([])


def _extract_row(item: dict, position_index: int) -> dict:
    conv_id = str(item.get("conversation_id", "")).strip()
    row_id = conv_id if conv_id else f"mrbench_{position_index + 1:06d}"

    student_question = str(item.get("conversation_history", "")).strip()

    topic = str(item.get("Topic", "")).strip()
    target_learner_level = (
        topic if topic and topic != "Not Available" else "math_student"
    )

    return {
        "id": row_id,
        "student_question": student_question,
        "target_learner_level": target_learner_level,
        "instruction_constraints": _EMPTY_CONSTRAINTS_JSON,
        "expected_rubric": _RUBRIC_JSON,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def prepare_mrbench_csvs(
    input_json: Path,
    output_dir: Path,
    dev_ratio: float = 0.7,
    seed: int = 42,
) -> None:
    with input_json.open(encoding="utf-8") as f:
        raw_items: list[dict] = json.load(f)

    # Deduplicate by resolved row id, keeping the first occurrence.
    seen_ids: set[str] = set()
    unique_pairs: list[tuple[int, dict]] = []
    for position_index, item in enumerate(raw_items):
        conv_id = str(item.get("conversation_id", "")).strip()
        row_id = conv_id if conv_id else f"mrbench_{position_index + 1:06d}"
        if row_id not in seen_ids:
            seen_ids.add(row_id)
            unique_pairs.append((position_index, item))

    rows = [_extract_row(item, idx) for idx, item in unique_pairs]

    random.Random(seed).shuffle(rows)

    split_idx = int(len(rows) * dev_ratio)
    dev_rows = rows[:split_idx]
    test_rows = rows[split_idx:]

    output_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(output_dir / "dev.csv", dev_rows)
    _write_csv(output_dir / "test.csv", test_rows)

    metadata = {
        "input_json": str(input_json),
        "total_rows": len(rows),
        "dev_rows": len(dev_rows),
        "test_rows": len(test_rows),
        "dev_ratio": dev_ratio,
        "seed": seed,
    }
    with (output_dir / "split_metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert MRBench JSON into dev/test CSVs for the evaluation pipeline."
    )
    parser.add_argument("--input-json", required=True, help="Path to MRBench JSON file.")
    parser.add_argument(
        "--output-dir", default="data/processed_mrbench",
        help="Directory to write dev.csv, test.csv, and split_metadata.json."
    )
    parser.add_argument("--dev-ratio", type=float, default=0.7, help="Fraction of rows for dev set.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")

    args = parser.parse_args()

    prepare_mrbench_csvs(
        input_json=Path(args.input_json),
        output_dir=Path(args.output_dir),
        dev_ratio=args.dev_ratio,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
