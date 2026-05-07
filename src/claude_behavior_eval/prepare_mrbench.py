from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

_CSV_FIELDNAMES = ["id", "student_question", "target_learner_level", "instruction_constraints", "expected_rubric"]

_VALIDATION_FIELDNAMES = [
    "id",
    "student_question",
    "target_learner_level",
    "instruction_constraints",
    "expected_rubric",
    "tutor_response",
    "human_mistake_identification",
    "human_mistake_location",
    "human_answer_revealing_appropriate",
    "human_providing_guidance",
    "human_actionability",
    "human_coherence",
    "human_tutor_tone",
    "human_human_likeness",
]

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
    # MRBench Tutor_Tone is categorical (Encouraging / Neutral / Offensive). We reformulate
    # as binary: encouraging=True, neutral=False. The single Offensive class is excluded from
    # quantitative splits due to insufficient support for reliable Macro-F1 evaluation.
    "tutor_tone": (
        "Is the tutor's tone encouraging rather than neutral? "
        "In this binary reformulation, encouraging=True and neutral=False; "
        "offensive responses are excluded from quantitative validation due to insufficient support."
    ),
    "human_likeness": (
        "Does the tutor's response feel natural and human-like, not robotic or formulaic?"
    ),
}

_RUBRIC_JSON = json.dumps(_RUBRIC)
_EMPTY_CONSTRAINTS_JSON = json.dumps([])

# (mrbench_annotation_key, validation_csv_column, invert_label)
# invert=True for Revealing_of_the_Answer: MRBench "Yes" means the tutor revealed the answer
# (pedagogically bad), so it maps to human_answer_revealing_appropriate="No".
# Tutor_Tone is handled separately below — it is categorical, not boolean.
_ANNOTATION_MAP: list[tuple[str, str, bool]] = [
    ("Mistake_Identification",  "human_mistake_identification",       False),
    ("Mistake_Location",        "human_mistake_location",             False),
    ("Revealing_of_the_Answer", "human_answer_revealing_appropriate", True),
    ("Providing_Guidance",      "human_providing_guidance",           False),
    ("Actionability",           "human_actionability",                False),
    ("Coherence",               "human_coherence",                    False),
    ("Tutor_Tone",              "human_tutor_tone",                   False),  # special-cased below
    ("humanlikeness",           "human_human_likeness",               False),
]

_VALID_TONE_VALUES = {"Encouraging", "Neutral", "Offensive"}


def _normalize_label(raw: str, invert: bool) -> str:
    """Map a boolean MRBench annotation value to Yes/No. Returns "" for unknown values.

    MRBench uses plain "Yes"/"No" for most dimensions, but Revealing_of_the_Answer
    uses qualified forms such as "Yes (and the answer is correct)" or
    "Yes (but the answer is incorrect)". Both qualified forms still mean the tutor
    revealed the answer (pedagogically bad), so any value starting with "Yes" is
    treated as affirmative. This is safe for all current MRBench boolean dimensions
    because no other dimension produces "Yes"-prefixed qualified values.
    """
    v = raw.strip()
    is_yes = v == "Yes" or v.startswith("Yes ")
    is_no = v == "No"
    if is_yes:
        return "No" if invert else "Yes"
    if is_no:
        return "Yes" if invert else "No"
    return ""


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


def _extract_validation_rows(item: dict, position_index: int) -> list[dict]:
    conv_id = str(item.get("conversation_id", "")).strip()
    base_id = conv_id if conv_id else f"mrbench_{position_index + 1:06d}"

    student_question = str(item.get("conversation_history", "")).strip()
    topic = str(item.get("Topic", "")).strip()
    target_learner_level = (
        topic if topic and topic != "Not Available" else "math_student"
    )

    anno_responses = item.get("anno_llm_responses") or {}
    rows: list[dict] = []
    for model_name, model_data in anno_responses.items():
        if not isinstance(model_data, dict):
            continue
        tutor_response = str(model_data.get("response", "")).strip()
        annotation = model_data.get("annotation") or {}

        row: dict = {
            "id": f"{base_id}_{model_name}",
            "student_question": student_question,
            "target_learner_level": target_learner_level,
            "instruction_constraints": _EMPTY_CONSTRAINTS_JSON,
            "expected_rubric": _RUBRIC_JSON,
            "tutor_response": tutor_response,
        }

        for src_key, dst_col, invert in _ANNOTATION_MAP:
            if src_key == "Tutor_Tone":
                # Tutor_Tone is categorical, not boolean. Store Encouraging/Neutral/Offensive
                # as-is so 01_create_splits.py can apply the Encouraging-vs-Neutral
                # binary reformulation and exclude Offensive from quantitative splits.
                raw_value = str(annotation.get(src_key, "")).strip()
                row[dst_col] = raw_value if raw_value in _VALID_TONE_VALUES else ""
            else:
                raw_value = str(annotation.get(src_key, "")).strip()
                row[dst_col] = _normalize_label(raw_value, invert)

        rows.append(row)
    return rows


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = _CSV_FIELDNAMES
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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

    validation_rows: list[dict] = []
    for idx, item in unique_pairs:
        validation_rows.extend(_extract_validation_rows(item, idx))
    _write_csv(output_dir / "judge_validation_raw.csv", validation_rows, _VALIDATION_FIELDNAMES)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert MRBench JSON into dev/test CSVs for the evaluation pipeline."
    )
    parser.add_argument("--input-json", required=True, help="Path to MRBench JSON file.")
    parser.add_argument(
        "--output-dir", default="data/processed_mrbench",
        help="Directory to write dev.csv, test.csv, split_metadata.json, and judge_validation_raw.csv."
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
