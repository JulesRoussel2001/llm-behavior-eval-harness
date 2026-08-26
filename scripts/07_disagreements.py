"""
Disagreement analysis for a validate_judge output JSONL. Local, no API calls.

For each of the 8 rubric dimensions, reports where the judge disagreed with the
human gold label, split into:
  FP  (false positive): human=False, judge=True
  FN  (false negative): human=True,  judge=False

Output is a Markdown file. Per dimension:
  - FP / FN counts,
  - every FP row then every FN row: item_id, the judge's reason for that dimension,
    and the first 300 characters of tutor_response_excerpt (capped at 25 rows per
    group with a "... N more" line),
  - a crude top-10 word-frequency list of the judge's reasons for FPs and for FNs
    (common stopwords removed) to surface recurring patterns fast.

Usage:
  PYTHONPATH=src .venv/bin/python scripts/07_disagreements.py \
    --input judge_dev_results.jsonl --output disagreements_dev.md
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from claude_behavior_eval.schemas import MRBenchEvaluation

DIMS = list(MRBenchEvaluation.model_fields.keys())
MAX_ROWS_PER_GROUP = 25
EXCERPT_CHARS = 300
TOP_WORDS = 10

_WORD_RE = re.compile(r"[a-z']+")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "it", "its", "this", "that", "these",
    "those", "as", "at", "by", "from", "not", "no", "s", "t", "than", "then",
    "which", "who", "whom", "their", "them", "they", "there", "here", "he", "she",
}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _top_words(reasons: list[str], n: int = TOP_WORDS) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for reason in reasons:
        for word in _WORD_RE.findall((reason or "").lower()):
            if word in _STOPWORDS or len(word) <= 1:
                continue
            counter[word] += 1
    return counter.most_common(n)


def analyze(rows: list[dict]) -> dict[str, dict]:
    """Return {dim: {"fp": [entry...], "fn": [entry...],
                     "fp_words": [(w,c)...], "fn_words": [(w,c)...]}}.

    Each entry is {"item_id", "reason", "excerpt"}.
    """
    result: dict[str, dict] = {}
    for dim in DIMS:
        fp: list[dict] = []
        fn: list[dict] = []
        for r in rows:
            human = bool(r["human_labels"][dim])
            judge = bool(r["judge_labels"][dim])
            if human == judge:
                continue
            entry = {
                "item_id": r.get("item_id", ""),
                "reason": (r.get("judge_reasons", {}) or {}).get(dim, ""),
                "excerpt": (r.get("tutor_response_excerpt", "") or "")[:EXCERPT_CHARS],
            }
            if (not human) and judge:
                fp.append(entry)
            elif human and (not judge):
                fn.append(entry)
        result[dim] = {
            "fp": fp,
            "fn": fn,
            "fp_words": _top_words([e["reason"] for e in fp]),
            "fn_words": _top_words([e["reason"] for e in fn]),
        }
    return result


def _render_group(label: str, entries: list[dict]) -> list[str]:
    lines = [f"**{label} ({len(entries)}):**", ""]
    if not entries:
        lines += ["_none_", ""]
        return lines
    for e in entries[:MAX_ROWS_PER_GROUP]:
        lines += [
            f"- **{e['item_id']}**",
            f"  - reason: {e['reason']}",
            f"  - excerpt: {e['excerpt']!r}",
        ]
    if len(entries) > MAX_ROWS_PER_GROUP:
        lines.append(f"- ... {len(entries) - MAX_ROWS_PER_GROUP} more")
    lines.append("")
    return lines


def _render_words(label: str, words: list[tuple[str, int]]) -> str:
    if not words:
        return f"- {label} reason words: _none_"
    joined = ", ".join(f"{w} ({c})" for w, c in words)
    return f"- {label} reason words: {joined}"


def render_markdown(analysis: dict[str, dict], source: str) -> str:
    lines = [
        "# Judge Disagreement Analysis",
        "",
        f"Source: `{source}`",
        "",
        "FP = human False, judge True (judge over-credits). "
        "FN = human True, judge False (judge under-credits).",
        "",
    ]
    for dim in DIMS:
        data = analysis[dim]
        lines += [
            f"## {dim}",
            "",
            f"FP: {len(data['fp'])}  ·  FN: {len(data['fn'])}",
            "",
            _render_words("FP", data["fp_words"]),
            _render_words("FN", data["fn_words"]),
            "",
        ]
        lines += _render_group("False positives", data["fp"])
        lines += _render_group("False negatives", data["fn"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge disagreement analysis (local, no API).")
    parser.add_argument("--input", required=True, help="validate_judge output JSONL.")
    parser.add_argument("--output", required=True, help="Markdown output path.")
    args = parser.parse_args()

    rows = read_jsonl(Path(args.input))
    analysis = analyze(rows)
    md = render_markdown(analysis, args.input)
    Path(args.output).write_text(md, encoding="utf-8")

    total_fp = sum(len(analysis[d]["fp"]) for d in DIMS)
    total_fn = sum(len(analysis[d]["fn"]) for d in DIMS)
    print(f"Wrote {args.output}  ({len(rows)} rows; total FP={total_fp}, FN={total_fn})")


if __name__ == "__main__":
    main()
