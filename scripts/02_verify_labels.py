"""
Data quality verification for judge_validation_raw.csv.

Prints:
  - Total raw rows
  - Raw Revealing_of_the_Answer distribution from MRBench JSON (to explain the normalization)
  - Per-column value distributions for all 8 processed dimensions
  - human_tutor_tone distribution (raw categorical) and after binary mapping
  - Eligible row counts and exclusion breakdown

Run after prepare_mrbench to verify labels before creating splits.

Normalization note for Revealing_of_the_Answer:
  MRBench uses qualified "Yes (...)" labels rather than plain "Yes".
  Raw labels starting with "Yes" are treated as answer-revealing and inverted to
  human_answer_revealing_appropriate="No" (i.e., not pedagogically appropriate).
  Raw "No" (tutor did not reveal) is inverted to human_answer_revealing_appropriate="Yes".
"""

import csv
import json
from collections import Counter
from pathlib import Path

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

_BOOL_VALID = {"yes", "no", "true", "false", "1", "0"}

RAW_JSON_PATH = Path("data/raw_mrbench/MRBench/MRBench_V2.json")
PROCESSED_CSV_PATH = Path("data/processed_mrbench/judge_validation_raw.csv")


def _is_bool_clean(val: str) -> bool:
    return val.strip().lower() in _BOOL_VALID


def _raw_revealing_distribution() -> dict[str, int]:
    """Read raw Revealing_of_the_Answer values directly from the MRBench JSON."""
    if not RAW_JSON_PATH.exists():
        return {}
    with RAW_JSON_PATH.open(encoding="utf-8") as f:
        items = json.load(f)
    counter: Counter = Counter()
    for item in items:
        for model_data in (item.get("anno_llm_responses") or {}).values():
            if isinstance(model_data, dict):
                ann = model_data.get("annotation") or {}
                val = str(ann.get("Revealing_of_the_Answer", "")).strip()
                if val:
                    counter[val] += 1
    return dict(counter)


def main() -> None:
    if not PROCESSED_CSV_PATH.exists():
        raise SystemExit(
            f"ERROR: {PROCESSED_CSV_PATH} not found. Run prepare_mrbench first."
        )

    with PROCESSED_CSV_PATH.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Total processed rows: {len(rows)}")

    # --- Raw Revealing_of_the_Answer from JSON ---
    raw_revealing = _raw_revealing_distribution()
    if raw_revealing:
        print("\n" + "=" * 60)
        print("RAW Revealing_of_the_Answer VALUES (from MRBench JSON)")
        print("=" * 60)
        print("  Mapping: 'No' → appropriate → 'Yes' after inversion")
        print("  Mapping: 'Yes (...)' → revealing → 'No' after inversion")
        print()
        for val, cnt in sorted(raw_revealing.items(), key=lambda x: -x[1]):
            mapping = "→ human='No'"  if val.startswith("Yes") else "→ human='Yes'"
            print(f"  {val!r:<45} {cnt:>6}  {mapping}")
    else:
        print(f"\n(Raw JSON not found at {RAW_JSON_PATH} — skipping raw distribution)")

    # --- Boolean dimensions ---
    print("\n" + "=" * 60)
    print("PROCESSED BOOLEAN DIMENSION DISTRIBUTIONS")
    print("=" * 60)
    for col in BOOL_COLS:
        dim = col.replace("human_", "")
        counter = Counter(r[col] for r in rows)
        clean = sum(v for k, v in counter.items() if k.strip().lower() in _BOOL_VALID)
        print(f"\n  {dim}:")
        for val, cnt in sorted(counter.items(), key=lambda x: -x[1]):
            label = "(clean)" if val.strip().lower() in _BOOL_VALID else "(excluded)"
            print(f"    {val!r:<20} {cnt:>6}  {label}")
        print(f"    {'-- clean total --':<20} {clean:>6}")

    # --- Tutor tone ---
    print("\n" + "=" * 60)
    print("TUTOR TONE DISTRIBUTION")
    print("=" * 60)
    tone_counter = Counter(r[TONE_COL] for r in rows)
    print("\n  Raw categorical values (stored as-is in processed CSV):")
    for val, cnt in sorted(tone_counter.items(), key=lambda x: -x[1]):
        print(f"    {val!r:<20} {cnt:>6}")

    encouraging = tone_counter.get("Encouraging", 0)
    neutral = tone_counter.get("Neutral", 0)
    offensive = tone_counter.get("Offensive", 0)
    empty = tone_counter.get("", 0)
    other = len(rows) - encouraging - neutral - offensive - empty

    print("\n  After binary mapping (Encouraging=True, Neutral=False, Offensive=excluded):")
    print(f"    True  (Encouraging): {encouraging:>6}")
    print(f"    False (Neutral):     {neutral:>6}")
    print(f"    Excluded (Offensive):{offensive:>6}")
    print(f"    Missing (empty):     {empty:>6}")
    if other:
        print(f"    Invalid (other):     {other:>6}")

    # --- Eligibility breakdown ---
    print("\n" + "=" * 60)
    print("ELIGIBILITY ANALYSIS")
    print("=" * 60)
    excluded: dict[str, int] = {"missing_bool": 0, "missing_tone": 0,
                                 "offensive_tone": 0, "invalid_tone": 0}
    clean_count = 0
    for row in rows:
        bool_ok = all(_is_bool_clean(row[c]) for c in BOOL_COLS)
        tone = row[TONE_COL].strip()
        if not bool_ok:
            excluded["missing_bool"] += 1
        elif tone == "Offensive":
            excluded["offensive_tone"] += 1
        elif tone not in {"Encouraging", "Neutral"}:
            if tone == "":
                excluded["missing_tone"] += 1
            else:
                excluded["invalid_tone"] += 1
        else:
            clean_count += 1

    print(f"\n  Clean eligible rows: {clean_count}")
    print(f"  Excluded breakdown:")
    for reason, cnt in excluded.items():
        print(f"    {reason:<25} {cnt:>6}")
    print(f"  Total excluded: {len(rows) - clean_count}")

    # Note: judge splits are now sampled at the conversation level (80 conversations
    # split 40/40) with per-row filtering applied inside 01_create_splits.py, so
    # there is no fixed clean-row minimum here. See judge_split_manifest.json for the
    # actual before/after/excluded row counts per split.
    print(f"\n  Clean rows available for conversation-level splits: {clean_count}")

    # --- Class balance for answer_revealing_appropriate specifically ---
    ara_yes = sum(1 for r in rows if r["human_answer_revealing_appropriate"] == "Yes")
    ara_no = sum(1 for r in rows if r["human_answer_revealing_appropriate"] == "No")
    ara_empty = sum(1 for r in rows if r["human_answer_revealing_appropriate"] == "")
    print(f"\n  answer_revealing_appropriate in processed CSV:")
    print(f"    Yes (appropriate, tutor did not reveal): {ara_yes:>6}")
    print(f"    No  (not appropriate, tutor revealed):   {ara_no:>6}")
    print(f"    Empty (unmapped / not clean):             {ara_empty:>6}")
    if ara_no == 0:
        print("  WARNING: 0 'No' values — the normalizer may not be recognizing qualified 'Yes' labels.")
    else:
        print("  OK: Both 'Yes' and 'No' classes present.")


if __name__ == "__main__":
    main()
