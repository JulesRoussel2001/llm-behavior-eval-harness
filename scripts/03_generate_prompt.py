"""
Generate the _SYSTEM_PROMPT string to paste into src/claude_behavior_eval/judge.py.

Reads calibration.csv (3 rows) and embeds them as grounding examples.
Run after 01_create_splits.py.
"""

import csv
import json

# All 8 MRBench-inspired dimensions.
# tutor_tone uses a binary Encouraging-vs-Neutral reformulation:
#   Encouraging=True (active encouragement), Neutral=False (not encouraging).
#   Offensive examples are excluded from splits due to insufficient support.
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
    """Convert a human annotation label to True/False string.

    Handles both boolean dimensions (Yes/No/True/False/1/0) and the
    binary tone reformulation (Encouraging=True, Neutral=False).
    """
    v = (value or "").strip()
    # Tone labels (checked first, distinct from Yes/No)
    if v == "Encouraging":
        return "True"
    if v == "Neutral":
        return "False"
    # Boolean labels
    v_lower = v.lower()
    if v_lower in {"yes", "true", "1"}:
        return "True"
    if v_lower in {"no", "false", "0"}:
        return "False"
    return "N/A"


def main() -> None:
    lines = [
        '_SYSTEM_PROMPT = (',
        '    "You are a frozen rubric-based pedagogical judge evaluating AI tutor responses "',
        '    "under the MRBench academic-tutoring taxonomy. "',
        '    "You are a validated proxy evaluator, not an objective ground truth: your scores "',
        '    "approximate expert human judgment and should be interpreted accordingly.\\n\\n"',
        '',
        '    "### RUBRIC DIMENSIONS\\n"',
        '    "- mistake_identification: whether the tutor identifies the student\'s mistake or misconception.\\n"',
        '    "- mistake_location: whether the tutor locates where the mistake occurs.\\n"',
        '    "- answer_revealing_appropriate: whether the tutor avoids giving away the final answer too directly.\\n"',
        '    "- providing_guidance: whether the tutor gives useful learning guidance.\\n"',
        '    "- actionability: whether the tutor gives a concrete next step.\\n"',
        '    "- coherence: whether the response is logically clear and consistent.\\n"',
        # tutor_tone uses a binary Encouraging-vs-Neutral reformulation
        '    "- tutor_tone: whether the tutor\'s tone is encouraging rather than neutral. '
        'For this binary MRBench reformulation, Encouraging=True and Neutral=False; '
        'Offensive examples are excluded from quantitative validation due to insufficient support.\\n"',
        '    "- human_likeness: whether the response sounds like a natural human tutor.\\n\\n"',
        '',
        '    "### IMPORTANT NOTE ON tutor_tone\\n"',
        '    "For tutor_tone, passed=True means the response is encouraging; '
        'passed=False means the response is neutral/not encouraging. '
        'Do not interpret False as offensive or unsafe — '
        'False simply means the tone is measured/neutral rather than actively encouraging.\\n\\n"',
        '',
        '    "### CALIBRATION EXAMPLES: REAL MRBENCH GOLD LABELS\\n"',
        '    "These examples are excluded from validation and test sets to avoid leakage. "',
        '    "Use them only to align grading boundaries with MRBench human annotations.\\n\\n"',
    ]

    with open("data/processed_mrbench/calibration.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            q = clean_text(row.get("student_question", ""))
            t = clean_text(row.get("tutor_response", ""))
            label_text = "; ".join(
                f"{dim}={label_to_bool(row.get(col, ''))}"
                for dim, col in DIMENSIONS
            )
            example = (
                f"EXAMPLE {i}:\\n"
                f"Student/context: {q}\\n"
                f"Tutor response: {t}\\n"
                f"Gold labels: {label_text}\\n\\n"
            )
            lines.append(f"    {json.dumps(example)}")

    lines.extend([
        '',
        '    "### INSTRUCTIONS\\n"',
        '    "Evaluate the generated tutor response by calling the mrbench_evaluation tool. "',
        '    "For each rubric dimension, return a structured judgment with two fields:\\n"',
        '    "1. reason: one concise sentence, maximum 25 words, describing the observable success or failure.\\n"',
        '    "2. passed: the final boolean score.\\n"',
        '    "Do not provide chain-of-thought. Do not explain your reasoning step by step. "',
        '    "Only provide short observable diagnostic reasons inside the structured tool output."',
        ')',
    ])

    print("\n" + "=" * 50)
    print("COPY EVERYTHING BELOW THIS LINE:")
    print("=" * 50 + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
