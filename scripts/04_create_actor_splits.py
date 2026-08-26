"""
Create reproducible Actor splits for prompt optimization and evaluation.

Source pool (conversation-level, question-only):
  data/processed_mrbench/dev.csv   (136 rows)
  data/processed_mrbench/test.csv  (59 rows)
  Combined: 195 conversations from MRBench V2.

Leakage guard:
  Every conversation used by the Judge validation splits — calibration, judge_dev,
  and judge_test — is excluded from the Actor pool. The forbidden conversation ids
  are read from data/processed_mrbench/judge_split_manifest.json (written by
  scripts/01_create_splits.py). With calibration (3) + judge_dev (40) + judge_test
  (40) = 83 conversations excluded, the eligible Actor pool is ≈112 conversations.

Output files — all question-only, no tutor_response or human_* labels:
  actor_train.csv  — the remaining eligible conversations, capped at FULL_TRAIN_CAP (55)
  actor_test.csv   — FULL_TEST_SIZE (60) held-out conversations

  The previous mini splits (actor_mini_train / actor_mini_test) are no longer
  generated; the pipeline consumes actor_train.csv / actor_test.csv directly.

Split construction:
  Eligible conversations are shuffled once with a fixed seed (SEED=42). The first
  FULL_TEST_SIZE become actor_test; the next FULL_TRAIN_CAP (or fewer, if the pool
  is smaller) become actor_train. Train and test are therefore disjoint by
  construction and disjoint from all judge splits (forbidden ids are removed first).

Schema (all Actor files):
  id, student_question, target_learner_level, instruction_constraints, expected_rubric
"""

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FULL_TEST_SIZE = 60
FULL_TRAIN_CAP = 55
SEED = 42

ACTOR_FIELDNAMES = [
    "id",
    "student_question",
    "target_learner_level",
    "instruction_constraints",
    "expected_rubric",
]

_MANIFEST_PATH = Path("data/processed_mrbench/judge_split_manifest.json")

_ACTOR_POOL_PATHS = [
    Path("data/processed_mrbench/dev.csv"),
    Path("data/processed_mrbench/test.csv"),
]

_JUDGE_SPLIT_KEYS = ["calibration", "judge_dev", "judge_test"]

