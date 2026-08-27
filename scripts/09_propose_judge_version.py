"""
Propose the next judge prompt version from DEV evidence. ONE Anthropic API call.

This script makes an API call and is intended to be run BY A HUMAN during judge
development — it is not part of any automated/no-API flow. It never touches the
frozen artifacts: it refuses paths pointing at FROZEN, calibration.csv, judge.py,
or any judge_test_* file, and it never writes to FROZEN or judge.py.

Inputs (CLI):
  --current        judge_prompts/vN.txt          (the version to refine)
  --stats          stats_dev_vN.md               (DEV statistics)
  --disagreements  disagreements_vN.md           (DEV disagreement report)
  --out            judge_prompts/vN+1.candidate.txt
  --rationale      judge_prompts/vN+1.rationale.md
  --model          <model id>

The model returns the full candidate prompt, a separator line, then a rationale.
The script splits those into --out / --rationale, and verifies that the three
preserved sections (opening framing, the {{CALIBRATION_EXAMPLES}} marker, and the
output/tool instructions) are byte-identical to --current. On any failure it writes
the candidate to "<out>.REJECTED" and exits non-zero.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from anthropic import Anthropic

from claude_behavior_eval.judge_prompt import CALIBRATION_MARKER

# Anchors delimiting the editable middle. The opening framing is everything before
# _RUBRIC_ANCHOR; the output/tool instructions are everything from _INSTRUCTIONS_ANCHOR.
_RUBRIC_ANCHOR = "### RUBRIC DIMENSIONS"
_INSTRUCTIONS_ANCHOR = "### INSTRUCTIONS"

RATIONALE_SEPARATOR = "=== RATIONALE ==="

SYSTEM_PROMPT = (
    "You are refining a frozen rubric-based pedagogical judge prompt using only "
    "DEV-split evidence. All of the following constraints are mandatory:\n"
    "- Preserve the opening framing, the {{CALIBRATION_EXAMPLES}} marker, and the "
    "output/tool instructions BYTE-FOR-BYTE. Do not alter, reword, add to, remove, "
    "or reorder a single character of these three sections.\n"
    "- Edit ONLY rubric definitions and semantic clarifications.\n"
    "- Every edit must be justified by a repeated disagreement pattern (>= 3 rows) "
    "visible in the disagreements report.\n"
    "- Do not insert item ids, excerpts, or verbatim DEV text into the prompt.\n"
    "- Do not change what a human label means.\n"
    "- A metric target (e.g. 'raise recall') is NOT a justification.\n\n"
    "Output format, with no preamble and no code fences:\n"
    "1. The COMPLETE candidate prompt, starting at its very first character, including "
    "the unchanged preserved sections and the {{CALIBRATION_EXAMPLES}} marker in place.\n"
    f"2. A line containing exactly: {RATIONALE_SEPARATOR}\n"
    "3. The rationale: for EACH edit list the dimension, the direction (FP or FN), the "
    "row count, 2-3 example item ids, and the general rule you inferred."
)

_FORBIDDEN_NAMES = {"frozen", "judge.py"}


def assert_safe_paths(paths: list[Path]) -> None:
    """Refuse any path pointing at a frozen/leakage-sensitive artifact.

    Raises ValueError if a path's basename is FROZEN or judge.py, contains
    'calibration', or starts with 'judge_test'.
    """
    for p in paths:
        name = Path(p).name.lower()
        if name in _FORBIDDEN_NAMES:
            raise ValueError(f"Refusing to use forbidden path: {p}")
        if "calibration" in name:
            raise ValueError(f"Refusing to read/write calibration data: {p}")
        if name.startswith("judge_test"):
            raise ValueError(f"Refusing to touch held-out test data: {p}")


def preserved_sections(template: str) -> tuple[str, str]:
    """Return (opening_framing, output_instructions) extracted from `template`."""
    if _RUBRIC_ANCHOR not in template:
        raise ValueError(f"Current prompt is missing the {_RUBRIC_ANCHOR!r} anchor.")
    if _INSTRUCTIONS_ANCHOR not in template:
        raise ValueError(f"Current prompt is missing the {_INSTRUCTIONS_ANCHOR!r} anchor.")
    if template.count(CALIBRATION_MARKER) != 1:
        raise ValueError(
            f"Current prompt must contain {CALIBRATION_MARKER!r} exactly once."
        )
    opening = template[: template.index(_RUBRIC_ANCHOR)]
    instructions = template[template.index(_INSTRUCTIONS_ANCHOR):]
    return opening, instructions


def verify_preserved(current: str, candidate: str) -> list[str]:
    """Return a list of preserved-section violations ([] means the candidate is valid)."""
    opening, instructions = preserved_sections(current)
    problems: list[str] = []
    if not candidate.startswith(opening):
        problems.append("opening framing was modified")
    if not candidate.endswith(instructions):
        problems.append("output/tool instructions were modified")
    if candidate.count(CALIBRATION_MARKER) != 1:
        problems.append("{{CALIBRATION_EXAMPLES}} marker not preserved exactly once")
    return problems


def split_output(model_text: str) -> tuple[str, str]:
    """Split the model output into (candidate_prompt, rationale) at the separator."""
    if RATIONALE_SEPARATOR not in model_text:
        raise ValueError(f"Model output is missing the {RATIONALE_SEPARATOR!r} separator.")
    idx = model_text.index(RATIONALE_SEPARATOR)
    candidate = model_text[:idx].rstrip("\n")
    rationale = model_text[idx + len(RATIONALE_SEPARATOR):].lstrip("\n")
    return candidate, rationale


def build_user_message(current: str, stats: str, disagreements: str) -> str:
    return (
        "CURRENT JUDGE PROMPT (refine this):\n"
        "-----8<----- BEGIN CURRENT PROMPT -----8<-----\n"
        f"{current}\n"
        "-----8<----- END CURRENT PROMPT -----8<-----\n\n"
        "DEV STATISTICS:\n"
        f"{stats}\n\n"
        "DEV DISAGREEMENTS:\n"
        f"{disagreements}\n"
    )


def propose(client: Anthropic, model: str, current: str, stats: str, disagreements: str) -> str:
    """One streamed messages call. Returns the model's raw text output."""
    with client.messages.stream(
        model=model,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(current, stats, disagreements)}],
    ) as stream:
        response = stream.get_final_message()
    for block in response.content:
        if block.type == "text":
            return block.text
    raise ValueError(
        f"Proposer returned no text block. stop_reason={response.stop_reason!r}, "
        f"block types={[b.type for b in response.content]}"
    )


