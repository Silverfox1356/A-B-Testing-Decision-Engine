# Study guide

Everything needed to learn this project end to end and defend it in an
interview: architecture, statistical theory derived from first principles, a
complete code walkthrough, the design decisions and their alternatives, an
honest account of the weaknesses, and a rehearsable question bank.

**Calibration.** Every number in these notes comes from the current config: a
**+3% MDE** on a 3.5% baseline, which needs **487,847 users per arm (~98 days)**.
An earlier version of the project used an optimistic 8% MDE (70,229 users/arm,
14 days). Where an old figure is mentioned, it is labelled as the earlier
calibration and kept on purpose, because how the numbers changed is itself
worth understanding (see `02_theory.md`, "Guardrail power is expensive").

Read in order:

| File | What it covers |
|---|---|
| [`00_master_plan.md`](00_master_plan.md) | The learning roadmap: 7 study sessions with exit tests, the five core ideas, how to pitch the project at three levels of depth |
| [`01_architecture.md`](01_architecture.md) | Layers, the exact import graph, why each module is shaped the way it is, end-to-end data flow |
| [`02_theory.md`](02_theory.md) | The statistics, derived not quoted: power analysis, CUPED, non-inferiority, Benjamini-Hochberg, post-treatment conditioning bias, the simulation design |
| [`03_code_walkthrough.md`](03_code_walkthrough.md) | Every file, every function, line by line — including edge cases, failure modes and the reasoning behind each implementation choice |
| [`04_decisions_and_alternatives.md`](04_decisions_and_alternatives.md) | Every decision with the alternatives rejected and why, plus 11 genuine weaknesses and a prioritized roadmap |
| [`05_interview_qa.md`](05_interview_qa.md) | ~95 questions with model answers, from basics to curveballs, plus a rapid-fire table |
| [`06_drills_and_numbers.md`](06_drills_and_numbers.md) | Numbers to memorize, derivations to reproduce from memory, a self-test checklist, and mock interview scripts |

If you read only one thing before an interview: `06_drills_and_numbers.md`
Part 1 (the numbers) and `05_interview_qa.md` Section 11 (rapid fire).
