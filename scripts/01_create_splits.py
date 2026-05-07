"""
Class-aware split construction for MRBench judge validation.

Produces three disjoint CSV files from judge_validation_raw.csv:
  calibration.csv  -  3 rows (prompt grounding examples, excluded from metrics)
  judge_dev.csv    - 20 rows (primary evaluation set)
  judge_test.csv   - 10 rows (held-out test set)

Eligibility filter (8 dimensions):
  - 7 boolean dimensions: must have Yes/No (or True/False/1/0)
  - tutor_tone: must be Encouraging or Neutral (Offensive excluded)

MRBench Tutor_Tone is categorical rather than boolean. We preserve the pedagogical
distinction between Neutral and Encouraging by reformulating tone as a binary
Encouraging-vs-Neutral metric. The single/rare Offensive class is excluded from the
quantitative split because it has insufficient support for reliable Macro-F1 evaluation.
Therefore, tutor_tone passed=True means Encouraging, and passed=False means Neutral.

Split construction uses repeated random sampling (MAX_ATTEMPTS attempts, seed 42).

Two-tier coverage strategy:
  STRONG (preferred, 25% minority threshold):
    dev  >= 5 True  and >= 5 False  per dimension
    test >= 2 True  and >= 2 False  per dimension

  FALLBACK (minimum acceptable):
    dev  >= 2 True  and >= 2 False  per dimension
    test >= 1 True  and >= 1 False  per dimension

The first split satisfying the STRONG constraint is used. If none is found in
MAX_ATTEMPTS, the first split satisfying FALLBACK is used with a printed WARNING.
If neither is found, the best-scored overall split is used with a WARNING.
"""

import csv
import random
import sys
from pathlib import Path

CALIBRATION_SIZE = 3
DEV_SIZE = 20
TEST_SIZE = 10
TOTAL_NEEDED = CALIBRATION_SIZE + DEV_SIZE + TEST_SIZE
MAX_ATTEMPTS = 10_000
SEED = 42

BOOL_COLS = [
    "human_mistake_identification",
    "human_mistake_location",
    "human_answer_revealing_appropriate",
    "human_providing_guidance",
    "human_actionability",
    "human_coherence",
    "human_human_likeness",
]
TONE_COL = "human_tutor_tone"

DIM_NAMES = [
    "mistake_identification",
    "mistake_location",
    "answer_revealing_appropriate",
    "providing_guidance",
    "actionability",
    "coherence",
    "human_likeness",
    "tutor_tone",
]

_BOOL_VALID = {"yes", "no", "true", "false", "1", "0"}


def _is_clean(row: dict) -> tuple[bool, str]:
    """Return (is_clean, exclusion_reason)."""
    for col in BOOL_COLS:
        if row[col].strip().lower() not in _BOOL_VALID:
            return False, "missing_bool"
    tone = row[TONE_COL].strip()
    if tone == "Offensive":
        return False, "offensive_tone"
    if tone not in {"Encouraging", "Neutral"}:
        return False, "missing_tone" if tone == "" else "invalid_tone"
    return True, ""


def _to_bools(row: dict) -> list[bool]:
    """Convert a clean row to a list of 8 booleans (one per DIM_NAMES)."""
    bools = [row[c].strip().lower() in {"yes", "true", "1"} for c in BOOL_COLS]
    bools.append(row[TONE_COL].strip() == "Encouraging")
    return bools


def _coverage_ok(bool_rows: list[list[bool]], min_true: int, min_false: int) -> bool:
    for d in range(len(DIM_NAMES)):
        vals = [b[d] for b in bool_rows]
        if sum(vals) < min_true or (len(vals) - sum(vals)) < min_false:
            return False
    return True


def _coverage_score(bool_rows: list[list[bool]], min_true: int, min_false: int) -> int:
    """Count (dim, class) pairs meeting minimum coverage. Max = len(DIM_NAMES) * 2."""
    score = 0
    for d in range(len(DIM_NAMES)):
        vals = [b[d] for b in bool_rows]
        if sum(vals) >= min_true:
            score += 1
        if (len(vals) - sum(vals)) >= min_false:
            score += 1
    return score


