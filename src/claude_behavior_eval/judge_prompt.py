"""Single source of truth for assembling the judge system prompt.

The judge `_SYSTEM_PROMPT` is a versioned artifact: the editable template lives in
`judge_prompts/<version>.txt` with a `{{CALIBRATION_EXAMPLES}}` marker where the
grounding examples (generated from `calibration.csv`) are inlined. This module is
the ONLY place that assembles a prompt from a template + calibration examples, so
`03_generate_prompt.py`, `05_check_prompt_drift.py`, and `validate_judge` all agree
byte-for-byte.

Note on escaping: the calibration-examples block embeds literal backslash-n escape
sequences (``\\n``), not real newlines — matching exactly what is stored in
`judge.py`'s `_SYSTEM_PROMPT`. Only the section headers use real newlines, and
those live in the template file.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

CALIBRATION_MARKER = "{{CALIBRATION_EXAMPLES}}"

# Defaults are resolved relative to the current working directory (the repo root),
# matching the convention used by every other script in this project.
DEFAULT_PROMPTS_DIR = Path("judge_prompts")
DEFAULT_CALIBRATION_CSV = Path("data/processed_mrbench/calibration.csv")
FROZEN_FILENAME = "FROZEN"

# The 8 MRBench dimensions and their human-label columns, in prompt order.
DIMENSIONS = [
    ("mistake_identification",       "human_mistake_identification"),
    ("mistake_location",             "human_mistake_location"),
    ("answer_revealing_appropriate", "human_answer_revealing_appropriate"),
    ("providing_guidance",           "human_providing_guidance"),
    ("actionability",                "human_actionability"),
    ("coherence",                    "human_coherence"),
    ("tutor_tone",                   "human_tutor_tone"),
    ("human_likeness",               "human_human_likeness"),
]


def clean_text(value: str, limit: int = 900) -> str:
    value = (value or "").replace("\n", " ").replace("\r", " ").strip()
    if len(value) > limit:
        value = value[:limit] + "..."
    return value


def label_to_bool(value: str) -> str:
    """Convert a human annotation label to a True/False string.

    Handles boolean dimensions (Yes/No/True/False/1/0) and the binary tone
    reformulation (Encouraging=True, Neutral=False).
    """
    v = (value or "").strip()
    if v == "Encouraging":
        return "True"
    if v == "Neutral":
        return "False"
    v_lower = v.lower()
    if v_lower in {"yes", "true", "1"}:
        return "True"
    if v_lower in {"no", "false", "0"}:
        return "False"
    return "N/A"


def build_calibration_examples(cal_path: Path = DEFAULT_CALIBRATION_CSV) -> str:
    """Build the runtime calibration-examples block from calibration.csv.

    The returned string is byte-identical to the examples block embedded in
    `judge.py`'s `_SYSTEM_PROMPT` (literal ``\\n`` escapes, not real newlines).
    """
    parts: list[str] = []
    with Path(cal_path).open(encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), 1):
            q = clean_text(row.get("student_question", ""))
            t = clean_text(row.get("tutor_response", ""))
            label_text = "; ".join(
                f"{dim}={label_to_bool(row.get(col, ''))}"
                for dim, col in DIMENSIONS
            )
            parts.append(
                f"EXAMPLE {i}:\\n"
                f"Student/context: {q}\\n"
                f"Tutor response: {t}\\n"
                f"Gold labels: {label_text}\\n\\n"
            )
    return "".join(parts)


def version_path(version: str, prompts_dir: Path = DEFAULT_PROMPTS_DIR) -> Path:
    return Path(prompts_dir) / f"{version}.txt"


def assemble_prompt(
    version: str,
    prompts_dir: Path = DEFAULT_PROMPTS_DIR,
    cal_path: Path = DEFAULT_CALIBRATION_CSV,
) -> str:
    """Assemble the full `_SYSTEM_PROMPT` string for `version`.

    Raises FileNotFoundError if the version file is missing, and ValueError if the
    calibration marker is missing or appears more than once.
    """
    template_path = version_path(version, prompts_dir)
    if not template_path.exists():
        raise FileNotFoundError(f"Judge prompt version file not found: {template_path}")
    template = template_path.read_text(encoding="utf-8")

    count = template.count(CALIBRATION_MARKER)
    if count == 0:
        raise ValueError(
            f"Calibration marker {CALIBRATION_MARKER!r} missing from {template_path}."
        )
    if count > 1:
        raise ValueError(
            f"Calibration marker {CALIBRATION_MARKER!r} occurs {count} times in "
            f"{template_path} (expected exactly 1)."
        )

    examples = build_calibration_examples(cal_path)
    return template.replace(CALIBRATION_MARKER, examples)


def prompt_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_frozen(prompts_dir: Path = DEFAULT_PROMPTS_DIR) -> str:
    """Return the version name recorded in judge_prompts/FROZEN (stripped)."""
    frozen_path = Path(prompts_dir) / FROZEN_FILENAME
    if not frozen_path.exists():
        raise FileNotFoundError(f"FROZEN pointer not found: {frozen_path}")
    return frozen_path.read_text(encoding="utf-8").strip()
