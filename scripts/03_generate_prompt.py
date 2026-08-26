"""
Assemble the judge `_SYSTEM_PROMPT` for the FROZEN version and print it for pasting
into src/claude_behavior_eval/judge.py.

Reads judge_prompts/FROZEN -> version name, loads judge_prompts/<version>.txt,
inlines the calibration examples from calibration.csv at the {{CALIBRATION_EXAMPLES}}
marker (via the shared claude_behavior_eval.judge_prompt helper), prints the
`_SYSTEM_PROMPT = (...)` block, writes judge_prompts/<version>.assembled.txt, and
prints the SHA-256 of the assembled prompt.

Run from the repository root with PYTHONPATH=src. No API calls.
"""

from claude_behavior_eval.judge_prompt import (
    DEFAULT_PROMPTS_DIR,
    assemble_prompt,
    prompt_sha256,
    read_frozen,
    version_path,
)


def main() -> None:
    version = read_frozen()
    assembled = assemble_prompt(version)
    sha = prompt_sha256(assembled)

    assembled_path = DEFAULT_PROMPTS_DIR / f"{version}.assembled.txt"
    assembled_path.write_text(assembled, encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"FROZEN judge prompt version: {version}")
    print(f"Template:  {version_path(version)}")
    print(f"Assembled: {assembled_path}")
    print(f"SHA-256:   {sha}")
    print("=" * 60)
    print("COPY EVERYTHING BELOW THIS LINE into src/claude_behavior_eval/judge.py")
    print("(replacing the existing _SYSTEM_PROMPT assignment):")
    print("=" * 60 + "\n")

    # repr() emits a single valid Python string literal that evaluates back to the
    # exact assembled string, so pasting this keeps judge.py byte-identical.
    print("_SYSTEM_PROMPT = (")
    print("    " + repr(assembled))
    print(")")


if __name__ == "__main__":
    main()
