from __future__ import annotations

from anthropic import Anthropic

from claude_behavior_eval.config import DEFAULT_ACTOR_MODEL
from claude_behavior_eval.deterministic_checks import contains_roleplay_marker
from claude_behavior_eval.judge import ClaudeRubricJudge
from claude_behavior_eval.schemas import DatasetItem, EvaluationResult


class PipelineOrchestrator:
    def __init__(
        self,
        judge: ClaudeRubricJudge,
        actor_client: Anthropic | None = None,
        actor_model: str = DEFAULT_ACTOR_MODEL,
    ) -> None:
        self._judge = judge
        self._actor_client = actor_client if actor_client is not None else Anthropic()
        self._actor_model = actor_model

    def evaluate_single_item(
        self,
        item: DatasetItem,
        actor_system_prompt: str,
    ) -> EvaluationResult:
        user_message_parts = [f"Student question: {item.student_question}"]
        if item.target_learner_level:
            user_message_parts.append(f"Target learner level: {item.target_learner_level}")
        if item.instruction_constraints:
            user_message_parts.append(
                f"Please follow these constraints: {', '.join(item.instruction_constraints)}"
            )
        user_message = "\n".join(user_message_parts)

        actor_response = self._actor_client.messages.create(
            model=self._actor_model,
            max_tokens=512,
            temperature=0.7,
            system=actor_system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        generated_text: str | None = None
        for block in actor_response.content:
            if block.type == "text":
                generated_text = block.text
                break

        if generated_text is None:
            raise ValueError(
                f"Actor returned no text block for item '{item.id}'."
            )

        if "no_roleplay" in item.instruction_constraints and contains_roleplay_marker(generated_text):
            return EvaluationResult(
                item_id=item.id,
                generated_response=generated_text,
                deterministic_passed=False,
                judge_scores=None,
            )

        judge_scores = self._judge.evaluate_response(item, generated_text)
        return EvaluationResult(
            item_id=item.id,
            generated_response=generated_text,
            deterministic_passed=True,
            judge_scores=judge_scores,
        )
