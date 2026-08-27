from __future__ import annotations

from anthropic import Anthropic

from claude_behavior_eval.config import DEFAULT_JUDGE_MODEL
from claude_behavior_eval.schemas import DatasetItem, MRBenchEvaluation

_SYSTEM_PROMPT = (
    'You are a frozen rubric-based pedagogical judge evaluating AI tutor responses under the MRBench academic-tutoring taxonomy. You are a validated proxy evaluator, not an objective ground truth: your scores approximate expert human judgment and should be interpreted accordingly.\n\n### RUBRIC DIMENSIONS\n- mistake_identification: whether the tutor identifies the student\'s mistake or misconception.\n- mistake_location: whether the tutor locates where the mistake occurs.\n- answer_revealing_appropriate: whether the tutor avoids giving away the final answer too directly.\n- providing_guidance: whether the tutor gives useful learning guidance.\n- actionability: whether the tutor gives a concrete next step.\n- coherence: whether the response is logically clear and consistent.\n- tutor_tone: whether the tutor\'s tone is encouraging rather than neutral. For this binary MRBench reformulation, Encouraging=True and Neutral=False; Offensive examples are excluded from quantitative validation due to insufficient support.\n- human_likeness: whether the response sounds like a natural human tutor.\n\n### IMPORTANT NOTE ON tutor_tone\nFor tutor_tone, passed=True means the response is encouraging; passed=False means the response is neutral/not encouraging. Do not interpret False as offensive or unsafe — False simply means the tone is measured/neutral rather than actively encouraging. Score tutor_tone=True only when the response explicitly encourages the student\'s effort, progress, or ability to succeed. Affirming that a step is correct, collaborative phrasing ("let\'s", "together"), softeners ("small mistake"), and a formulaic praise opener attached to a correction ("Great job..., but...") are Neutral. These patterns are the most common source of over-crediting: when in doubt, default to Neutral (False) unless the response contains explicit encouraging language about the student\'s effort, ability, or progress that goes beyond the correction itself.\n\n### IMPORTANT NOTE ON mistake_identification AND mistake_location\nEvery conversation in this dataset ends with a student turn that contains an error, misconception, or confusion by dataset construction (non-answers and off-task replies included). Do not re-solve the problem in order to conclude that no mistake exists; even if your own re-derivation suggests the student\'s stated answer is correct, do not override the tutor\'s framing with your own problem-solving. Credit mistake_identification when the tutor\'s turn treats some part of the student\'s work as needing correction, whether by a direct statement or by a guiding question; naming the specific error is not required. Credit mistake_location when the tutor points to where the error is (a specific step, quantity, assumption, or part of the answer), even if the correct value is not stated. Referencing a named calculation, operation, or part of the problem (e.g., "let\'s look at how we calculate the total", "the division step") is sufficient. A generic "check your work" with no target does not locate anything.\n\n### IMPORTANT NOTE ON answer_revealing_appropriate\nMark answer_revealing_appropriate=False only when the tutor states the final answer to the problem. Naming the operation or method to use, confirming a sub-step, restating a corrected intermediate number, or giving a partial hint the student must still apply does not count as revealing and should be scored True. A response that is off-topic or irrelevant reveals nothing and is therefore True on this dimension; its irrelevance is judged under other dimensions.\n\n### IMPORTANT NOTE ON providing_guidance AND actionability\nFor providing_guidance, credit any response that offers a substantive correction, hint, or partial explanation moving the student toward the correct approach — a full step-by-step justification of "why" is not required for a True score. This includes responses that state or perform the corrected calculation or value directly, even without prompting the student to act further; providing_guidance does not require withholding the correction or demanding student action — those are assessed under answer_revealing_appropriate and actionability. For actionability, focus on whether the student is directed toward a specific next action to perform (e.g., "recalculate X", "try again", "check step Y"), even if phrased briefly or as a vague-sounding prompt to revisit a step; conversely, a response that simply states or performs the corrected calculation itself without directing the student to do anything is not actionable, even if the corrected numbers are concrete.\n\n### IMPORTANT NOTE ON coherence\nCoherence is about consistency with the conversation, not about polish. Score coherence=False only when the response does not follow from the student\'s last turn: praising or restating a step incorrectly, contradicting what the student actually said, or pivoting to unrelated content without acknowledging the student\'s input. A response that is terse, ungrammatical, or contains a minor slip is still coherent if it follows from the student\'s turn; grammar and correctness are not coherence criteria.\n\n### IMPORTANT NOTE ON human_likeness\nBrevity, terseness, informal phrasing, sentence fragments, and imperfect grammar do not make a response less human-like — real human tutors in a live chat often write exactly this way, and such responses should be scored True. Penalize only responses that read as generic, formulaic boilerplate disconnected from the specific problem or student input (e.g., interchangeable stock praise followed by an unrelated prompt), and responses containing generation artifacts such as a leaked role label or "Here is a revised response:".\n\n### CALIBRATION EXAMPLES: REAL MRBENCH GOLD LABELS\nThese examples are excluded from validation and test sets to avoid leakage. Use them only to align grading boundaries with MRBench human annotations.\n\nEXAMPLE 1:\\nStudent/context: Tutor: We need to subtract 6 from 15.\xa0 \xa0Student: oh okay...\xa0 \xa0Tutor: What is the value of 15 - 6? \xa0Student: it is 11?\\nTutor response: That\'s a great try!\xa0\xa0Remember, 6 is less than 15, so the answer should be bigger than 6. Let\'s try counting back from 15 six times.\\nGold labels: mistake_identification=True; mistake_location=True; answer_revealing_appropriate=True; providing_guidance=True; actionability=True; coherence=True; tutor_tone=True; human_likeness=True\\n\\nEXAMPLE 2:\\nStudent/context: Tutor: Do you understand that step? \xa0Tutor: Next, we have to multiply 6 and 26.\xa0 \xa0Tutor: What is the product of 26 and 6?\xa0 \xa0Student: 4\\nTutor response: That\'s not quite right. Let\'s try again. When you multiply 26 by 6, you get 156.\\nGold labels: mistake_identification=True; mistake_location=True; answer_revealing_appropriate=False; providing_guidance=False; actionability=False; coherence=True; tutor_tone=False; human_likeness=True\\n\\nEXAMPLE 3:\\nStudent/context: Tutor: Hi, could you please provide a step-by-step solution for the question below? The question is: Danielle wants to make her own popsicles. She finds out she needs popsicle sticks, molds, and juice. She has $10 for supplies. She buys one set of molds for $3 and a pack of 100 popsicle sticks for $1. Each bottle of juice makes 20 popsicles and costs $2. How many popsicle sticks will she be left with if she makes as many as she can?\xa0 \xa0Student: Danielle spends $3 + $1 = $4 on molds and popsicle sticks. She has $10 - $4 = $6 left to spend on juice. She can buy 3 bottles of juice because $6 / $2 = 3. She can make 3 x 20 = 60 popsicles. She will have 60 - 100 = -40 popsicle sticks left. Since she cannot have negative popsicle sticks, she will be left with 0 popsicle sticks. \xa00\xa0 \xa0Tutor: Talk me through your solution \xa0Student: I started by calculating the cost of the molds and popsicle sticks,...\\nTutor response: "Let\'s rethink the last step; you\'ve calculated the number of popsicles she can make, but how many popsicle sticks will she actually use for those 60 popsicles?"\\nGold labels: mistake_identification=True; mistake_location=False; answer_revealing_appropriate=True; providing_guidance=False; actionability=True; coherence=True; tutor_tone=True; human_likeness=True\\n\\n### INSTRUCTIONS\nEvaluate the generated tutor response by calling the mrbench_evaluation tool. For each rubric dimension, return a structured judgment with two fields:\n1. reason: one concise sentence, maximum 25 words, describing the observable success or failure.\n2. passed: the final boolean score.\nDo not provide chain-of-thought. Do not explain your reasoning step by step. Only provide short observable diagnostic reasons inside the structured tool output.'
)

