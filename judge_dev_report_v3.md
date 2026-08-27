# Judge Validation Report

**Judge prompt version:** v3  
**Judge prompt SHA-256:** c23035680b4161f1ccfa0ff12c6d2d2cc30ad1857f647f1dc65c87e4d66ebf8c  
**Reasons truncated (>25 words):** 0  
**Macro F1:** 89.4%  
**Macro Accuracy:** 87.0%

## Dimension Metrics

| Dimension | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| mistake_identification | 86.8% | 97.4% | 87.6% | 92.2% |
| mistake_location | 80.0% | 97.0% | 79.4% | 87.3% |
| answer_revealing_appropriate | 93.7% | 98.0% | 94.2% | 96.1% |
| providing_guidance | 87.9% | 93.1% | 92.5% | 92.8% |
| actionability | 82.1% | 90.4% | 83.7% | 86.9% |
| coherence | 92.1% | 96.4% | 94.7% | 95.6% |
| tutor_tone | 79.5% | 62.1% | 74.5% | 67.8% |
| human_likeness | 93.7% | 96.6% | 96.6% | 96.6% |

## Weakest Dimensions

### tutor_tone (F1: 67.8%)

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tone is neutral; no explicit encouragement of student effort or ability.
  - **Excerpt:** 'Good, so how many bunnies does this mean that he has, when you add the kittens?'

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_GPT4
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tone is neutral; affirming correctness followed by correction is formulaic, not encouraging.
  - **Excerpt:** "That's correct! After giving away some bunnies to Rodney, Marlon indeed has 18 bunnies left. However, when calculating t"

- **Item:** 1081-903b7bbe-1fc9-4196-9c04-7f7d9c04d865_Sonnet
  - **Human:** False
  - **Judge:** True
  - **Reason:** Tutor affirms student's observation as 'great' and collaboratively invites further thinking with 'let's.'
  - **Excerpt:** "Great observation about the 220 cups and post-its, now let's think about how this relates to the total number of post-it"

### actionability (F1: 86.9%)

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor explains the correction but does not direct student to recalculate or verify the answer.
  - **Excerpt:** "That's correct, Marlon has 18 female baby bunnies left in his hutch after giving 12 to Rodney, so when you calculate the"

- **Item:** 1081-903b7bbe-1fc9-4196-9c04-7f7d9c04d865_Sonnet
  - **Human:** False
  - **Judge:** True
  - **Reason:** Tutor directs student to think about the relationship between cups labeled and total post-its used.
  - **Excerpt:** "Great observation about the 220 cups and post-its, now let's think about how this relates to the total number of post-it"

- **Item:** 5032-7e6f6017-7c1d-4232-b9cb-13a563f9bf01_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor states the correction but does not direct student toward a next step or action.
  - **Excerpt:** "Since Jose and Rick eat lunch of the same price, Rick's lunch also cost $45."

### mistake_location (F1: 87.3%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor points to subtraction but misses the core error: 60% should apply to commission, not total earnings.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not clearly specify which calculation step contains the error or what was done incorrectly.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Gemini
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not pinpoint where the error occurs in the final sum (30+36 vs 18+36).
  - **Excerpt:** "That's a great start, but remember, the bunnies also gave birth to kittens, so we need to add those to the total number "

### mistake_identification (F1: 92.2%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor misidentifies the error; student's revised approach is actually incorrect per problem logic, not the subtraction step.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Gemini
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not identify the core mistake: using 30 instead of 18 in the final calculation.
  - **Excerpt:** "That's a great start, but remember, the bunnies also gave birth to kittens, so we need to add those to the total number "

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not identify the student's error: using 30 instead of 18 in the final sum.
  - **Excerpt:** 'Good, so how many bunnies does this mean that he has, when you add the kittens?'

### providing_guidance (F1: 92.8%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor provides a calculation but doesn't explain why subtracting from commission alone is correct.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor's guidance is vague and does not explain why the commission should be used or clarify the correct approach.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 2381-65fd981f-d994-4186-ab41-599d2712dee3_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor does not provide substantive guidance; merely asks student to add without addressing the error.
  - **Excerpt:** 'Good, so how many bunnies does this mean that he has, when you add the kittens?'

### coherence (F1: 95.6%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor's logic contradicts the problem: savings should come from commission, not total sales minus personal needs.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor's statement contradicts the earlier hint about multiplying by commission; the logic is unclear and inconsistent.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Phi3
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor praises the student and moves on despite the student's answer remaining mathematically incorrect.
  - **Excerpt:** "Great job! Now let's move on to the next problem together."

### answer_revealing_appropriate (F1: 96.1%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor directly states the final answer ($2880 - $1728) without guiding student to derive it.
  - **Excerpt:** "I see you've revised your calculation, but I still notice a small issue - shouldn't you subtract the amount allocated to"

- **Item:** 638345336_Llama31405B
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor directly states the answer (4 goes into 6 one time) rather than guiding student to discover it.
  - **Excerpt:** "I think there may be a mistake - remember, we're looking for how many times 4 fits into 6, and from our multiplication t"

- **Item:** 2162-38ea7f4f-0d0c-411f-80ae-f2401b2fdeb8_Phi3
  - **Human:** True
  - **Judge:** False
  - **Reason:** Tutor directly states the final corrected conversion (10 weeks, 0 days) without prompting student to recalculate.
  - **Excerpt:** 'To convert 70 days into weeks and days, divide the number of days by 7, which gives you 10 weeks and 0 days.\n\nTutor resp'

### human_likeness (F1: 96.6%)

- **Item:** 5752-777381cf-e363-4ea9-8638-482ac9ad22e5_Expert
  - **Human:** True
  - **Judge:** False
  - **Reason:** Response is terse and grammatically awkward; reads as a fragmented instruction rather than natural tutoring dialogue.
  - **Excerpt:** 'You should have done her commission subtract her personal need amount'

- **Item:** 5722-bc3658a3-ba86-43c0-a3f3-5a42e167e492_Phi3
  - **Human:** True
  - **Judge:** False
  - **Reason:** Generic boilerplate formula disconnected from the specific problem context and student input.
  - **Excerpt:** 'To calculate the percentage change, subtract the old value from the new value, divide by the old value, and multiply by '

- **Item:** 111-ddb33eb8-4cfa-41c8-9234-576ab1b32925_Llama318B
  - **Human:** True
  - **Judge:** False
  - **Reason:** The response is confusing and self-contradictory, sounding more like a confused bot than a natural tutor.
  - **Excerpt:** "You're right that $100 represents the amount Madeline spends on food for her dog each month, but I notice you initially "

