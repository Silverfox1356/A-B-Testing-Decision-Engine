# 06 — Drills, numbers to memorize, and self-tests

Two categories of knowledge: things you **recall** and things you **derive**.
Do not try to memorize a derivation — practise producing it.

---

## Part 0 — Defending your CV bullet

Your CV says:

> Cut **experiment runtime 39%** (14 to 8.6 days) with **CUPED**, stripping
> variance from pre-period spend at ρ=0.62.

**Every figure in it is true and reproducible.** They come from the engine at
its *original* design, an **8% MDE**. The repo's default was later recalibrated
to a more realistic 3%, which is why the README's headline shows 98 days.
Notebook 02 §3 and the README table now show both designs side by side:

| Design MDE | Users/arm | ρ (seed 42) | Variance removed | Days: raw → CUPED |
|---|---|---|---|---|
| **+8% (CV)** | 70,229 | **0.625** | **39.0%** | **14.0 → 8.6** |
| +3% (repo default) | 487,847 | 0.611 | 37.3% | 97.6 → 61.1 |

Know these four things cold. Each one is a question an interviewer can ask.

**1. Why the repo says 98 days and your CV says 14.** "I first designed for an
8% MDE. Reading Kohavi, I realized most real effects are 1–3%, so I recalibrated
the default to 3%. That multiplies the sample size by about seven, from 14 days
to 98. CUPED's *percentage* gain doesn't change, because it depends on ρ, not on
the MDE: 39% at 8%, 37% at 3%. The README shows both." That's a story about
judgment, not a discrepancy. Tell it that way.

**2. ρ = 0.62 is one simulated experiment.** Across 20 random seeds, ρ is
0.61 ± 0.015 (range 0.59–0.64) at the 8% design's sample size, so the
*expected* reduction is 37.6% ± 1.8%. Seed 42 happened to draw 0.625 (16th of
20, high but not unusual), which gives 39%. If pressed: "39% in
that experiment; across seeds it's 37 ± 2%." Volunteering that is stronger
than defending 39 as a constant.

**3. What "cut runtime" means.** It is a *design-time, equal-precision*
comparison on simulated data. CUPED makes revenue per user as precise with 61%
of the users, so at fixed traffic the same precision arrives in 8.6 days
instead of 14. It is not a live experiment that was stopped early.

