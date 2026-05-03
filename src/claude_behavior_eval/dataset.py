from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Generator

from claude_behavior_eval.schemas import DatasetItem


class CSVDatasetLoader:
    def __init__(self, filepath: str | Path) -> None:
        self._filepath = Path(filepath)

    def load(self) -> Generator[DatasetItem, None, None]:
        with self._filepath.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_id = row.get("id", "<unknown>")

                raw_constraints = row.get("instruction_constraints", "").strip()
                if raw_constraints:
                    try:
                        instruction_constraints = json.loads(raw_constraints)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Row '{row_id}': malformed JSON in 'instruction_constraints': {exc}"
                        ) from exc
                else:
                    instruction_constraints = []

                raw_rubric = row.get("expected_rubric", "").strip()
                if raw_rubric:
                    try:
                        expected_rubric = json.loads(raw_rubric)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Row '{row_id}': malformed JSON in 'expected_rubric': {exc}"
                        ) from exc
                else:
                    expected_rubric = {}

                yield DatasetItem(
                    id=row["id"],
                    student_question=row["student_question"],
                    target_learner_level=row["target_learner_level"],
                    instruction_constraints=instruction_constraints,
                    expected_rubric=expected_rubric,
                )
