# 06 — Drills, numbers to memorize, and self-tests

Two categories of knowledge: things you **recall** and things you **derive**.
Do not try to memorize a derivation — practise producing it.

---

## Part 1 — Numbers to have at your fingertips

### Design

| Quantity | Value |
|---|---|
| Baseline conversion | 3.5% |
| MDE | +8% relative → 3.78% (Δ = 0.0028 = 0.28pp) |
| α | 0.05 (two-sided for sizing) |
| Target power | 80% |
| **Sample size** | **70,229 per arm, 140,458 total** |
| Traffic assumption | 10,000 users/day |
| **Duration** | **14 days** |

### Standard normal quantiles (know these cold)

| | Value |
|---|---|
| z₀.₉₇₅ (two-sided α = 0.05) | 1.960 |
| z₀.₉₅ (one-sided α = 0.05) | 1.645 |
| z₀.₈₀ (80% power) | 0.842 |
| z₀.₉₀ (90% power) | 1.282 |
| (1.96 + 0.84)² | 7.84 ≈ 8 |

### The observed experiment (seed 42 / 204, 70,229 per arm)

| Metric | Value |
|---|---|
| Control conversion | 3.5427% |
| Treatment conversion | 3.8588% |
| Absolute lift | +0.3161pp, 95% CI [+0.119, +0.514] |
| Relative lift | +8.92% |
| z / p | 3.138 / 0.0017 |
| Revenue per user effect | +$0.18 |
| Converters per arm | ~2,400 |
| AOV control mean / SD | ~$59 / ~$52 |

### CUPED

| Case | ρ | Variance reduction | CI narrowing |
|---|---|---|---|
| Synthetic revenue (covariate: pre-period spend) | 0.625 | 39.0% | 21.9% |
| Synthetic conversion (covariate: pre-period sessions) | 0.251 | 6.3% | 3.2% |
| Real spend (covariate: prior-year history) | 0.0195 | 0.038% | 0.02% |

θ values: revenue 0.0433, conversion 0.0182, real-data 0.001035.
Duration effect: revenue 14 → 8.6 days; conversion 14 → 13.2 days.

### Guardrails

| | AOV | Checkout error rate |
|---|---|---|
| Margin | 2% relative (≈ $1.18) | 0.5pp absolute |
| Population | converters only (~3.5%) | all users |
| SE at 70k/arm | ≈ $1.44 | ≈ 0.00059 |
| Margin ÷ SE | 0.82 | 8.4 |
| **Power at 70k/arm** | **20%** | **~100%** |
| n for 80% power | ~650k/arm (~9×) | already there |
| n used in demos | 900k/arm (~91% power) | — |

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

### Business

| | Value |
|---|---|
| Revenue per user lift | +$0.18 |
| Annualized | ≈ $660,000/year |
| Extra checkouts/year | ≈ 11,600 |
| Recommendation | Phased rollout (25 → 50 → 100%) with auto-pause rule |

### Code

| | Value |
|---|---|
| Total Python | ~1,580 lines, 11 files |
| Unit tests | 13, ~1 second, all passing |
| Validation gates | 10 (G1a–d, G2a–c, G3a–c) |
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
- [ ] Explain 39% vs 6% *two different ways*
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

- "The correction changes no verdict here — with two metrics the thresholds are
  nearly identical to no correction. The value is that the structure scales."
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
- Any overclaim about BH mattering at m = 2, or about the $660k being a forecast
  rather than an extrapolation.
