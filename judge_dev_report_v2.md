# Judge Validation Report

**Judge prompt version:** v2  
**Judge prompt SHA-256:** 16c178792319c4489f328f7732e2be5095be4e58379c08aa6c24d4ccf2d9278d  
**Reasons truncated (>25 words):** 0  
**Macro F1:** 89.1%  
**Macro Accuracy:** 87.0%

## Dimension Metrics

| Dimension | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| mistake_identification | 84.2% | 97.3% | 84.6% | 90.5% |
| mistake_location | 81.1% | 97.1% | 80.6% | 88.1% |
| answer_revealing_appropriate | 93.7% | 98.6% | 93.6% | 96.1% |
| providing_guidance | 88.9% | 94.8% | 91.9% | 93.3% |
| actionability | 82.1% | 91.7% | 82.2% | 86.7% |
| coherence | 92.6% | 97.6% | 94.2% | 95.8% |
| tutor_tone | 79.5% | 63.8% | 67.3% | 65.5% |
| human_likeness | 93.7% | 97.1% | 96.0% | 96.6% |

## Weakest Dimensions

### tutor_tone (F1: 65.5%)

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tone is neutral and procedural; no explicit encouragement of student effort or ability.
  - **Excerpt:** 'Good, so how many bunnies does this mean that he has, when you add the kittens?'

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_GPT4
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tone is neutral; affirming correctness followed by correction is formulaic, not encouraging.
  - **Excerpt:** "That's correct! After giving away some bunnies to Rodney, Marlon indeed has 18 bunnies left. However, when calculating t"

- **Item:** 5032-7e6f6017-7c1d-4232-b9cb-13a563f9bf01_Sonnet
  - **Human:** False
  - **Judge:** True
  - **Reason:** Tutor uses affirming language ('you remembered correctly') before redirecting, encouraging the student.
  - **Excerpt:** "I see you remembered Jose's lunch cost correctly, but let's take another look at what the question says about Rick's lun"

### actionability (F1: 86.7%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor presents a corrected calculation without directing the student to perform a specific next action or verify their understanding.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Gemini
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor states the correction but does not direct the student to recalculate or take a specific next step.
  - **Excerpt:** "You're on the right track, but remember that the 60% is applied to her commission, not her total earnings after the comm"

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor explains the correction but does not direct student to recalculate or verify the answer.
  - **Excerpt:** "That's correct, Marlon has 18 female baby bunnies left in his hutch after giving 12 to Rodney, so when you calculate the"

### mistake_location (F1: 88.1%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor provides no specific reference to which step or calculation contains the error.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Gemini
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not pinpoint where the error occurs in the final sum.
  - **Excerpt:** "That's a great start, but remember, the bunnies also gave birth to kittens, so we need to add those to the total number "

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not locate the error in the final calculation step where 30+36 should be 18+36.
  - **Excerpt:** 'Good, so how many bunnies does this mean that he has, when you add the kittens?'

### mistake_identification (F1: 90.5%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not identify the core mistake: the student should allocate 60% of commission to personal needs, not 40%.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not clearly identify the specific mistake in the student's reasoning or calculation.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Gemini
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not identify the core mistake: using 30 instead of 18 in the final calculation.
  - **Excerpt:** "That's a great start, but remember, the bunnies also gave birth to kittens, so we need to add those to the total number "

### providing_guidance (F1: 93.3%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor corrects the calculation but does not explain why commission is the base or clarify the 60/40 split logic.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Sonnet
  - **Human:** True
  - **Judge:** False
  - **Reason:** The tutor questions a correct answer rather than guiding toward the actual error in the final calculation.
  - **Excerpt:** "That's a good start, but let's think carefully about how many bunnies Marlon has after giving some to Rodney - are you s"

- **Item:** 1081-903b7bbe-1fc9-4196-9c04-7f7d9c04d865_Sonnet
  - **Human:** False
  - **Judge:** True
  - **Reason:** Tutor guides student to reconsider how cups labeled relates to total post-its used throughout the day.
  - **Excerpt:** "Great observation about the 220 cups and post-its, now let's think about how this relates to the total number of post-it"

### coherence (F1: 95.8%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Response contradicts prior tutor guidance and is unclear about what 'her personal need amount' refers to.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Phi3
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor ignores the student's work and context, pivoting to an unrelated next problem without acknowledgment.
  - **Excerpt:** "Great job! Now let's move on to the next problem together."

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Sonnet
  - **Human:** True
  - **Judge:** False
  - **Reason:** The tutor contradicts the student's correct prior answer by questioning whether 18 is right.
  - **Excerpt:** "That's a good start, but let's think carefully about how many bunnies Marlon has after giving some to Rodney - are you s"

### answer_revealing_appropriate (F1: 96.1%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor states the final answer directly: $2880 - $1728 = $1152, revealing the complete solution.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 638345336_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor directly states the answer (4 goes into 6 one time) rather than guiding student to discover it.
  - **Excerpt:** "I think there may be a mistake - remember, we're looking for how many times 4 fits into 6, and from our multiplication t"

- **Item:** 2162-38ea7f4f-0d0c-411f-80ae-f2401b2fdeb8_Phi3
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor directly states the correct conversion (10 weeks and 0 days) without prompting student to recalculate.
  - **Excerpt:** 'To convert 70 days into weeks and days, divide the number of days by 7, which gives you 10 weeks and 0 days.\n\nTutor resp'

### human_likeness (F1: 96.6%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Response is terse, grammatically incomplete, and reads as robotic rather than natural tutoring.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Phi3
  - **Human:** True
  - **Judge:** False
  - **Reason:** Response is generic boilerplate disconnected from the specific problem; reads formulaic and dismissive of student work.
  - **Excerpt:** "Great job! Now let's move on to the next problem together."

- **Item:** 5722-bc3658a3-ba86-43c0-a3f3-5a42e167e492_Phi3
  - **Human:** True
  - **Judge:** False
  - **Reason:** Response reads as generic boilerplate disconnected from the specific problem context and student's misconception.
  - **Excerpt:** 'To calculate the percentage change, subtract the old value from the new value, divide by the old value, and multiply by '

