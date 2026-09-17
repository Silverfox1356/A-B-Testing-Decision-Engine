# Master plan: how to learn this project end to end

You are preparing to defend this project in an interview. That means two
separate skills:

1. **Recall** — you can state what the code does, where, and why.
2. **Derivation** — you can rebuild the reasoning live, on a whiteboard, when
   the interviewer pushes past your prepared answer.

Recall alone fails. Every interviewer's second question is "why?", and their
third is "what if?". The plan below is built so that by the end you can answer
all three levels for every part of the repo.

---

## The one-sentence version of the project

> A/B testing decision engine that (a) sizes an experiment before it runs,
> (b) uses pre-experiment data to cut metric variance so the experiment can be
> shorter, and (c) turns the results into a SHIP / DO NOT SHIP / INVESTIGATE
> verdict that treats success metrics and guardrail metrics with deliberately
> different statistical risk postures — validated on simulation and then run
> unchanged on a real 64,000-user experiment.

Memorize that. It is your opening answer to "tell me about your project."

---

## The five things this project is actually about

Interviewers do not care that you called `scipy`. They care that you understand
these five ideas. Everything in the repo exists to demonstrate one of them.

| # | Idea | Where it lives | The question it answers |
|---|---|---|---|
| 1 | Power analysis | `src/power.py` | How big must the experiment be *before* we run it? |
| 2 | Variance reduction (CUPED) | `src/cuped.py` | How do we get the same precision from less traffic? |
| 3 | Asymmetric risk: Type I vs Type II | `src/tests_stats.py` | Success metrics fear false positives; guardrails fear false negatives. Why do they get different treatment? |
| 4 | Non-inferiority testing | `src/tests_stats.py` | How do you *prove* something did not get worse? (You cannot prove a null.) |
| 5 | Post-treatment conditioning bias | `data/generate_data.py`, notebook 04 | Why is "average order value" a dangerous guardrail? |

Idea 5 is your differentiator. Almost nobody at the junior level can explain
selection bias from conditioning on a post-treatment variable, and this project
has a real war story about it. Save it for when you need to impress.

---

## Study schedule (7 sessions, ~2–3 hours each)

Do them in order. Each session ends with an **exit test** — if you cannot pass
it without notes, repeat the session before moving on.

### Session 1 — The map
**Read:** `docs/study/01_architecture.md`, then `config.py`, then `README.md`.

Goal: you can draw the dependency graph from memory and explain what each of
the 11 source files is for, in one sentence each.

**Exit test:** On blank paper, draw every file in the repo and every import
arrow between them. Then explain, without looking, why `config.py` exists
rather than putting constants where they are used.

---

### Session 2 — Power analysis from first principles
**Read:** `docs/study/02_theory.md` §1–§2, then `src/power.py`, then
notebook 01.

Goal: derive the two-proportion sample size formula from scratch. Not memorize
it — *derive* it, from "reject when the observed difference exceeds the
critical value."

**Exit test:** Whiteboard the derivation in under 5 minutes. Then answer: "I
halve the MDE. What happens to sample size, and why exactly that factor?"

---

### Session 3 — CUPED
**Read:** `docs/study/02_theory.md` §3, then `src/cuped.py` (only 51 lines —
read every one), then notebook 02.

Goal: derive `θ* = Cov(Y,X)/Var(X)` by minimizing the adjusted variance, and
derive `Var(Y_cuped) = Var(Y)(1 − ρ²)` from it. Then explain in plain English
why the estimator stays unbiased.

**Exit test:** "Why did CUPED cut revenue variance by 39% but conversion
variance by only 6%?" Answer it twice: once with the correlation argument, once
with the law-of-total-variance argument. Both are in §3.

---

### Session 4 — The decision layer
**Read:** `docs/study/02_theory.md` §4–§5, then `src/tests_stats.py`
(all 216 lines), then notebook 03.

Goal: the three tests — superiority, non-inferiority, Benjamini-Hochberg —
and above all the *risk asymmetry* argument for why guardrails are not
alpha-corrected.

**Exit test:** "Why not apply BH to the guardrails too? Isn't that
inconsistent?" You need a crisp 60-second answer. It is the single most likely
follow-up question this project invites.

