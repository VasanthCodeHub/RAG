<!-- Soft Suave · The AI Engineering League -->
# Week 7 Practical — Task Set D

## Race the claims agent against a fixed workflow

| | |
|---|---|
| Domain | Insurance claims |
| Week | 7 — Agent Loops — and When Not to Use Them |
| Module | M4 — Agents |
| Sat on | Week 8 · Monday |
| Marks | 100 |

> **This is an extension of the app you already built in Week 7.** It is not a build from scratch, and it tests only this week's concepts. Bring your numbers written down.


---

## 1. Problem statement

Your hand-built agent triages claims: pull the claim, read the adjuster notes, check the policy exclusions, compute the payable amount after the excess. The claims director asks the question you should have asked first — does this need to be an agent at all, or would four hard-coded steps be faster, cheaper and more auditable? Settle it with four numbers rather than an opinion.


---

## 2. Requirements

1. Add a third tool to the existing loop (compute_payout or get_adjuster_notes) whose description names exactly one job, uses an enum for the claim-status parameter, and does not overlap the two existing tool descriptions.
2. Re-implement the identical task as a fixed workflow — hard-coded steps, same tools, same model, same output contract. No loop.
3. Race agent vs workflow over the same 10 claims (including at least 3 where step 3 depends on what step 2 found, e.g. the notes reveal a flood cause that triggers an exclusion lookup) and report four numbers for each: pass rate, p50 latency, total tokens, cost per claim.
4. Enforce all four budgets in the loop — max iterations, max tokens, max cost, wall-clock — and include the log of one run that hits a budget and terminates cleanly instead of spinning.
5. Write the verdict applying the decision rule (does the path vary by input?), naming the specific claim class that forces an agent — or stating honestly that none of the 10 does.


---

## 3. Expected output

race.csv or a table with 8 numbers (4 per system), the workflow implementation, the budget-termination log, the third tool's description diff, and a verdict paragraph of under 150 words.


---

## 4. Evaluation rubric

| Criterion | Points |
|---|---|
| Four numbers for both systems over the same 10 inputs — pass rate, p50 latency, tokens, cost/task — reported as one comparable table | 30 |
| The workflow genuinely does the same task: same inputs, same output contract, same tools, no loop hiding inside it | 20 |
| All four budgets enforced in code plus a log showing one clean budget termination | 20 |
| Verdict applies the decision rule to a named input class and is consistent with your own numbers — a verdict contradicting the table scores 0 here | 20 |
| Third tool: one job, typed/enum parameters, no description overlap with existing tools | 10 |
| **Total** | **100** |

*Zero points for polish, UI, or "it works". This mirrors the House rubric: failure-finding and a number that moved are what score.*


---

## 5. Bonus challenge

Add a sliding window plus summarisation to the agent so it survives a claim with 30 turns of adjuster notes, and persist one fact (the policy's excess amount) across a full process restart. Re-run the race on 3 long claim files and name one detail summarisation destroyed and the claim it broke.


---

## 6. Submission checklist

- [ ] Agent and workflow both runnable by one command each
- [ ] race.csv / table with all 8 numbers over the same 10 claim numbers
- [ ] Log excerpt of the budget-triggered termination, showing which budget fired
- [ ] Diff of the third tool's description and parameter enums
- [ ] Verdict paragraph naming the claim class that does or does not need an agent


---

## 7. Common mistakes

- **Racing on 10 clean, fully-documented claims the agent already passes — the race is decided by the input mix, and without the exclusion-triggering and missing-notes cases the workflow wins by construction.**
- **Declaring the agent the winner on adaptability while your own table shows the workflow ahead on all four numbers — that is fashion overruling the rule you were taught.**
- **Counting only the final call's tokens; the loop re-sends the whole message list every lap, so per-lap tokens must be summed or the agent's cost is understated by multiples.**
- **Defining MAX_ITERS, MAX_TOKENS, MAX_COST as constants and never checking three of them in the loop — an unenforced budget is a comment with ambition.**
- **Fixing tool thrash by switching model or bolting 'use the correct tool' onto the system prompt instead of sharpening the overlapping get_claim / search_policy descriptions — the description bug stays, and it will resurface on the next tool you add.**


---

*Set D of 6. Sets A–F are equivalent in difficulty and objectives; only the domain differs.*





WEEK 8 · MODULE 4 — AGENTS
Agent Failure Modes & Trajectory Evals
Build week
Spot how your agent fails, defend it against tricks, and measure a fix to its worst problem.
What this week is about
Agents fail in new and sneaky ways — going in circles, picking the wrong tool, or reaching a right answer through a lucky wrong path that will break later. This week you learn to watch the whole path, not just the final answer, and to protect the agent from being tricked.
Why it matters
If the answer is right, why care how it got there?
A right answer reached by luck won't stay right. Next week the same lucky path gives a wrong answer, in production, to a customer.
What is “prompt injection”?
When hidden instructions inside a document or web page trick your agent into doing something it shouldn't. The agent can't tell your instructions from the text it reads.
Why give tools the least access possible?
Your agent is helpful and holds your keys. If something goes wrong, tightly-scoped tools keep the damage small.
What you'll learn
•	The common agent failures: loops, wrong tool, made-up inputs, giving up quietly
•	Judging the whole path, not just the final answer
•	The gap between “got the right answer” and “took the right steps” — and why it matters
•	Prompt injection: hidden instructions in documents or web pages that hijack your agent
•	Defending the agent: checking what it reads, and limiting what each tool can do
•	Fixing the worst failure and measuring that it actually went down
Topics covered
The exact concepts to study:
•	Agent failure modes   ·   Trajectory evaluation
•	Expected tool sequences   ·   Tool-choice accuracy
•	Outcome vs trajectory gap   ·   Cost per task (mean & p99)
•	Prompt injection (direct)   ·   Indirect prompt injection
•	Tool sandboxing & least privilege   ·   Output validation
•	OWASP LLM Top 10
Your task this week
Evaluated	Week 9 · Monday

Look at a batch of your agent's runs and find where it took a wrong path even when the answer looked right. Try a simple attack that hides an instruction in a document, then defend against it, and fix your top failure — measuring the improvement.
Choose your track
Same task, six different topics — so everyone works on their own version. Download whichever you're assigned.

	Topic	Task
A	Customer support tickets	Find the outcome-vs-trajectory gap in the ticket agent, then close one mode
B	Recipes & food	Find the outcome-vs-trajectory gap in the recipe agent, then close one mode
C	HR policy	Find the outcome-vs-trajectory gap in the HR agent, then close one mode
D	Insurance claims	Find the outcome-vs-trajectory gap in the claims agent, then close one mode
E	Developer documentation	Find the outcome-vs-trajectory gap in the docs agent, then close one mode
F	Legal contracts	Find the outcome-vs-trajectory gap in the contract agent, then close one mode
