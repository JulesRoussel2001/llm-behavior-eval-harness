"""Judge test-retest on identical rows. Usage:
  python scripts/10_self_consistency.py judge_dev_results_v2.jsonl judge_dev_results_v2_rep2.jsonl judge_dev_results_v2_rep3.jsonl
"""
import json, sys
from itertools import combinations

DIMS = ["mistake_identification","mistake_location","answer_revealing_appropriate","providing_guidance",
        "actionability","coherence","tutor_tone","human_likeness"]

def load(p):
    return {r["item_id"]: r["judge_labels"] for r in map(json.loads, filter(str.strip, open(p, encoding="utf-8")))}

def kappa(a, b):
    n = len(a); po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)

runs = [load(p) for p in sys.argv[1:]]
ids = sorted(set.intersection(*(set(r) for r in runs)))
print(f"runs={len(runs)}  common rows={len(ids)}")
print(f"{'dimension':30s} {'pairwise agree %':>16s} {'pairwise kappa':>15s} {'rows flipping (any run)':>24s}")
tot_agree = []; tot_flip = 0
for d in DIMS:
    agrees, kaps = [], []
    for i, j in combinations(range(len(runs)), 2):
        a = [bool(runs[i][k][d]) for k in ids]; b = [bool(runs[j][k][d]) for k in ids]
        agrees.append(sum(x == y for x, y in zip(a, b)) / len(ids) * 100); kaps.append(kappa(a, b))
    flips = sum(len({bool(r[k][d]) for r in runs}) > 1 for k in ids); tot_flip += flips
    tot_agree.append(sum(agrees) / len(agrees))
    print(f"{d:30s} {sum(agrees)/len(agrees):16.1f} {sum(kaps)/len(kaps):15.2f} {flips:>24d}")
all_same = sum(all(len({bool(r[k][d]) for r in runs}) == 1 for d in DIMS) for k in ids)
print(f"\nmean pairwise agreement: {sum(tot_agree)/len(tot_agree):.1f}%   rows identical on all 8 dims across all runs: {all_same}/{len(ids)}   label flips: {tot_flip}/{len(ids)*len(DIMS)}")