**4. The metric caveat — the one most likely to catch you.** The 39% is for
**revenue per user**. The 14-day design is sized for **conversion**, the
primary metric. On conversion CUPED removes less: **20%** with pre-period spend
(the engine's covariate) and **6%** with pre-period sessions. That's because of
the rare-binary ceiling from theory §3. So if the decision rests on conversion,
the runtime saving is closer to 20% (14 → 11.2 days). The honest answer:

> "The 39% is on revenue per user, the continuous metric. On the primary,
> conversion, it's 20%, because a rare binary outcome caps how much any
> covariate can explain. The runtime figure on my CV is the equal-precision
> saving for revenue; for an experiment that ships on conversion I'd quote 20%."

Say that *before* they find it. A candidate who volunteers the limit of their
own headline number is far more credible than one who gets caught on it.

**A 60-second version, start to finish:**

> "I sized the experiment at 80% power. For an 8% lift on a 3.5% conversion
> baseline that's 70,000 users per arm, about 14 days at 10,000 a day. CUPED
> regresses out pre-period spend. On revenue per user, the correlation was 0.62
> in that experiment, so ρ² of about 39% of the variance disappears, and the same
> precision arrives in 8.6 days instead of 14. Two honest caveats. That's on
> revenue; conversion only gains 20%, because rare binary outcomes cap the
> correlation. And I later recalibrated to a more realistic 3% MDE, which pushes
> the design to 98 days, but CUPED still removes 37%, because the percentage
> depends on ρ, not on the effect size."

---

## Part 1 — Numbers to have at your fingertips

### Design

| Quantity | Value |
|---|---|
| Baseline conversion | 3.5% |
| MDE | +3% relative → 3.605% (Δ = 0.00105 ≈ 0.1pp) |
| α | 0.05 (two-sided for sizing) |
| Target power | 80% |
| **Sample size** | **487,847 per arm, 975,694 total** |
| Traffic assumption | 10,000 users/day |
| **Duration** | **~98 days (97.6)** |

Why 3% and not 8%: the project was recalibrated to a realistic effect size.
Typical winning e-commerce tests lift conversion by low single digits, and
Kohavi et al. note most real effects are 1–3%. 8% was an optimistic demo value
that made the primary test look cheap (70,229/arm, 14 days). Halving an MDE
quadruples n; going from 8% to 3% should multiply it by about (8/3)² ≈ 7.1. The
actual ratio is 487,847 / 70,229 ≈ 6.9, slightly less, because the variance
terms in the formula shrink a little as p₂ moves closer to p₁.

### Standard normal quantiles (know these cold)

| | Value |
|---|---|
| z₀.₉₇₅ (two-sided α = 0.05) | 1.960 |
| z₀.₉₅ (one-sided α = 0.05) | 1.645 |
| z₀.₈₀ (80% power) | 0.842 |
| z₀.₉₀ (90% power) | 1.282 |
| (1.96 + 0.84)² | 7.84 ≈ 8 |

### Notebooks 01–02: one simulated experiment (seed 42, 487,847/arm)

| Metric | Value |
|---|---|
| Control conversion | 3.4876% |
| Treatment conversion | 3.6516% |
| Absolute lift | +0.164pp, 95% CI [+0.090, +0.238] (truth: +0.105pp) |
| Relative lift | +4.70% (truth: +3%) — one draw, overstating by >50% |
| z / p | 4.365 / < 0.0001 |

### The engine on the designed experiment (seed 204, 487,847/arm) — verdict INVESTIGATE

| Metric | Raw | With CUPED | Status |
|---|---|---|---|
| Conversion (primary) | +0.110pp, p = 0.0016 | **+0.115pp, p = 0.0003** | PASS |
| Revenue per user | +$0.048, p = 0.136 | **+$0.056, p = 0.054** | FAIL (not significant) |
| AOV guardrail | −$1.37, bound −$2.73 vs margin −$1.77 | not adjusted (unsafe) | INCONCLUSIVE, **70% power** |
| Error-rate guardrail | +0.07pp vs +0.5pp margin | not adjusted (no covariate) | PASS (within-margin harm) |

Converters per arm ≈ 17,000. Control AOV mean / SD ≈ $89 / $77.

### CUPED

| Case | ρ | Variance reduction | CI narrowing |
|---|---|---|---|
| Synthetic revenue (covariate: pre-period spend, seed 42) | 0.611 | 37.3% | 20.8% |
| Synthetic conversion (covariate: **pre-period spend**, used by the engine) | 0.430 | 18.5% | 9.7% |
| Synthetic conversion (covariate: pre-period sessions, notebook 02) | 0.245 | 6.0% | 3.0% |
| Real spend (covariate: prior-year history) | 0.0195 | 0.038% | 0.02% |

In the engine at seed 204 the two success metrics lose 37.9% (revenue) and
18.6% (conversion) of variance — the same story, a different draw.

**Why the engine uses pre-period spend for conversion too:** spend loads far
more heavily on the frequency latent that drives conversion than session count
does, so it is the better covariate on *both* metrics (19% vs 6%). Notebook 02
keeps the sessions covariate to contrast a strong and a weak one.

**Guardrail covariates: none, for two different reasons.** AOV is converters-only,
and CUPED behind a post-treatment filter is *biased* — +$0.42 against a $1.76
margin when the true effect is zero (14 MC SE over 400 sims), biased toward
passing. `MetricSpec` raises on it. The error rate has no useful covariate
(ρ = 0.002) and already has ~100% power.

**The CUPED story to tell (memorize this one):** CUPED cut revenue's p-value
from 0.136 to 0.054 and its standard error by about a fifth, and it was still
not enough. A six-cent lift on a heavy-tailed metric is hard to detect even
with variance reduction, and the memo refuses to book revenue as a result.

θ values: revenue 0.0589, conversion (sessions) 0.0174, real-data 0.001035.
Duration effect: revenue 97.6 → 61.1 days; conversion 97.6 → 91.7 days.

### Guardrails

| | AOV | Checkout error rate |
|---|---|---|
| Margin | 2% relative (≈ $1.77) | 0.5pp absolute |
| Population | converters only (~3.5%) | all users |
| SE at 488k/arm | ≈ $0.82 | ≈ 0.00023 |
| Margin ÷ SE | 2.16 | 22 |
| **Power at 488k/arm** | **~70%** | **~100%** |
| n for 80% power | ~650k/arm (~1.3×) | already there |
| n used in demos | 900k/arm (~1.8×, ~90% power) | — |

**The point to make:** ~650k/arm for 80% AOV power is the *same* under the old
8% calibration and the new 3% one. It depends on the margin and order-value
variance, not on the MDE. Only the ratio to the primary changed: ~9× at 8%,
~1.3× at 3%.

### Real data (Hillstrom)

| | Value |
|---|---|
| Total customers | 64,000 (3 arms) |
| Used | Womens E-Mail vs No E-Mail, ~21k per arm |
| Conversion effect | +0.311pp (p = 0.0001) |
| Visit effect | +4.52pp (p < 0.0001) |
| Spend effect | +$0.424, worst-case bound +$0.210 |
| Margin | 10% of control mean = $0.065 |
| Guardrail power | **13%** |
| Verdict | **INVESTIGATE** |
| Control spend mean / SD | $0.65 / $11.6 |

### Sample ratio mismatch

| | Value |
|---|---|
| Test | Chi-square goodness of fit, 2 cells, 1 df |
| Gate | p < 0.0005 (`config.SRM_ALPHA`), not 0.05 |
| Why | Runs on every experiment; 0.05 discards 1 healthy test in 20 |
| Demo mismatch | 49/51 at 975,694 users → chi² = 390, **p = 7e-87** |
| A 49.9/50.1 split at the same n | p ≈ 0.05 — a fair coin does this 1 time in 20 |
| G3d false-alarm rate | 0.00035 over 20,000 fair-coin sims |
| G3d detection | 100% on a 49/51 bug |
| Hillstrom | 21,387 / 21,306 → p = 0.695, passes cleanly |
| On failure | verdict INVALID, **zero metrics reported** |

### Business

| | Value |
|---|---|
| Conversion lift | +0.11pp (~+3% relative), significant |
| Extra checkouts/year | ≈ 4,000 |
| Revenue per user lift | +$0.06, **not** significant (p = 0.054) |
| Dollar figure booked | **none** — deliberately, because revenue is not established |
| Recommendation | Phased rollout (25 → 50 → 100%) with auto-pause rule |

### Code

| | Value |
|---|---|
| Total Python | ~1,580 lines, 11 files |
| Unit tests | 26, ~5 seconds, all passing |
| Validation gates | 11 (G1a–d, G2a–c, G3a–d) |
| Simulations per gate | 1,000–5,000 |
| `src/cuped.py` | 51 lines — the whole method |
| `src/decision_engine.py` | 233 lines — the largest module |

---

## Part 2 — Derivations to reproduce from memory

Do each on blank paper, timed. If you need notes, you are not ready.

### Drill 1 — Two-proportion sample size (target: 5 minutes)
Start from "we reject when the observed difference exceeds the critical value."
End at the boxed formula. **The checkpoint that matters:** you must explain why
there are two *different* standard errors — pooled under H₀ for the critical
value, unpooled under H₁ for the estimator's distribution.

### Drill 2 — CUPED θ and variance reduction (target: 3 minutes)
Expand Var(Y − θX), differentiate, set to zero, solve, substitute back, and show
the result collapses to Var(Y)(1 − ρ²).

### Drill 3 — CUPED unbiasedness (target: 2 minutes)
Write the difference in adjusted means. Show the centring constant cancels.
Invoke randomization for E[X̄_T] = E[X̄_C]. Conclude.

### Drill 4 — Non-inferiority power (target: 3 minutes)
Start from "we pass when the one-sided bound clears the margin." Condition on
Δ = 0. Rearrange into Φ(m/SE − z_{1−α}). Then say in words what it depends on:
the margin-to-noise ratio, a property of the design.

### Drill 5 — Why guardrails aren't alpha-corrected (target: 90 seconds, verbal)
No math — the risk-asymmetry argument, cleanly, plus the perverse-incentive
point about adding guardrails to loosen the others.

### Drill 5b — Why the SRM gate uses 0.0005 (target: 60 seconds, verbal)
The false-alarm-budget argument: the check runs on every experiment, a real SRM
is orders of magnitude more extreme anyway, and a check that cries wolf gets
deleted. Then the numbers: 7e-87 on the demo, 0.00035 false-alarm rate in G3d.

### Drill 5c — Why CUPED is refused on AOV (target: 60 seconds, verbal)
Unbiasedness needs E[X̄_T] = E[X̄_C], randomization gives it only on the full
randomized population, converters-only is post-treatment, so the arms' covariate
means genuinely differ. Then the number: +$0.42 against a $1.76 margin, biased
toward passing.

### Drill 6 — The selection bias story (target: 90 seconds, verbal)
Symptom → mechanism → name → fix → lesson carried forward. Practise until it
flows without backtracking; this is your headline anecdote.

### Drill 7 — The rule-of-thumb sample size (target: 60 seconds, mental)
Given a baseline and a relative MDE, produce an approximate n out loud using
n ≈ 16p(1−p)/Δ². Practise on: 2% baseline +10% relative; 20% baseline +5%
relative; 0.5% baseline +20% relative.

*(Answers: Δ=0.002 → ≈78,400; Δ=0.01 → ≈25,600; Δ=0.001 → ≈79,600.)*

### Drill 8 — Explain the whole project at three altitudes (target: 30s / 2min / 5min)
Same content, three depths, on command. Practise switching mid-answer when
someone says "go deeper" or "simpler."

---

## Part 3 — Self-test: can you answer without notes?

Score yourself. Any "no" is your next study session.

**Architecture**
- [ ] Draw the full dependency graph from memory
- [ ] Name every file and its one-sentence purpose
- [ ] Explain why `src/cuped.py` imports nothing from the project
- [ ] Explain why config values are function *defaults*, not read inside bodies
- [ ] Explain why `evaluate_experiment` returns data instead of printing

**Power**
- [ ] Derive the sample size formula
- [ ] Explain the two different standard errors in it
- [ ] State the 1/Δ² relationship and what halving the MDE does
- [ ] Estimate a sample size mentally with the rule of thumb
- [ ] Explain the two-sided-sizing / one-sided-testing inconsistency

**CUPED**
- [ ] Derive θ
- [ ] Derive the variance reduction
- [ ] Prove unbiasedness
- [ ] Explain pooled vs per-arm θ
- [ ] Explain 37% vs 6% *two different ways*
- [ ] Explain why CI narrowing ≠ variance reduction
- [ ] Explain the real-data 0.04% result
- [ ] Define CUPAC

**Decisions**
- [ ] Justify one-sided superiority tests
- [ ] Explain non-inferiority to a non-statistician
- [ ] Explain why guardrails aren't alpha-corrected (90 seconds, fluent)
- [ ] Explain BH step-up including the rescue case
- [ ] State the verdict precedence and why harm comes first
- [ ] Explain `inferior` vs `harm_detected`
- [ ] Defend reporting guardrail power against the post-hoc power critique
- [ ] Argue *both sides* of the INVESTIGATE-on-low-power choice

**Simulation**
- [ ] Explain the probit threshold trick and what two properties it buys
- [ ] Tell the selection-bias story in 90 seconds
- [ ] Name five things the simulation doesn't model
- [ ] Explain the G2a tautology problem and how you avoided it
- [ ] Explain why tolerances are in Monte-Carlo SE units

**The new layer**
- [ ] Explain what an SRM is and why it invalidates everything
- [ ] Justify 0.0005 against the project's own 0.05
- [ ] Explain why INVALID withholds all metrics
- [ ] Explain why INVALID is separate from DO NOT SHIP
- [ ] Explain why CUPED is refused behind a post-treatment filter, with the number
- [ ] Explain what CUPED bought revenue (0.136 → 0.054) and why it still isn't significant
- [ ] Explain why ~650k/arm for 80% AOV power didn't change when the MDE did

**Weaknesses**
- [ ] Name five genuine weaknesses unprompted
- [ ] Say what you'd build next, in priority order, with effort estimates
- [ ] Name the biggest gap (SRM) before being asked

---

## Part 4 — Mock interview scripts

### Script A: the 5-minute project pitch
1. One sentence on what it is (15s)
2. The three things it does and why each matters (90s)
3. One concrete result — the guardrail power finding (60s)
4. One honest limitation and what you'd do about it (45s)
5. "Happy to go deeper on any of those" (5s)

Practise this until it is automatic. It is your opening in most interviews and
it sets the agenda for everything that follows.

### Script B: the deep-dive on one component
When they say "tell me more about CUPED" —
1. What problem it solves (20s)
2. The formula and the intuition (30s)
3. The derivation, if they want it (2min)
4. Your actual numbers, synthetic and real (30s)
5. The limitation and the extension — CUPAC (30s)

### Script C: handling a challenge
When they push back on something:
1. **Acknowledge the substance first.** "That's fair" / "You're right that…"
2. State your reasoning.
3. State when their alternative would be better.
4. If they are simply right, say so and say what you'd change.

Never get defensive. An interviewer testing whether you can be moved by an
argument is testing something more important than whether you were right.

---

## Part 5 — Things to say that signal seniority

Deploy naturally, not as a checklist.

- "The correction changes no verdict here — at two metrics, BH's second
  threshold is the uncorrected α. The value is that the structure scales."
- "That's not post-hoc power in the discredited sense, but there is a fair
  caveat, which is that I plug in the realized SE."
- "I'd use the library in production. I wrote it out here to show I understand
  it, and then used the library as an independent oracle."
- "There's a legitimate argument on the other side of that, which is…"
- "The generator can't produce a sample ratio mismatch, so I can't demonstrate
  SRM detection. That's the first thing I'd add."
- "The tolerance is four Monte-Carlo standard errors, not a hardcoded number."
- "Statistical significance and business significance are different things, and
  this is the line of code where the engine knows it."
- "Absence of evidence isn't evidence of absence — that's the whole reason the
  guardrails are non-inferiority tests."

## Part 6 — Things never to say

- "The p-value is the probability the result is due to chance." (It isn't.)
- "We accepted the null hypothesis." (You fail to reject.)
- "The experiment proved there's no difference." (Never provable.)
- "95% chance the true value is in this interval." (Frequentist CIs don't say
  that.)
- "CUPED made the effect bigger." (It reduces *variance*; the estimate is
  unbiased and shouldn't systematically move.)
- "I used machine learning." (You didn't, and this project is better for it.)
- Any overclaim about BH mattering at m = 2, or any dollar figure for the revenue
  lift — it is not statistically established.
