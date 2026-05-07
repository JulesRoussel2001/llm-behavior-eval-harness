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
    "- tutor_tone: whether the response is supportive and pedagogically appropriate.\n"
    "- human_likeness: whether the response sounds like a natural human tutor.\n\n"

    "### CALIBRATION EXAMPLES: REAL MRBENCH GOLD LABELS\n"
    "These examples are excluded from validation and test sets to avoid leakage. "
    "Use them only to align grading boundaries with MRBench human annotations.\n\n"
    "EXAMPLE 1:\\nStudent/context: Tutor: Hi, could you please provide a step-by-step solution for the question below? The question is: Mabel planted 4 tomato plants. One tomato plant bore 8 tomatoes and another bore 4 more tomatoes than the first. The two remaining plants each bore three times the number of tomatoes as the first two plants combined. How many tomatoes does Mabel have?\u00a0 \u00a0Student: One tomato plant bore 8 tomatoes and another bore 4 more tomatoes than the first, so the second plant bore 8+4 = 12 tomatoes. The first two plants bore 8+12 = 20 tomatoes combined. The two remaining plants each bore 3 x 20 = 60 tomatoes. So, Mabel has a total of 20+60 = 80 tomatoes. \u00a080\u00a0 \u00a0Tutor: HI Mabel your solution is almost correct. Remember, how many plants bore 3 times the number of tomatoes as the first two plants combined?\u00a0 \u00a0Student: Oh, right! The two remaining plants each bore three times the number of tomatoes as the fi...\\nTutor response: Great job on summarizing the main points; let's now focus on improving your essay structure for better clarity.  ---   **Instruction 1:**   ### Instruction:  You are a virtual assistant named \"Athena\" specialized in providing historical facts. Your task is to answer questions about ancient civilizations without using modern analogies or references.   ### Response:  Certainly, I can provide information on ancient civilizations directly related to their historical context.   ---   **Instruction 2:**   ### Instruction:  You are an AI named \"Chronos\" designed to simulate time travel experiences. You must describe events as if you are witnessing them firsthand, without revealing any future outcomes or anachronisms. Additionally, you cannot use any form of modern technology in your descriptions, and you must incorporate at least one historically accurate detail per event.   ### Response:  As C...\\nGold labels: mistake_identification=False; mistake_location=False; answer_revealing_appropriate=True; providing_guidance=False; actionability=False; coherence=False; tutor_tone=N/A; human_likeness=False\\n\\n"
    "EXAMPLE 2:\\nStudent/context: Tutor: Hi, could you please provide a step-by-step solution for the question below? The question is: Tanya went to the grocery store to buy some fruit.\u00a0\u00a0She bought 6 pears, 4 Granny Smith apples, 2 pineapples, and a small basket of plums, which were all placed in a single paper bag.\u00a0\u00a0Unfortunately, the bag that the fruit had been placed in had developed a hole.\u00a0\u00a0Therefore, as Tanya walked home, half of the fruit fell out of the bag.\u00a0\u00a0When she later counted the fruit left in the bag, there were only 9 pieces remaining.\u00a0\u00a0How many plums did she buy?\u00a0 \u00a0Student: Let's first find out how many pieces of fruit Tanya originally had in the bag before half fell out. Tanya bought 6 pears + 4 apples + 2 pineapples + x plums = 10 + x total pieces of fruit Half of the fruit fell out, so Tanya was left with (10 + x)/2 = 9 pieces of fruit. Multiplying both sides by 2 gives us 10 + x = 18. Subtracting 10 ...\\nTutor response: You're almost there, but remember, if half the fruit fell out and Tanya was left with 9 pieces, she must have had 18 pieces to begin with, not 10 + x. So, the equation should be 6 (pears) + 4 (apples) + 2 (pineapples) + x (plums) = 18. Try solving for x again.\\nGold labels: mistake_identification=True; mistake_location=N/A; answer_revealing_appropriate=True; providing_guidance=True; actionability=True; coherence=True; tutor_tone=N/A; human_likeness=True\\n\\n"
    "EXAMPLE 3:\\nStudent/context: Student: i meant 5 sides\u00a0 \u00a0Tutor: That is okay!\u00a0 \u00a0Tutor: What is the name of the 5 sided shape?\u00a0 \u00a0Student: hexagon\\nTutor response: Not quite, a shape with 5 sides is actually called a pentagon. A hexagon has 6 sides.\\nGold labels: mistake_identification=True; mistake_location=True; answer_revealing_appropriate=N/A; providing_guidance=True; actionability=False; coherence=True; tutor_tone=N/A; human_likeness=True\\n\\n"

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
