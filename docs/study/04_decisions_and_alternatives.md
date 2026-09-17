# 04 — Every decision, the alternatives, and the honest weaknesses

Interview reality: *what* you built is worth maybe 20% of the score. *Why you
chose it over the alternative* is worth the rest. This document is the answer
key.

Format for each: **Decision → Alternatives considered → Why this one → When the
alternative would win.**

---

## Part A — Project-level decisions

### A1. Simulated data first, real data second

**Alternatives:** (a) real data only; (b) simulation only.

**Why:** with real data you never know the true effect, so you cannot verify
that a *method* has the error rates it claims. Simulation lets you set the truth
and check that the pipeline recovers it — 80% power really is 80%, α really is
5%, CUPED really is unbiased. But simulation alone is self-confirming: you can
always generate data your method handles. Doing both gives you the validation
that only simulation provides *and* the credibility that only real data
provides.

**Order matters:** validate on simulation, then transfer unchanged to real data.
Notebook 04 changed zero lines of engine code, which is itself the proof that
the abstraction was right.

**When the alternative wins:** if the goal were a *finding* about checkout flows
rather than a *method*, simulation would be worthless.

**The pushback to expect:** *"You designed the data to make your method look
good."* Answer: the generator is a test harness, not evidence. And the real-data
result is deliberately unflattering — CUPED delivered 0.04% instead of 39%, and
the engine returned INVESTIGATE rather than a clean SHIP. If the goal were
flattery, those results would have been buried.

---

### A2. Hand-rolled formulas rather than library calls

**Alternatives:** call `statsmodels.stats.power` and `statsmodels.stats.proportion`
throughout.

**Why:** the project's purpose is to demonstrate understanding. A library call
demonstrates that you can read documentation. Writing the formula out, with the
derivation in the docstring, demonstrates you know what it means — and it makes
every step auditable by a statistician who does not read Python.