def _print_balance(label: str, bool_rows: list[list[bool]]) -> None:
    n = len(bool_rows)
    print(f"\n{label} ({n} rows):")
    print(f"  {'Dimension':<38} {'True':>6} {'False':>6}  {'Note'}")
    print(f"  {'-'*65}")
    for i, dim in enumerate(DIM_NAMES):
        vals = [b[i] for b in bool_rows]
        t = sum(vals)
        f = n - t
        minority = min(t, f)
        minority_pct = minority / n if n else 0
        if minority == 0:
            note = "WEAK — single-class"
        elif minority_pct >= 0.25:
            note = f"GOOD ≥25%  ({minority_pct:.0%})"
        else:
            note = f"OK min     ({minority_pct:.0%})"
        print(f"  {dim:<38} {t:>6} {f:>6}  {note}")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote: {path}  ({len(rows)} rows)")


def main() -> None:
    rng = random.Random(SEED)

    raw_path = Path("data/processed_mrbench/judge_validation_raw.csv")
    if not raw_path.exists():
        sys.exit(f"ERROR: {raw_path} not found. Run prepare_mrbench first.")

    with raw_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        all_rows = list(reader)

    # Classify rows
    excluded: dict[str, int] = {"missing_bool": 0, "missing_tone": 0,
                                 "offensive_tone": 0, "invalid_tone": 0}
    clean_rows: list[dict] = []
    for row in all_rows:
        ok, reason = _is_clean(row)
        if ok:
            clean_rows.append(row)
        else:
            excluded[reason] = excluded.get(reason, 0) + 1

    print(f"Total raw rows:    {len(all_rows)}")
    print(f"Clean eligible:    {len(clean_rows)}")
    print(f"Excluded: {excluded}")

    if len(clean_rows) < TOTAL_NEEDED:
        sys.exit(
            f"ERROR: Need {TOTAL_NEEDED} rows but only {len(clean_rows)} clean rows available."
        )

    clean_bools = [_to_bools(r) for r in clean_rows]

    # Report pool class balance; warn about impossible constraints
    print("\nClass balance in clean pool:")
    print(f"  {'Dimension':<38} {'True':>6} {'False':>6}")
    print(f"  {'-'*52}")
    impossible_strong: list[str] = []
    impossible_fallback: list[str] = []
    for i, dim in enumerate(DIM_NAMES):
        t = sum(b[i] for b in clean_bools)
        f = len(clean_bools) - t
        print(f"  {dim:<38} {t:>6} {f:>6}")
        if t < 5 or f < 5:
            impossible_strong.append(dim)
        if t < 2 or f < 2:
            impossible_fallback.append(dim)
    if impossible_strong:
        print(f"  NOTE: Strong (≥5) constraint unreachable for: {', '.join(impossible_strong)}")
    if impossible_fallback:
        print(f"  WARNING: Fallback (≥2) constraint unreachable for: {', '.join(impossible_fallback)}")

    # --- Repeated random sampling ---
    # Track three candidate splits:
    #   best_strong   : first split satisfying strong constraints
    #   best_fallback : first split satisfying fallback constraints
    #   best_overall  : highest combined coverage score (for last-resort)
    indices = list(range(len(clean_rows)))
    best_strong: tuple | None = None
    best_fallback: tuple | None = None
    best_overall: tuple | None = None
    best_overall_score = -1

    for attempt in range(MAX_ATTEMPTS):
        idx = indices.copy()
        rng.shuffle(idx)

        cal_i = idx[:CALIBRATION_SIZE]
        dev_i = idx[CALIBRATION_SIZE:CALIBRATION_SIZE + DEV_SIZE]
        test_i = idx[CALIBRATION_SIZE + DEV_SIZE:CALIBRATION_SIZE + DEV_SIZE + TEST_SIZE]

        dev_b = [clean_bools[i] for i in dev_i]
        test_b = [clean_bools[i] for i in test_i]

        strong_ok = _coverage_ok(dev_b, 5, 5) and _coverage_ok(test_b, 2, 2)
        fallback_ok = _coverage_ok(dev_b, 2, 2) and _coverage_ok(test_b, 1, 1)

        if strong_ok:
            best_strong = (cal_i, dev_i, test_i)
            print(f"\nStrong 25% dev coverage satisfied (attempt {attempt + 1}).")
            break

        if fallback_ok and best_fallback is None:
            best_fallback = (cal_i, dev_i, test_i)

        # Track best overall by combined coverage score
        score = (_coverage_score(dev_b, 5, 5) + _coverage_score(test_b, 2, 2))
        if score > best_overall_score:
            best_overall_score = score
            best_overall = (cal_i, dev_i, test_i)

    # Choose which split to use
    if best_strong is not None:
        selected = best_strong
        coverage_label = "STRONG — 25% minority threshold met for all feasible dimensions"
    elif best_fallback is not None:
        selected = best_fallback
        coverage_label = "FALLBACK MINIMUM — 25% threshold not achieved; minimum 2T+2F dev / 1T+1F test used"
        print(
            "\nWARNING: Strong 25% dev coverage not fully achieved. "
            "Using fallback minimum coverage split."
        )
        if impossible_strong:
            print(f"  Dimensions blocking strong coverage: {', '.join(impossible_strong)}")
    else:
        assert best_overall is not None
        selected = best_overall
        coverage_label = "BEST AVAILABLE — neither strong nor fallback constraints could be fully satisfied"
        max_possible = len(DIM_NAMES) * 4
        print(
            f"\nWARNING: No satisfying split found after {MAX_ATTEMPTS} attempts. "
            f"Using best available split (score {best_overall_score}/{max_possible})."
        )
        if impossible_fallback:
            print(f"  Impossible fallback dimensions: {', '.join(impossible_fallback)}")

    print(f"\nCoverage strategy: {coverage_label}")

    cal_i, dev_i, test_i = selected
    calibration = [clean_rows[i] for i in cal_i]
    dev = [clean_rows[i] for i in dev_i]
    test = [clean_rows[i] for i in test_i]

    out_dir = Path("data/processed_mrbench")
    _write_csv(out_dir / "calibration.csv", fieldnames, calibration)
    _write_csv(out_dir / "judge_dev.csv", fieldnames, dev)
    _write_csv(out_dir / "judge_test.csv", fieldnames, test)

    # Balance reports
    cal_b = [clean_bools[i] for i in cal_i]
    dev_b = [clean_bools[i] for i in dev_i]
    test_b = [clean_bools[i] for i in test_i]
    _print_balance("CALIBRATION SET", cal_b)
    _print_balance("DEV SET", dev_b)
    _print_balance("TEST SET", test_b)

    # Per-constraint audit
    print("\nConstraint audit:")
    any_issue = False
    for i, dim in enumerate(DIM_NAMES):
        dev_t = sum(b[i] for b in dev_b)
        dev_f = len(dev_b) - dev_t
        test_t = sum(b[i] for b in test_b)
        test_f = len(test_b) - test_t
        issues = []
        if dev_t < 5 or dev_f < 5:
            strong_miss = []
            if dev_t < 5: strong_miss.append(f"dev True={dev_t}<5")
            if dev_f < 5: strong_miss.append(f"dev False={dev_f}<5")
            issues.append("strong: " + ", ".join(strong_miss))
        if dev_t < 2 or dev_f < 2:
            if dev_t < 2: issues.append(f"FALLBACK FAIL dev True={dev_t}<2")
            if dev_f < 2: issues.append(f"FALLBACK FAIL dev False={dev_f}<2")
        if test_t < 2 or test_f < 2:
            strong_miss = []
            if test_t < 2: strong_miss.append(f"test True={test_t}<2")
            if test_f < 2: strong_miss.append(f"test False={test_f}<2")
            issues.append("strong test: " + ", ".join(strong_miss))
        if test_t < 1 or test_f < 1:
            if test_t < 1: issues.append(f"FALLBACK FAIL test True={test_t}<1")
            if test_f < 1: issues.append(f"FALLBACK FAIL test False={test_f}<1")

        if issues:
            any_issue = True
            print(f"  NOTE  {dim}: {'; '.join(issues)}")
        else:
            print(f"  OK    {dim}")

    if not any_issue:
        print("\nAll dimensions satisfy the strong 25% threshold in dev and test sets.")


if __name__ == "__main__":
    main()
