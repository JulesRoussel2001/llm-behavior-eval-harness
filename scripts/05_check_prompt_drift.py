"""
Check that judge.py `_SYSTEM_PROMPT` matches the assembled prompt of the version
named in judge_prompts/FROZEN.

PASS (exit 0) if the two runtime strings are byte-identical.
FAIL (exit 1) otherwise, or if any of the following hold (addendum E):
  - FROZEN names a version whose template file does not exist,
  - the {{CALIBRATION_EXAMPLES}} marker is missing from the version file,
  - the marker occurs more than once.

The PASS/FAIL line reports the FROZEN version name and the assembled SHA-256.
Assembly is delegated to claude_behavior_eval.judge_prompt (the single source of
truth), so this check can never diverge from 03_generate_prompt.py. No API calls.
"""

import difflib
import importlib.util
import sys
from pathlib import Path

from claude_behavior_eval.judge_prompt import assemble_prompt, prompt_sha256, read_frozen

_REPO_ROOT = Path(__file__).parent.parent
_JUDGE_MODULE_PATH = _REPO_ROOT / "src" / "claude_behavior_eval" / "judge.py"


def _load_judge_prompt() -> str:
    """Import judge.py and return its `_SYSTEM_PROMPT` runtime value."""
    spec = importlib.util.spec_from_file_location("judge", _JUDGE_MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]

    src_dir = str(_REPO_ROOT / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"FAIL  Could not import judge.py: {exc}")

    if not hasattr(mod, "_SYSTEM_PROMPT"):
        sys.exit("FAIL  judge.py does not define _SYSTEM_PROMPT.")

    return mod._SYSTEM_PROMPT


def main() -> None:
    print("=== Prompt drift check ===")

    try:
        version = read_frozen()
    except FileNotFoundError as exc:
        print(f"FAIL  {exc}")
        sys.exit(1)

    try:
        expected = assemble_prompt(version)
    except (FileNotFoundError, ValueError) as exc:
        print(f"FAIL  [version={version}] {exc}")
        sys.exit(1)

    sha = prompt_sha256(expected)
    actual = _load_judge_prompt()

    if expected == actual:
        print(f"PASS  judge.py _SYSTEM_PROMPT matches FROZEN version {version} "
              f"(sha256={sha}).")
        sys.exit(0)

    print(f"FAIL  judge.py _SYSTEM_PROMPT does NOT match FROZEN version {version} "
          f"(sha256={sha}).\n")

    exp_lines = expected.splitlines()
    act_lines = actual.splitlines()
    for i, (e, a) in enumerate(zip(exp_lines, act_lines)):
        if e != a:
            print(f"  First difference at prompt line {i + 1}:")
            print(f"    expected: {e[:120]!r}")
            print(f"    actual:   {a[:120]!r}")
            break
    if len(exp_lines) != len(act_lines):
        print(f"  Length: expected {len(exp_lines)} lines, actual {len(act_lines)} lines.")

    diff = list(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile="judge.py (current)",
            tofile=f"assembled {version} (expected)",
            n=2,
        )
    )
    if diff:
        print("\n--- Unified diff (judge.py -> expected) ---")
        print("".join(diff[:80]))
        if len(diff) > 80:
            print(f"  ... ({len(diff) - 80} more diff lines not shown)")

    print("\nFix: re-run scripts/03_generate_prompt.py and paste its output into")
    print("     src/claude_behavior_eval/judge.py, then re-run this script.")
    sys.exit(1)


if __name__ == "__main__":
    main()
