"""
Check that judge.py _SYSTEM_PROMPT matches what 03_generate_prompt.py would produce
from the current calibration.csv.

Exits 0 if they match.
Exits 1 if they differ, printing a unified diff of the two runtime string values.

Run after 01_create_splits.py (Step 3) and before any API-backed steps (Step 8+).
If drift is detected, re-run 03_generate_prompt.py (Step 4) and paste its output
into judge.py, then rerun this script to confirm.
"""

import contextlib
import difflib
import importlib.util
import io
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_GENERATE_SCRIPT = Path(__file__).parent / "03_generate_prompt.py"
_JUDGE_MODULE_PATH = _REPO_ROOT / "src" / "claude_behavior_eval" / "judge.py"


def _build_expected_prompt() -> str:
    """
    Run 03_generate_prompt.py and exec its _SYSTEM_PROMPT = (...) output to get
    the runtime string value.  This is the source of truth from calibration.csv.
    """
    spec = importlib.util.spec_from_file_location("generate_prompt", _GENERATE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main()
    source_output = buf.getvalue()

    match = re.search(r"(_SYSTEM_PROMPT = \(.*?\n\))", source_output, re.DOTALL)
    if not match:
        sys.exit("ERROR: Could not find _SYSTEM_PROMPT block in 03_generate_prompt.py output.")

    ns: dict = {}
    try:
        exec(match.group(1), ns)  # noqa: S102
    except SyntaxError as exc:
        sys.exit(f"ERROR: SyntaxError evaluating generated _SYSTEM_PROMPT: {exc}")

    if "_SYSTEM_PROMPT" not in ns:
        sys.exit("ERROR: exec did not produce _SYSTEM_PROMPT in namespace.")

    return ns["_SYSTEM_PROMPT"]


def _load_judge_prompt() -> str:
    """Import judge.py and return its _SYSTEM_PROMPT runtime value."""
    spec = importlib.util.spec_from_file_location("judge", _JUDGE_MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]

    # judge.py imports from claude_behavior_eval — ensure src/ is on sys.path
    src_dir = str(_REPO_ROOT / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception as exc:
        sys.exit(f"ERROR: Could not import judge.py: {exc}")

    if not hasattr(mod, "_SYSTEM_PROMPT"):
        sys.exit("ERROR: judge.py does not define _SYSTEM_PROMPT.")

    return mod._SYSTEM_PROMPT


def _diff_lines(a: str, b: str, label_a: str, label_b: str) -> list[str]:
    return list(
        difflib.unified_diff(
            a.splitlines(keepends=True),
            b.splitlines(keepends=True),
            fromfile=label_a,
            tofile=label_b,
            n=2,
        )
    )


def main() -> None:
    print("=== Prompt drift check ===")
    print(f"  calibration.csv  →  03_generate_prompt.py  →  expected prompt")
    print(f"  judge.py _SYSTEM_PROMPT                    →  actual prompt")
    print()

    expected = _build_expected_prompt()
    actual = _load_judge_prompt()

    if expected == actual:
        print("OK  judge.py _SYSTEM_PROMPT is in sync with calibration.csv.")
        sys.exit(0)

    # --- Drift detected ---
    print("DRIFT DETECTED  judge.py _SYSTEM_PROMPT does not match calibration.csv.\n")

    # Summarise where the difference is
    exp_lines = expected.splitlines()
    act_lines = actual.splitlines()

    # Find first differing line for a quick summary
    for i, (e, a) in enumerate(zip(exp_lines, act_lines)):
        if e != a:
            print(f"  First difference at prompt line {i + 1}:")
            print(f"    expected: {e[:120]!r}")
            print(f"    actual:   {a[:120]!r}")
            break
    if len(exp_lines) != len(act_lines):
        print(f"  Length: expected {len(exp_lines)} lines, actual {len(act_lines)} lines.")

    print()
    diff = _diff_lines(actual, expected,
                       "judge.py (current)", "calibration.csv (expected)")
    if diff:
        print("--- Unified diff (judge.py → expected) ---")
        # Cap output so the terminal doesn't flood
        shown = diff[:80]
        print("".join(shown))
        if len(diff) > 80:
            print(f"  ... ({len(diff) - 80} more diff lines not shown)")

    print()
    print("Fix: re-run scripts/03_generate_prompt.py and paste the output into")
    print("     src/claude_behavior_eval/judge.py, then re-run this script.")
    sys.exit(1)


if __name__ == "__main__":
    main()