_BUCKET_KEYS = ["short", "medium", "long"]
_BUCKET_DISPLAY = {
    "short":  "short  (<500 chars)",
    "medium": "medium (500–1500 chars)",
    "long":   "long   (>1500 chars)",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _length_bucket(question: str) -> str:
    n = len(question)
    if n < 500:
        return "short"
    if n <= 1500:
        return "medium"
    return "long"


def build_forbidden_base_ids(manifest_path: Path) -> set[str]:
    """Return the set of conversation ids used by any Judge split.

    Reads calibration + judge_dev + judge_test conversation ids from the manifest
    written by scripts/01_create_splits.py.
    """
    if not manifest_path.exists():
        sys.exit(
            f"ERROR: {manifest_path} not found. Run 01_create_splits.py first so the "
            "Actor pool can exclude every Judge-split conversation."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    forbidden: set[str] = set()
    for key in _JUDGE_SPLIT_KEYS:
        forbidden.update(manifest.get(key, {}).get("conversation_ids", []))
    return forbidden


def load_actor_pool(pool_paths: list[Path]) -> list[dict]:
    """Load and concatenate actor rows from the given CSV paths, deduplicating by ID."""
    rows: list[dict] = []
    seen_ids: set[str] = set()
    for path in pool_paths:
        if not path.exists():
            sys.exit(f"ERROR: {path} not found. Run prepare_mrbench first.")
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["id"] in seen_ids:
                    print(f"  WARNING: duplicate actor ID {row['id']!r} skipped.")
                    continue
                seen_ids.add(row["id"])
                rows.append(row)
    return rows


def create_actor_splits(
    rows: list[dict],
    forbidden_base_ids: set[str],
    test_size: int,
    train_cap: int,
    seed: int,
) -> tuple[list[dict], list[dict]]:
    """
    Filter eligible rows (excluding forbidden ids), shuffle once with `seed`, then
    take the first `test_size` rows as actor_test and the next (up to `train_cap`)
    rows as actor_train.

    Returns (train_rows, test_rows). Raises ValueError if the eligible pool cannot
    fill the test split with at least one conversation left for training.
    """
    eligible = [r for r in rows if r["id"] not in forbidden_base_ids]
    if len(eligible) <= test_size:
        raise ValueError(
            f"Only {len(eligible)} eligible rows after forbidden-ID exclusion, "
            f"but more than test_size={test_size} are required (60 test + >=1 train)."
        )

    rng = random.Random(seed)
    shuffled = eligible.copy()
    rng.shuffle(shuffled)

    test = shuffled[:test_size]
    train = shuffled[test_size : test_size + train_cap]
    return train, test


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_diversity(label: str, rows: list[dict]) -> None:
    n = len(rows)
    print(f"\n{label} ({n} rows):")
    if n == 0:
        return

    level_counts = Counter(r["target_learner_level"] for r in rows)
    print(f"  target_learner_level: {len(level_counts)} unique values")
    for val, cnt in level_counts.most_common(5):
        print(f"    {val!r:<50} {cnt:>3}")

    bucket_counts = Counter(_length_bucket(r["student_question"]) for r in rows)
    print(f"  student_question length:")
    for b in _BUCKET_KEYS:
        cnt = bucket_counts.get(b, 0)
        print(f"    {_BUCKET_DISPLAY[b]}: {cnt:>3}  ({cnt / n:.0%})")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ACTOR_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote: {path}  ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Actor Split Construction ===\n")

    # --- Forbidden conversation ids from Judge splits ---
    forbidden = build_forbidden_base_ids(_MANIFEST_PATH)
    print(f"Forbidden conversation ids (calibration + judge_dev + judge_test): {len(forbidden)}")

    # --- Source pool ---
    pool = load_actor_pool(_ACTOR_POOL_PATHS)
    excluded_count = sum(1 for r in pool if r["id"] in forbidden)
    eligible_count = len(pool) - excluded_count
    print(f"Source pool (dev.csv + test.csv): {len(pool)} rows")
    print(f"Excluded (judge-split ids):       {excluded_count}")
    print(f"Eligible for Actor splits:        {eligible_count}")

    # --- Actor splits ---
    print(f"\nSampling actor splits (seed={SEED}, test={FULL_TEST_SIZE}, train cap={FULL_TRAIN_CAP})…")
    try:
        actor_train, actor_test = create_actor_splits(
            pool, forbidden, FULL_TEST_SIZE, FULL_TRAIN_CAP, SEED
        )
    except ValueError as exc:
        sys.exit(f"\nERROR: {exc}")

    # --- Hard assertions ---
    assert len(actor_test) == FULL_TEST_SIZE
    assert len(actor_train) <= FULL_TRAIN_CAP
    assert len(actor_train) == min(FULL_TRAIN_CAP, eligible_count - FULL_TEST_SIZE)

    train_ids = {r["id"] for r in actor_train}
    test_ids = {r["id"] for r in actor_test}

    assert not (train_ids & test_ids), "actor_train ∩ actor_test must be empty"
    assert train_ids.isdisjoint(forbidden), "actor_train must exclude all judge-split ids"
    assert test_ids.isdisjoint(forbidden), "actor_test must exclude all judge-split ids"
    assert len(train_ids) == len(actor_train), "Duplicate IDs in actor_train"
    assert len(test_ids) == len(actor_test), "Duplicate IDs in actor_test"

    # --- Overlap report ---
    print("\n--- Overlap audit ---")
    print(f"  actor_train ∩ actor_test:        {len(train_ids & test_ids)}  (expected 0)")
    for key in _JUDGE_SPLIT_KEYS:
        print(f"  actor_train ∩ {key:<11}: {len(train_ids & forbidden)}  (expected 0)")
        print(f"  actor_test  ∩ {key:<11}: {len(test_ids & forbidden)}  (expected 0)")

    # --- Diversity reports ---
    _print_diversity("ACTOR_TRAIN", actor_train)
    _print_diversity("ACTOR_TEST", actor_test)

    # --- Write ---
    out_dir = Path("data/processed_mrbench")
    _write_csv(out_dir / "actor_train.csv", actor_train)
    _write_csv(out_dir / "actor_test.csv", actor_test)

    print(f"\n=== Actor split summary ===")
    print(f"  actor_train: {len(actor_train)} conversations")
    print(f"  actor_test:  {len(actor_test)} conversations")
    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
