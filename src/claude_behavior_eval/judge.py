from __future__ import annotations

from anthropic import Anthropic

from claude_behavior_eval.config import DEFAULT_JUDGE_MODEL
from claude_behavior_eval.schemas import DatasetItem, MRBenchEvaluation

_SYSTEM_PROMPT = (
    "You are a frozen rubric-based pedagogical judge evaluating AI tutor responses "
    "under the MRBench academic-tutoring taxonomy. "
    "You are a validated proxy evaluator, not an objective ground truth: your scores "
    "approximate expert human judgment and should be interpreted accordingly.\n\n"

    "### RUBRIC DIMENSIONS\n"
    "- mistake_identification: whether the tutor identifies the student's mistake or misconception.\n"
    "- mistake_location: whether the tutor locates where the mistake occurs.\n"
    "- answer_revealing_appropriate: whether the tutor avoids giving away the final answer too directly.\n"
    "- providing_guidance: whether the tutor gives useful learning guidance.\n"
    "- actionability: whether the tutor gives a concrete next step.\n"
    "- coherence: whether the response is logically clear and consistent.\n"
    "- tutor_tone: whether the tutor's tone is encouraging rather than neutral. For this binary MRBench reformulation, Encouraging=True and Neutral=False; Offensive examples are excluded from quantitative validation due to insufficient support.\n"
    "- human_likeness: whether the response sounds like a natural human tutor.\n\n"

    "### IMPORTANT NOTE ON tutor_tone\n"
    "For tutor_tone, passed=True means the response is encouraging; passed=False means the response is neutral/not encouraging. Do not interpret False as offensive or unsafe — False simply means the tone is measured/neutral rather than actively encouraging.\n\n"

    "### CALIBRATION EXAMPLES: REAL MRBENCH GOLD LABELS\n"
    "These examples are excluded from validation and test sets to avoid leakage. "
    "Use them only to align grading boundaries with MRBench human annotations.\n\n"
    "EXAMPLE 1:\\nStudent/context: Tutor: We need to subtract 6 from 15.\u00a0 \u00a0Student: oh okay...\u00a0 \u00a0Tutor: What is the value of 15 - 6? \u00a0Student: it is 11?\\nTutor response: That's a great try!\u00a0\u00a0Remember, 6 is less than 15, so the answer should be bigger than 6. Let's try counting back from 15 six times.\\nGold labels: mistake_identification=True; mistake_location=True; answer_revealing_appropriate=True; providing_guidance=True; actionability=True; coherence=True; tutor_tone=True; human_likeness=True\\n\\n"
    "EXAMPLE 2:\\nStudent/context: Tutor: Do you understand that step? \u00a0Tutor: Next, we have to multiply 6 and 26.\u00a0 \u00a0Tutor: What is the product of 26 and 6?\u00a0 \u00a0Student: 4\\nTutor response: That's not quite right. Let's try again. When you multiply 26 by 6, you get 156.\\nGold labels: mistake_identification=True; mistake_location=True; answer_revealing_appropriate=False; providing_guidance=False; actionability=False; coherence=True; tutor_tone=False; human_likeness=True\\n\\n"
    "EXAMPLE 3:\\nStudent/context: Tutor: Hi, could you please provide a step-by-step solution for the question below? The question is: Danielle wants to make her own popsicles. She finds out she needs popsicle sticks, molds, and juice. She has $10 for supplies. She buys one set of molds for $3 and a pack of 100 popsicle sticks for $1. Each bottle of juice makes 20 popsicles and costs $2. How many popsicle sticks will she be left with if she makes as many as she can?\u00a0 \u00a0Student: Danielle spends $3 + $1 = $4 on molds and popsicle sticks. She has $10 - $4 = $6 left to spend on juice. She can buy 3 bottles of juice because $6 / $2 = 3. She can make 3 x 20 = 60 popsicles. She will have 60 - 100 = -40 popsicle sticks left. Since she cannot have negative popsicle sticks, she will be left with 0 popsicle sticks. \u00a00\u00a0 \u00a0Tutor: Talk me through your solution \u00a0Student: I started by calculating the cost of the molds and popsicle sticks,...\\nTutor response: \"Let's rethink the last step; you've calculated the number of popsicles she can make, but how many popsicle sticks will she actually use for those 60 popsicles?\"\\nGold labels: mistake_identification=True; mistake_location=False; answer_revealing_appropriate=True; providing_guidance=False; actionability=True; coherence=True; tutor_tone=True; human_likeness=True\\n\\n"

    "### INSTRUCTIONS\n"
    "Evaluate the generated tutor response by calling the mrbench_evaluation tool. "
    "For each rubric dimension, return a structured judgment with two fields:\n"
    "1. reason: one concise sentence, maximum 25 words, describing the observable success or failure.\n"
    "2. passed: the final boolean score.\n"
    "Do not provide chain-of-thought. Do not explain your reasoning step by step. "
    "Only provide short observable diagnostic reasons inside the structured tool output."
)

class ClaudeRubricJudge:
    def __init__(
        self,
        client: Anthropic | None = None,
        model: str = DEFAULT_JUDGE_MODEL,
        system_prompt: str | None = None,
    ) -> None:
        self._client = client if client is not None else Anthropic()
        self._model = model
        # Defaults to the frozen module-level _SYSTEM_PROMPT. A caller (e.g.
        # validate_judge --judge-prompt-version) may inject a candidate prompt
        # assembled from judge_prompts/<version>.txt without editing this file.
        self._system_prompt = system_prompt if system_prompt is not None else _SYSTEM_PROMPT

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
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=[
                {
                    "name": "mrbench_evaluation",
                    "description": (
                        "Record structured diagnostic judgments for each MRBench "
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