Critically, the library is then repurposed as an **independent oracle**:
`test_sample_size_matches_statsmodels` and gate G1c cross-check against
`NormalIndPower`. That is stronger than either approach alone, because the two
implementations use genuinely different parameterizations (statsmodels uses the
arcsine-transformed Cohen's *h* effect size), so agreement to within 1% is
meaningful independent confirmation rather than a tautology.

**When the alternative wins:** in production. Nobody should hand-roll power
analysis in a system real decisions depend on — use the maintained library and
spend your review budget elsewhere. Say this explicitly; it shows you know the
difference between a portfolio project and production code.

---

### A3. Four phases with validation gates between them

**Alternatives:** build everything, test at the end.

**Why:** each phase's correctness is a precondition for the next. If the power
analysis is wrong, every sample size downstream is wrong, and you would not find
out until the verdicts looked odd. Gating each phase means a failure is localized
to the ~300 lines you just wrote.

This is also what caught the selection-bias bug (C1 below): the Phase 3 SHIP
scenario refused to pass, and because Phases 1 and 2 were already gated, the
fault had to be in the new layer — or in the generator. It was the generator.

**Cost to acknowledge:** the full gate suite takes several minutes of
simulation. That is why there are *two* test tiers — 1-second unit tests for the
inner loop, minutes-long simulation gates for phase transitions.

---

### A4. Two test tiers: unit tests AND simulation gates

**Alternatives:** unit tests only; simulation gates only.

**Why:** they test different kinds of claim.

- Unit tests check **function-level properties**: does θ recover a known slope,
  does BH produce the textbook answer, is the generator reproducible. Fast,
  deterministic, run constantly.
- Simulation gates check **distributional properties of the whole pipeline**:
  is the false-positive rate really 5% over 1,000 experiments, is the estimator
  really unbiased, does BH really control FDR. These are statements about
  *repeated sampling* and cannot be asserted from a single run.

You cannot unit-test "this design has 80% power." You can only measure it.

**The detail that impresses:** G2b's tolerance is `4 * std / sqrt(n_sims)` —
four Monte-Carlo standard errors — not a hardcoded number. A stochastic
assertion needs a tolerance in SE units, or it either flakes or hides real bias
depending on luck.

---

## Part B — Statistical decisions

### B1. One-sided superiority for success metrics

**Alternatives:** two-sided tests (the default everywhere).

**Why:** the decision is binary — ship or don't. "No effect" and "harm" produce
the *same action*, so they belong in the same null hypothesis. A two-sided test
spends half its α detecting a direction you would never act on differently.
One-sided puts all of α where the decision lives.

**When the alternative wins:** when you are *estimating* rather than deciding,
or when a negative result would itself be a finding worth publishing.

**The fair criticism:** one-sided tests are widely abused to manufacture
significance after seeing the data. The defence here is that the direction is
fixed by the decision rule — the feature ships only on improvement — before any
data exists, and it is written into the `MetricSpec` as `direction="increase"`.

**The inconsistency to own:** `required_sample_size_per_arm` sizes with
`z_{1-α/2}` (two-sided) while the decision uses one-sided tests. This is
conservative — it demands more users than one-sided sizing would, so achieved
one-sided power exceeds 80%. Erring toward over-powered is safe, but the clean
version would be one-sided throughout. Volunteer this.

---

### B2. Non-inferiority for guardrails rather than "check p > 0.05"

**Alternatives:** two-sided test, ship if not significant.

**Why:** *absence of evidence is not evidence of absence.* "p = 0.4, so no harm"
is a failure to detect, and it rewards underpowered experiments — run a tiny
test and every guardrail passes. That incentive is catastrophic.

Non-inferiority makes harm the **null** and requires evidence to reject it. The
burden of proof now sits on the side of safety, where it belongs, and a small
sample produces *inconclusive* rather than a false all-clear.

**The cost:** you must choose a margin, which is a business judgement made
before the data. Real teams find this uncomfortable, which is precisely why it
is valuable — it forces the tolerance conversation to happen at design time.

---

### B3. DO-NOT-SHIP triggers on `inferior`, not on `harm_detected`

**Alternatives:** block on any statistically significant degradation.

**Why:** the margin exists *because* the business declared degradation below it
acceptable. At n = 1.8M, the true +0.1pp error-rate rise is overwhelmingly
significant and completely irrelevant — it sits well inside the +0.5pp tolerance
agreed before launch. Blocking on significance would make every large experiment
unshippable and would mean more traffic makes you *less* able to ship, which is
absurd.

`harm_detected` is retained as **informational** and surfaces in the report as
"significant but within-margin degradation (accepted cost)" — the reader learns
the harm is real without it blocking anything.

**The one-line version:** statistical significance and business significance are
different things, and this is the line of code where the project knows it.

---

### B4. BH on success metrics only; guardrails uncorrected

**Alternatives:** (a) correct everything; (b) correct nothing; (c) Bonferroni.

**Why not correct guardrails:** correction makes it harder to reject a null. For
a guardrail the null is "there is harm," so correcting makes it harder to
establish *safety*. Worse, it creates a perverse incentive — an analyst who
wants to ship is rewarded for adding more guardrails, because each one loosens
the others.

The structural reason: correction controls **Type I** inflation. Guardrails fear
**Type II**. Suppressing the error you don't fear at the cost of the one you do
is backwards. Guardrail risk is instead disclosed as **power**, with a floor
that triggers INVESTIGATE.

**Why BH not Bonferroni:** success metrics are a discovery family where a few
false leads are recoverable, so FDR ("at most 5% of my declared wins are
spurious") is the right error rate. Bonferroni's FWER guarantee is for settings
where a single false positive is catastrophic. Bonferroni also loses power fast
as m grows.

**The honest limitation:** with m = 2 success metrics, BH thresholds are 0.025
and 0.05 — nearly identical to no correction, and in every scenario here both
p-values are far below either. **The correction changes no verdict in this
project.** Say so. The value is a structure that scales; claiming it mattered
when it didn't is exactly what gets caught.

---

### B5. Pooled θ for CUPED

**Alternatives:** estimate θ separately per arm.

**Why:** under randomization X has the same distribution in both arms, so a
pooled θ is a treatment-independent constant and the unbiasedness argument holds
exactly. A per-arm θ becomes a function of that arm's outcomes, which
reintroduces a small bias and adds estimation noise for no benefit. Pooling also
halves the estimation error in θ itself.

The API encodes this: `cuped_adjust(y, x)` takes no `group` argument, so the
caller must pool and split afterwards. The right thing is the easy thing.

---

### B6. Unpooled (Welch) standard error everywhere

**Alternatives:** pooled SE under H₀ (the textbook two-proportion test).

**Why:** pooled is the more correct *null* variance for a test, but using pooled
for the test and unpooled for the CI lets a "significant" p-value coexist with a
CI that touches zero — confusing in a stakeholder report. Unpooled keeps test
and interval **coherent**. At p ≈ 0.035 and n = 70,000 the two differ in the
fourth significant figure.

This is an engineering trade-off, not a statistical error, and framing it that
way ("here is the trade-off, here is the side I picked and why") is far stronger
than reciting the formula.

---

### B7. Normal approximation (z) rather than t

**Alternatives:** t-tests; bootstrap; permutation tests.

**Why:** at n in the tens of thousands, `t ≈ z` to four decimals. The t
correction matters below roughly n = 100.

**When the alternative wins:** revenue is zero-inflated with a heavy lognormal
tail, so at *small* n the CLT could struggle. At n = 70,000 with ~2,400 nonzero
values per arm it is fine, but a bootstrap or a permutation test would be the
robust choice for a smaller experiment, and trimming/winsorizing is standard
practice for revenue metrics in industry. Know that answer.

---

### B8. Relative margins resolved against the **control** mean

**Alternatives:** pooled mean; treatment mean.

**Why:** the pooled mean contains treatment's effect, so a relative margin
anchored on it would *move with the thing being tested* — the tolerance would
shrink exactly when treatment did harm. Control is the pre-agreed, unaffected
reference point. One line (`margin_abs = spec.margin * np.mean(y_c)`), real
statistical content, easy to get wrong.

---

### B9. Reporting guardrail power at all

**Alternatives:** report nothing (the standard advice against post-hoc power).

**Why this is not the discredited thing:** observed/post-hoc power computes
power *at the observed effect*, and is a deterministic monotone function of the
p-value, so it carries zero information. This computes power at a **fixed
hypothetical alternative (zero true harm)** — a property of the design (margin,
n, metric variance), not of the result. Change the observed effect and it barely
moves; change the margin or n and it moves a lot.

**The caveat to volunteer:** the *realized* SE is plugged in rather than a
pre-experiment variance estimate, so it is not purely a priori. The rigorous
version computes it at design time from historical variance. Say the caveat
before the interviewer finds it — it converts a gotcha into evidence of
subtlety.

---

### B10. INVESTIGATE when NI passes but power < floor

**Alternatives:** call it a pass — the bound cleared the margin, evidence is
evidence.

**The argument for the engine's choice:** at 13% power, even a perfectly
harmless treatment would come back inconclusive ~87% of the time. So a pass
reflects an unusually large observed effect rather than an adequately sized
design, and the margin was never realistically testable at that n.

**The argument against (which is legitimate, and you should present it):** the
confidence bound already contains all the evidence. If the bound clears the
margin, non-inferiority is established at level α regardless of what would have
happened in other hypothetical datasets. Gating on power arguably double-counts.

**Why the engine's choice is still defensible:** it **flags rather than blocks**
— INVESTIGATE, not DO NOT SHIP. That is the proportionate response to a *design*
concern as distinct from an *evidence* concern, and it routes to the right
action: the memo's phased rollout, not a kill.

Presenting both sides here is a genuine seniority signal. Most candidates
defend; few evaluate.

---

## Part C — Simulation design decisions

### C1. Two independent latents — the selection-bias incident

**This is the project's best story. Have a 90-second version memorized.**

**The symptom:** with the true AOV effect set to exactly zero, treatment AOV
kept landing ~2% below control across every seed, silently consuming the whole
2% non-inferiority margin. The SHIP scenario would not pass.

**The diagnosis:** the original generator had **one latent "user quality"
factor** driving both conversion propensity and order value. Lifting conversion
pulled *marginal* users — lower on the quality latent — into the treatment
converter pool. Under a single factor, lower quality means smaller baskets. So
treatment's average order value fell with **no causal effect on order value
whatsoever**.

This is selection bias from **conditioning on a post-treatment variable**. AOV
is `revenue | converted`, and `converted` is affected by treatment, so
conditioning on it destroys the comparability randomization bought. Named
versions: collider-stratification bias; Lord's paradox.

**The fix:** two independent latents — the classic frequency/monetary
decomposition. `q_freq` drives conversion and pre-period activity; `q_value`
drives basket size. Now a conversion lift shifts composition on *frequency*, not
on *basket value*, so AOV is unbiased by construction. Every Phase 1 and Phase 2
gate was re-run and passed.

**The lesson carried forward:** guardrails belong on **all-user** metrics
wherever possible. Notebook 04 applies it directly — the Hillstrom guardrail is
spend per ALL users, not spend per converter, because its denominator is the set
of randomized users and treatment cannot move it.

**Why this anecdote works so well:** it demonstrates debugging a *statistical*
rather than a software bug, recognizing a named causal-inference failure mode,
fixing the root cause instead of the symptom, re-validating afterwards, and
transferring the lesson to a design decision on a different dataset. Very few
candidates have a complete story like that. Use it for "tell me about a hard bug
you fixed."

---

### C2. Probit threshold for conversion

**Alternatives:** `Bernoulli(p_i)` with a user-varying `p_i`; a logistic model
with a numerically solved intercept.

**Why:** the probit construction gives **two properties at once** — an *exact*
marginal conversion rate per arm (so "the true lift is 8%" means precisely that,
and validation gates can assert against it) *and* genuine user heterogeneity (so
CUPED has signal to exploit). A varying-`p_i` Bernoulli gives heterogeneity but
only an approximate marginal rate, which makes "the true effect" fuzzy — fatal
when the whole point is validating against known truth.

The mechanism: `w·q_freq + √(1−w²)·ε` has variance `w² + (1−w²) = 1` exactly, so
the index is standard normal and thresholding at `Φ⁻¹(1−p)` gives P = p exactly.

**Subtlety worth knowing:** applying the lift as `p → p(1+lift)` and then
thresholding is a shift in the *latent threshold*, i.e. a homogeneous effect on
the probit scale, not a homogeneous risk difference. The marginal rate is still
exactly `p(1+lift)`, which is what the analysis targets.

---

### C3. Exactly balanced 50/50 assignment

**Alternatives:** independent Bernoulli assignment per user.

**Why:** exact balance removes assignment-ratio noise, so measured variance is
metric variance and nothing else — cleaner for validating a method.

**The cost, which is a real gap:** the generator can never produce a **sample
ratio mismatch**, the single most common real-world data-quality failure. SRM
detection therefore cannot be demonstrated. Own this one.

---

### C4. Error rate independent of the latents

**Alternatives:** load it on `q_freq` too.

**Why:** the error-rate guardrail exists as the **well-powered contrast** to the
AOV guardrail — all users, binary, tight variance, ~100% power. Keeping it
simple isolates the teaching point: what makes AOV hard is the converter-only
denominator and heavy tails, not guardrails in general.

---

## Part D — Software design decisions

### D1. `MetricSpec` — metrics as declarative data

**Alternatives:** a function per metric; an `if metric_name == ...` chain;
subclasses.

**Why:** separating *what to measure* from *how to test it* is what let notebook
04 run the engine on a completely different real dataset by writing three
`MetricSpec` objects — **zero engine changes**. That is the strongest software
design point in the project and the one to lead with if asked about engineering
rather than statistics.

Against subclasses: a `GuardrailMetric(Metric)` hierarchy would scatter the
decision logic across classes, whereas the value of this engine is that all the
policy lives in one readable `evaluate_experiment`. Data + one interpreter beats
polymorphism when the behaviour space is small and fixed.

---

### D2. Dataclasses for results

**Alternatives:** tuples; dicts; bare DataFrames.

**Why:** `NonInferiorityResult` carries eight fields including three booleans
with genuinely different meanings. As a tuple that is unreadable (`r[5]` — which
flag?); as a dict it is untyped and typo-prone. A dataclass gives named, typed,
IDE-completable fields and makes `render()` self-documenting.

---

### D3. Computation separated from rendering

`evaluate_experiment` returns data; `render()` and the Streamlit tab format it
two different ways. If verdict logic lived in a renderer, the notebook and the
dashboard could disagree about the same experiment. Two presentations, one
computation.

---

### D4. `config.py` as a Python module

**Alternatives:** YAML/JSON; constants at call sites; CLI arguments.

**Why:** typed values, comments, arithmetic and IDE navigation with no parsing
layer. Config-as-code is right for a single-author analysis project; in a
multi-tenant production platform you would want config as *data* so it can be
versioned, diffed and audited independently of the code.

The pattern that makes it work: functions take config values as **default
arguments**, never by reading the module inside the body. That is what lets the
dashboard override α and power from sliders without any refactor.

---

### D5. Plot functions return `Figure`

Never `plt.show()`, never `savefig`. One function serves notebooks, PNG export
and `st.pyplot()`. Side-effect-free plotting is the whole reason `plots.py` is
reusable across three surfaces.

---

### D6. `sys.path.insert` instead of packaging

**This is the weakest pattern in the repo and you should say so first.**
The correct fix is a `pyproject.toml` and `pip install -e .`. `sys.path`
manipulation is fragile, invisible to tooling, and breaks under some runners.
It is a pragmatic shortcut for a notebook-centric analysis repo — acceptable
here, not acceptable in a shipped library.

---

## Part E — Honest weaknesses (know these before the interviewer does)

Ranked by how likely an interviewer is to find them.

### E1. No sample ratio mismatch (SRM) check — **the biggest gap**
Every real experimentation platform checks SRM *before* looking at any metric: a
chi-square test that the observed split matches the intended one. An SRM
invalidates the entire experiment, because it means assignment or logging is
broken and the arms are no longer comparable.

This project has no SRM check, and the generator cannot even produce one (C3).
**Fix:** a `chisquare([n_t, n_c], [n/2, n/2])` gate that hard-fails
`evaluate_experiment` before any metric is tested, plus an option in the
generator to inject a ratio imbalance so the check can be demonstrated.

Volunteer this. It is the first thing an experienced experimentation person
looks for.

### E2. CUPED is demonstrated but not wired into the decision engine
`cuped_adjust` is never called inside `evaluate_experiment`. The engine runs on
raw metrics; CUPED lives in notebook 02 and the dashboard. So the project shows
39% variance reduction and then does not spend it.

**Fix:** a `covariate: str | None` field on `MetricSpec`; when set,
`_metric_arrays` returns the adjusted array. Roughly ten lines. It is arguably
the single highest-value change left in the repo.

### E3. Fixed-horizon only — no sequential testing
No always-valid inference, no group-sequential boundaries, no alpha spending.
So the analysis is only valid if nobody peeks, which nobody in the real world
obeys. Peeking at a fixed-horizon test inflates the false-positive rate badly
(roughly 20–30% with frequent monitoring). **Fix:** mSPRT / always-valid
p-values, or O'Brien-Fleming boundaries. The README names this as the next
statistical layer.

### E4. Average effects only — no heterogeneous treatment effects
Everything estimates an ATE. The standard next question after a SHIP verdict is
"for whom?" — segment analysis, CATE estimation, uplift modelling. Deliberately
out of scope, and the README says so.

### E5. Guardrail power uses the realized SE
See B9. Not the discredited post-hoc power, but not purely a priori either.

### E6. Hardcoded `"converted"` and `"group"` column names
`_metric_arrays` leaks the synthetic schema into a general-purpose engine.
`"group"` is a defensible data contract; `"converted"` is not. **Fix:** a
`filter_column` field or a predicate callable on `MetricSpec`.

### E7. BH does nothing at m = 2
See B4. The structure is right; the effect is nil at this family size.

### E8. Independence assumed throughout
One row per user, no clustering, no repeated measures, no network interference.
Violated by any marketplace, social feature, or session-level metric. **Fix:**
cluster-robust standard errors, or cluster randomization with the delta method
for ratio metrics.

### E9. No effect-size reporting discipline beyond point estimates
No standardized effect sizes, no practical-significance thresholds on the
success metrics (only guardrails have margins). An MDE was used for *design* but
the success metrics ship on statistical significance alone. Arguably success
metrics deserve their own materiality floor.

### E10. `sys.path` hacking rather than packaging
See D6.

### E11. Single seed per scenario in G3c
The scenario gate uses fixed representative draws, so it is a **regression
test**, not a statistical claim. The module docstring says exactly this, which
is the right way to handle it — but be clear about the distinction if asked.

---

## Part F — What you would build next, in priority order

1. **SRM check** — smallest change, largest correctness gain (E1).
2. **Wire CUPED into the engine** — makes the variance reduction actually pay
   for itself (E2).
3. **CUPAC** — replace the single covariate with a model prediction over all
   pre-experiment features. Would materially help the real-data case where one
   year-long covariate correlates at 0.02.
4. **Sequential testing** — mSPRT or group-sequential boundaries so peeking is
   safe (E3).
5. **Heterogeneous treatment effects** — the natural follow-up question to any
   SHIP verdict (E4).
6. **Ratio metrics with the delta method** — session-level and per-converter
   metrics done correctly, with clustering.
7. **Packaging** — `pyproject.toml`, kill the `sys.path` hacks (E10).

The first two are half-day tasks. Being able to name them, in order, with
effort estimates, is exactly what "what would you do next?" is testing.