---

### Session 5 — Architecture and the code walkthrough
**Read:** `docs/study/03_code_walkthrough.md` end to end, with the files open
beside it.

Goal: you can explain any function's contract, its inputs, its edge cases, and
one alternative implementation you rejected.

**Exit test:** Pick three random functions. For each, state: what it returns,
what would break if a caller passed bad input, and how you would test it.

---

### Session 6 — Decisions, alternatives, and honest weaknesses
**Read:** `docs/study/04_decisions_and_alternatives.md`.

Goal: for every design decision, you know the alternative you rejected and the
reason. And you know the project's genuine weaknesses before the interviewer
finds them.

**Exit test:** Name five things wrong with this project and what you would do
about each. Volunteering a weakness you have already thought through reads as
seniority; being caught by one reads as inexperience.

---

### Session 7 — Drilling the question bank
**Read + rehearse:** `docs/study/05_interview_qa.md` and
`docs/study/06_drills_and_numbers.md`.

Goal: answers out loud, timed, no notes. Record yourself if you can stand it.

**Exit test:** 20 random questions from the bank, answered aloud, under 90
seconds each.

---

## How to use the four notebooks

The notebooks are the **narrative** of the project; `src/` is the **machinery**.
In an interview you tell the notebook story and, when pressed, drop into the
machinery.

| Notebook | The story it tells | The one number to remember |
|---|---|---|
| 01 power analysis | "Before running anything, we asked how much traffic a +8% lift needs." | 70,229 users/arm = 14 days |
| 02 CUPED | "Then we made the same traffic go further." | 39% variance reduction on revenue, 6% on conversion |
| 03 decision engine | "Then we turned results into a decision that respects risk." | SHIP / DO NOT SHIP / INVESTIGATE |
| 04 real data | "Then we proved it survives contact with real data." | Verdict INVESTIGATE at 13% guardrail power |

---

## How to talk about it: the 3-layer answer

Every question has three possible depths. Read the room and pick one.

- **Layer 1 (30 seconds, non-technical stakeholder):** what it does and why it
  matters to the business.
- **Layer 2 (2 minutes, hiring manager):** the method, the trade-off, the
  result.
- **Layer 3 (5+ minutes, senior DS on the panel):** the math, the assumptions,
  the failure modes, the alternatives.

Example, on CUPED:

- L1: "We used customers' past behaviour to cancel out noise, so the experiment
  needed 39% less traffic for the same confidence."
- L2: "CUPED regresses the outcome on a pre-experiment covariate and subtracts
  the predictable part. Because the covariate predates randomization, treatment
  cannot affect it, so the estimator stays unbiased while variance drops by a
  factor of 1 − ρ²."
- L3: the full derivation, why pooled θ, the binary-metric correlation ceiling,
  and why the real-data case only got 0.04%.

Practice moving between layers on command. Interviewers test this deliberately:
"explain it to me like I'm the VP of Product" is a real question.

---

## The traps to rehearse for

These are the questions most likely to break an unprepared candidate on *this*
specific project.

1. "You simulated the data. Doesn't that mean you just got the answer you
   designed for?" — See `04_decisions_and_alternatives.md` §Validation.
2. "Post-hoc power is discredited. Why are you reporting power?" — This is the
   sharpest available critique. §4 of the theory doc has the defence, and it is
   a genuinely subtle distinction.
3. "You applied BH to two metrics. Is that even doing anything?" — Honest
   answer: barely, and you should say so, then explain why the *structure*
   matters more than the correction at m=2.
4. "Your engine says INVESTIGATE when the guardrail actually passed. Isn't that
   overconservative?" — There is a legitimate counterargument. Know both sides.
5. "Where's your sample ratio mismatch check?" — It is missing. Own it.

---

## Reading order summary

```
00_master_plan.md            <- you are here
01_architecture.md           <- the map: files, layers, data flow
02_theory.md                 <- the statistics, derived not quoted
03_code_walkthrough.md       <- every file, every function, line by line
04_decisions_and_alternatives.md  <- why this, not that; and what's weak
05_interview_qa.md           <- ~90 questions with model answers
06_drills_and_numbers.md     <- what to memorize, what to derive
```