def _rejected_path(out: Path) -> Path:
    return Path(str(out) + ".REJECTED")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Propose the next judge prompt version from DEV evidence (one API call)."
    )
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--disagreements", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--rationale", required=True, type=Path)
    parser.add_argument("--model", required=True)
    args = parser.parse_args(argv)

    # Refuse any frozen/leakage-sensitive path before doing anything else.
    try:
        assert_safe_paths([args.current, args.stats, args.disagreements, args.out, args.rationale])
    except ValueError as exc:
        sys.exit(f"ERROR: {exc}")

    current = args.current.read_text(encoding="utf-8")
    stats = args.stats.read_text(encoding="utf-8")
    disagreements = args.disagreements.read_text(encoding="utf-8")

    # Fail fast if the current prompt is malformed.
    preserved_sections(current)

    client = Anthropic()
    model_text = propose(client, args.model, current, stats, disagreements)

    try:
        candidate, rationale = split_output(model_text)
    except ValueError as exc:
        rejected = _rejected_path(args.out)
        rejected.write_text(model_text, encoding="utf-8")
        sys.exit(f"REJECTED: {exc}\nRaw model output written to {rejected}")

    problems = verify_preserved(current, candidate)
    if problems:
        rejected = _rejected_path(args.out)
        rejected.write_text(candidate, encoding="utf-8")
        sys.exit(
            "REJECTED: preserved sections were not byte-identical:\n  - "
            + "\n  - ".join(problems)
            + f"\nCandidate written to {rejected} (NOT to {args.out})."
        )

    args.out.write_text(candidate, encoding="utf-8")
    args.rationale.write_text(rationale + "\n", encoding="utf-8")
    print(f"Wrote candidate:  {args.out}")
    print(f"Wrote rationale:  {args.rationale}")
    print("Preserved sections verified byte-identical. Review before freezing.")


if __name__ == "__main__":
    main()