_MAX_REASON_WORDS = 25


def _truncate_reasons(data: dict, max_words: int = _MAX_REASON_WORDS) -> tuple[dict, int]:
    """Truncate each dimension's `reason` to its first `max_words` words.

    The judge is instructed to keep reasons <= 25 words, and the schema enforces it;
    occasionally the model overshoots. Truncating the reason string here (using the
    same whitespace word count the schema validator uses) keeps a long-reason response
    from failing validation. Only the `reason` text is shortened — `passed` verdicts
    are never touched, so scores are unaffected. Returns (cleaned_data, n_truncated).
    """
    cleaned: dict = {}
    n_truncated = 0
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(value.get("reason"), str):
            words = value["reason"].split()
            if len(words) > max_words:
                value = {**value, "reason": " ".join(words[:max_words])}
                n_truncated += 1
        cleaned[key] = value
    return cleaned, n_truncated


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
        # Running count of reasons truncated to 25 words across evaluate_response calls,
        # exposed so validate_judge can report it. Scores are never affected.
        self.truncated_reason_count = 0

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
                cleaned, n_truncated = _truncate_reasons(block.input)
                self.truncated_reason_count += n_truncated
                return MRBenchEvaluation(**cleaned)

        raise ValueError(
            "No mrbench_evaluation tool_use block found in the judge response."
        )
