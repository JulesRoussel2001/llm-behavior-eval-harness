from __future__ import annotations

# Actor, judge, and optimizer model IDs are centralized here for easy pinning or updating.
DEFAULT_JUDGE_MODEL: str = "claude-haiku-4-5-20251001"
DEFAULT_ACTOR_MODEL: str = "claude-haiku-4-5-20251001"
# Optimizer defaults to the same Sonnet-class model used for judging, centralized for easy replacement.
DEFAULT_OPTIMIZER_MODEL: str = DEFAULT_JUDGE_MODEL
