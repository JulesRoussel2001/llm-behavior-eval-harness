from __future__ import annotations

from anthropic import Anthropic

from claude_behavior_eval.config import DEFAULT_JUDGE_MODEL
from claude_behavior_eval.schemas import DatasetItem, MRBenchEvaluation

_SYSTEM_PROMPT = (
    "You are a frozen rubric-based pedagogical judge evaluating AI tutor responses "
    "under the MRBench academic-tutoring taxonomy. "
    "You are a validated proxy evaluator, not an objective ground truth: your scores "
    "approximate expert human judgment and should be interpreted accordingly. "
    "Evaluate the generated tutor response by calling the mrbench_evaluation tool. "
    "Score each dimension as true (pass) or false (fail) based strictly on the "
    "provided rubric criteria."
)


class ClaudeRubricJudge:
    def __init__(
        self,
        client: Anthropic | None = None,
        model: str = DEFAULT_JUDGE_MODEL,
    ) -> None:
        self._client = client if client is not None else Anthropic()
        self._model = model

    def evaluate_response(
        self,
        item: DatasetItem,
        generated_response: str,
    ) -> MRBenchEvaluation:
        user_message = (
            f"Item ID: {item.id}\n"
            f"Student question: {item.student_question}\n"
            f"Target learner level: {item.target_learner_level}\n"
            f"Instruction constraints: {item.instruction_constraints}\n"
            f"Expected rubric: {item.expected_rubric}\n\n"
            f"Generated tutor response:\n{generated_response}"
        )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            temperature=0.0,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[
                {
                    "name": "mrbench_evaluation",
                    "description": (
                        "Record binary pass/fail scores for each MRBench "
                        "pedagogical dimension."
                    ),
                    "input_schema": MRBenchEvaluation.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "mrbench_evaluation"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "mrbench_evaluation":
                return MRBenchEvaluation(**block.input)

        raise ValueError(
            "No mrbench_evaluation tool_use block found in the judge response."
        )
