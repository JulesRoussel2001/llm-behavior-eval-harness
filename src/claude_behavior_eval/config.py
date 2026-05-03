from __future__ import annotations

# Actor, judge, and optimizer model IDs are centralized here for easy pinning or updating.
DEFAULT_JUDGE_MODEL: str = "claude-3-5-sonnet-latest"
DEFAULT_ACTOR_MODEL: str = "claude-3-5-haiku-latest"
# Optimizer defaults to the same Sonnet-class model used for judging, centralized for easy replacement.
DEFAULT_OPTIMIZER_MODEL: str = DEFAULT_JUDGE_MODEL
