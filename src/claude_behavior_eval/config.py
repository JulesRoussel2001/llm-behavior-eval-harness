from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

# Actor, judge, and optimizer model IDs are centralized here for easy pinning or updating.
DEFAULT_JUDGE_MODEL: str = "claude-haiku-4-5-20251001"
DEFAULT_ACTOR_MODEL: str = "claude-haiku-4-5-20251001"
# Judge, actor, and optimizer are all pinned to Haiku 4.5 (claude-haiku-4-5-20251001);
# the optimizer reuses the judge model ID, centralized here for easy replacement.
DEFAULT_OPTIMIZER_MODEL: str = DEFAULT_JUDGE_MODEL
