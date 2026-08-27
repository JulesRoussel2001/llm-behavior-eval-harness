# Judge Validation Report

**Judge prompt version:** v1  
**Judge prompt SHA-256:** c8a6762b72c9cecc6b4e7bebc96be2c7f7370885a3779a3fe57ff5085e3a8f1a  
**Reasons truncated (>25 words):** 1  
**Macro F1:** 86.9%  
**Macro Accuracy:** 83.2%

## Dimension Metrics

| Dimension | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| mistake_identification | 85.3% | 98.0% | 85.2% | 91.1% |
| mistake_location | 78.9% | 97.0% | 78.2% | 86.6% |
| answer_revealing_appropriate | 92.1% | 98.0% | 92.3% | 95.0% |
| providing_guidance | 76.3% | 95.3% | 75.6% | 84.3% |
| actionability | 83.7% | 91.9% | 84.4% | 88.0% |
| coherence | 85.8% | 97.4% | 86.5% | 91.6% |
| tutor_tone | 75.3% | 55.0% | 80.0% | 65.2% |
| human_likeness | 88.4% | 98.1% | 89.3% | 93.5% |

## Weakest Dimensions

### tutor_tone (F1: 65.2%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** False
  - **Judge:** True
  - **Reason:** Tutor uses softening language ('small issue') and collaborative phrasing, creating an encouraging tone.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tone is neutral and matter-of-fact; lacks explicit encouragement or affirmation of student progress.
  - **Excerpt:** 'Good, so how many bunnies does this mean that he has, when you add the kittens?'

- **Item:** 1081-903b7bbe-1fc9-4196-9c04-7f7d9c04d865_GPT4
  - **Human:** False
  - **Judge:** True
  - **Reason:** Tutor uses softening language ('little mistake', 'common mistake') and affirms the student's correct identification of cups labeled.
  - **Excerpt:** "That's correct, she used 220 post-it notes at work, but you made a little mistake in your calculation. The total number "

### providing_guidance (F1: 84.3%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor provides incorrect guidance; the logic of subtracting from commission alone contradicts the problem statement.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_GPT4
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor performs the calculation rather than guiding student through reasoning about what 'earnings' means.
  - **Excerpt:** "That's a good correction, but remember, her total earning is her commission, which is $2880. Then, she spends 60% on her"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor's suggestion is vague and does not clarify the correct conceptual approach.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

### mistake_location (F1: 86.6%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not locate the actual mistake: 60% should apply to commission only, not total earnings.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not clearly locate which step or calculation contains the error.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Gemini
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not pinpoint where the mistake occurs in the calculation or reasoning.
  - **Excerpt:** "That's a great start, but remember, the bunnies also gave birth to kittens, so we need to add those to the total number "

### actionability (F1: 88.0%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor's suggested calculation is mathematically incorrect and misleading for the student's learning.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Instruction lacks specificity; unclear which values to subtract or in what order.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 1081-903b7bbe-1fc9-4196-9c04-7f7d9c04d865_Sonnet
  - **Human:** False
  - **Judge:** True
  - **Reason:** Tutor directs student to think about how cups and post-its relate, providing a concrete conceptual step to revisit the calculation.
  - **Excerpt:** "Great observation about the 220 cups and post-its, now let's think about how this relates to the total number of post-it"

### mistake_identification (F1: 91.1%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor misidentifies the error; the student's revised approach is actually incorrect, but tutor's suggested correction is also wrong.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Gemini
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not identify the core error: student counted original 30 bunnies instead of remaining 18.
  - **Excerpt:** "That's a great start, but remember, the bunnies also gave birth to kittens, so we need to add those to the total number "

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not identify the student's error: using 30 instead of 18 in the final sum.
  - **Excerpt:** 'Good, so how many bunnies does this mean that he has, when you add the kittens?'

### coherence (F1: 91.6%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Response contradicts the problem context; savings should come from commission earnings, not be subtracted from commission itself.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_GPT4
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor's statement that 'total earning is her commission' contradicts standard financial terminology and the problem context.
  - **Excerpt:** "That's a good correction, but remember, her total earning is her commission, which is $2880. Then, she spends 60% on her"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Response contradicts prior tutor guidance and is logically unclear given context.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

### human_likeness (F1: 93.5%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_GPT4
  - **Human:** True
  - **Judge:** False
  - **Reason:** Response reads formulaic and contains a confusing/incorrect statement about what 'total earning' means.
  - **Excerpt:** "That's a good correction, but remember, her total earning is her commission, which is $2880. Then, she spends 60% on her"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Terse, grammatically awkward phrasing reads as robotic rather than natural tutoring.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Phi3
  - **Human:** True
  - **Judge:** False
  - **Reason:** Response reads as generic boilerplate disconnected from the specific problem context and student's actual work.
  - **Excerpt:** "Great job! Now let's move on to the next problem together."

### answer_revealing_appropriate (F1: 95.0%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor directly states the final answer ($2880 - $1728) without guiding student to derive it.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 5032-7e6f6017-7c1d-4232-b9cb-13a563f9bf01_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor directly states the corrected value ($45) without guiding student to discover it.
  - **Excerpt:** "Since Jose and Rick eat lunch of the same price, Rick's lunch also cost $45."

- **Item:** 638345336_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor directly states the final answer: 4 goes into 6 one time with a remainder.
  - **Excerpt:** "I think there may be a mistake - remember, we're looking for how many times 4 fits into 6, and from our multiplication t"

