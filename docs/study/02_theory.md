# 02 — The theory, derived rather than quoted

Everything here is derivable on a whiteboard in a few minutes. Interviewers can
tell instantly whether you memorized a formula or understand where it comes
from. Learn the derivations; the formulas fall out for free.

---

## §0 Foundations you must be able to state cold

**Type I error (α)** — rejecting a true null. "We claimed an effect that isn't
there." Ships a change that does nothing.

**Type II error (β)** — failing to reject a false null. "We missed a real
effect." Kills a change that would have worked.

**Power = 1 − β** — probability of detecting a real effect of a given size.

**The asymmetry that runs through this entire project:** for a *success* metric
the expensive error is Type I (you ship junk and believe a lie). For a
*guardrail* the expensive error is Type II (you miss real harm and ship a
regression). Any procedure that reduces one raises the other at fixed n. So the
two metric families must be treated differently. This single sentence is the
thesis of the whole project.

**p-value** — P(a test statistic at least this extreme | H₀ true). It is *not*
P(H₀ true), and it is not the probability the result is a fluke. Be precise
about this; sloppy p-value language is a common interview knockout.

**Confidence interval** — an interval produced by a procedure that covers the
true parameter in 95% of repeated experiments. The realized interval either
contains the truth or it doesn't; the 95% is a property of the *procedure*.

**Minimum detectable effect (MDE)** — the smallest effect the design is powered
to find. It is a *design input*, chosen from what the business would care about,
not a result.

---

## §1 The difference-in-means estimator

Everything in `src/tests_stats.py` is built on one estimator:

$$\hat{\Delta} = \bar{Y}_T - \bar{Y}_C$$

Under independent sampling, variances add:

$$\text{Var}(\hat{\Delta}) = \frac{\sigma_T^2}{n_T} + \frac{\sigma_C^2}{n_C}
\quad\Longrightarrow\quad
\widehat{SE} = \sqrt{\frac{s_T^2}{n_T} + \frac{s_C^2}{n_C}}$$

This is the **unpooled (Welch) standard error** and it is what the code uses
everywhere.

By the CLT, $\hat{\Delta}/SE \approx N(0,1)$ under H₀, so:

- two-sided CI: $\hat{\Delta} \pm z_{1-\alpha/2}\cdot SE$
- two-sided p: $2(1 - \Phi(|\hat{\Delta}|/SE))$

**Why z and not t?** At n in the tens of thousands, $t_{140000} \approx z$ to
four decimal places. The t distribution's correction matters below roughly
n = 100. Stating this confidently (rather than defensively) is the right move.

**Why unpooled and not pooled?** For a two-proportion test, the textbook null
variance is *pooled*: under H₀ the two rates are equal, so you estimate one
common rate $\bar{p}$. The unpooled version uses each arm's own variance.

- Pooled is the more correct *null* variance for a hypothesis test.
- Unpooled makes the test and the confidence interval agree — with pooled SE for
  the test and unpooled SE for the CI you can get a "significant" p-value with a
  CI that touches zero, which is confusing in a report.
- At p ≈ 0.035 and n = 70,000 the two SEs differ in the fourth significant
  figure. Immaterial.

The code chooses **coherence between test and interval** over textbook purity,
and says so in the docstring. That is a defensible engineering decision, and
"here is the trade-off and here is why I picked this side" is a much stronger
answer than "this is the formula."

**Binary metrics are a special case, not a special test.** For a 0/1 column,
$\bar{Y} = \hat{p}$ and $s^2 = \hat{p}(1-\hat{p})\cdot n/(n-1)$, so the
difference-in-means machinery *is* the two-proportion z-test. That is why
`MetricSpec.test` ("proportion" vs "mean") is only a **label for the report**
and does not change the code path — worth knowing, because it looks like a
dispatch key and isn't.

---

## §2 Power analysis

### The derivation (learn this one properly)

Setup: two arms of size n, rates $p_1$ (control) and $p_2 = p_1(1+\text{MDE})$,
true difference $\Delta = p_2 - p_1$.

**Step 1 — when do we reject?**
Under H₀ ($p_1 = p_2 = \bar{p}$), the null SE is

$$SE_0 = \sqrt{\frac{2\bar{p}(1-\bar{p})}{n}}, \qquad \bar{p} = \frac{p_1+p_2}{2}$$

We reject when $|\hat{\Delta}| > z_{1-\alpha/2}\cdot SE_0$.

**Step 2 — what is the distribution of $\hat\Delta$ when H₁ is true?**

$$\hat{\Delta} \sim N(\Delta,\ SE_1^2), \qquad
SE_1 = \sqrt{\frac{p_1(1-p_1) + p_2(1-p_2)}{n}}$$

Note the two SEs are different: $SE_0$ assumes equal rates, $SE_1$ does not.

**Step 3 — power is the probability of landing in the rejection region.**
(Ignoring the negligible wrong-tail probability.)

$$1-\beta = P(\hat{\Delta} > z_{1-\alpha/2}SE_0)
= \Phi\!\left(\frac{\Delta - z_{1-\alpha/2}SE_0}{SE_1}\right)$$

**Step 4 — solve for n.** Set the argument equal to $z_{1-\beta}$:

$$\Delta = z_{1-\alpha/2}SE_0 + z_{1-\beta}SE_1$$

Both SEs carry a $1/\sqrt{n}$, so factor it out and square:

$$\boxed{n = \frac{\left(z_{1-\alpha/2}\sqrt{2\bar{p}(1-\bar{p})}
+ z_{1-\beta}\sqrt{p_1(1-p_1)+p_2(1-p_2)}\right)^2}{(p_2-p_1)^2}}$$

That is `required_sample_size_per_arm` verbatim (`src/power.py:45-49`).

`achieved_power` inverts step 3 with n known — solve for the z-score and apply Φ
(`src/power.py:73-77`). The test `test_power_at_recommended_n_hits_target`
asserts the round trip closes, with power landing at or just above target
because n is rounded up with `math.ceil`.

### The intuitions to have ready

**n scales as 1/Δ².** Halve the MDE → **quadruple** the sample size. This is the
single most-asked power question and the answer is "four times, because n is
inversely proportional to the square of the effect size."

**The rule of thumb:** with α = 0.05 two-sided and 80% power,
$(z_{0.975} + z_{0.80})^2 = (1.96 + 0.84)^2 \approx 7.84 \approx 8$, so

$$n \approx \frac{16\,p(1-p)}{\Delta^2}$$

Check it: $16 \times 0.035 \times 0.965 / 0.0028^2 \approx 68{,}900$ against the
exact 70,229. Close enough to sanity-check any sample size in your head — which
is a genuinely useful party trick in an interview.

**Rare events are expensive.** Because $\Delta = p_1 \times \text{MDE}$, n grows
roughly as $1/p$ for a fixed *relative* lift. Halving the baseline rate roughly
doubles the required traffic.

**The four levers.** Sample size trades off against exactly four things:
baseline rate, MDE, α, and power. Raising α or lowering power buys a smaller n
by accepting more error. There is no free lunch — except variance reduction,
which is the next section, and which is why CUPED is interesting.

### The project's numbers

| Input | Value |
|---|---|
| Baseline conversion | 3.5% |
| MDE | +8% relative → 3.78% absolute (Δ = 0.0028) |
| α | 0.05 two-sided |
| Power | 80% |
| **Result** | **70,229 users/arm = 140,458 total = 14 days at 10k/day** |

### Why two-sided for design but one-sided for the decision?

A real inconsistency, and you should be ready for it. The sample-size formula
uses $z_{1-\alpha/2}$; the shipping decision uses a one-sided superiority test.

The defence: sizing two-sided is **conservative** — it demands more users than a
one-sided design would, so the achieved one-sided power is *above* the 80%
target. Being over-powered relative to plan is a safe direction to err.

The cleaner alternative would be one-sided throughout. Say that too. Owning a
small inconsistency and explaining its direction is stronger than pretending it
isn't there.

---

## §3 CUPED

**CUPED** = **C**ontrolled-experiment **U**sing **P**re-**E**xperiment **D**ata
(Deng, Xu, Kohavi & Walker, WSDM 2013).

### The problem

Metric variance comes from two sources: (a) the treatment effect we want to
measure, and (b) pre-existing differences between users — some people just buy
more than others. Source (b) is pure noise for our purposes, and it dominates.
If we could subtract it, the same number of users would give a tighter estimate.

We can, when a pre-experiment covariate predicts it.

### The estimator

$$Y_{\text{cuped}} = Y - \theta(X - \bar{X})$$

where X is measured **before** randomization.

### Derivation 1: the optimal θ

$$\text{Var}(Y - \theta X) = \text{Var}(Y) - 2\theta\,\text{Cov}(Y,X) + \theta^2\text{Var}(X)$$

Quadratic in θ, opening upward. Differentiate and set to zero:

$$\frac{d}{d\theta} = -2\,\text{Cov}(Y,X) + 2\theta\,\text{Var}(X) = 0
\quad\Longrightarrow\quad
\boxed{\theta^* = \frac{\text{Cov}(Y,X)}{\text{Var}(X)}}$$

That is `compute_theta` (`src/cuped.py:27-28`) and it is exactly the OLS slope
of Y on X — which is why the unit test
`test_theta_recovers_linear_coefficient` builds `y = 5 + 2x + noise` and asserts
θ ≈ 2.

### Derivation 2: the variance reduction

Substitute θ* back in:

$$\text{Var}(Y_{\text{cuped}}) = \text{Var}(Y) - \frac{\text{Cov}(Y,X)^2}{\text{Var}(X)}
= \text{Var}(Y)\left(1 - \frac{\text{Cov}(Y,X)^2}{\text{Var}(Y)\text{Var}(X)}\right)$$

The bracketed fraction is exactly $\rho^2$, so:

$$\boxed{\text{Var}(Y_{\text{cuped}}) = \text{Var}(Y)\,(1-\rho^2)}$$

**Everything about CUPED follows from this one line.** The entire value of the
method is captured by a single number, ρ.

### The three consequences (know all three, they get asked separately)

| Quantity | Scaling | At ρ = 0.625 |
|---|---|---|
| Variance | $\times(1-\rho^2)$ | −39.0% |
| Standard error / CI width | $\times\sqrt{1-\rho^2}$ | −21.9% |
| Sample size for equal power | $\times(1-\rho^2)$ | −39.0% → 14 days becomes 8.6 |

The CI narrows by $1 - \sqrt{1-\rho^2}$, **not** by $\rho^2$. Mixing these up is
a classic slip: variance and sample size scale together; SE and CI width scale
with the square root.

### Derivation 3: why it stays unbiased

$$\hat{\Delta}_{\text{cuped}} = (\bar{Y}_T - \theta(\bar{X}_T - \bar{X}))
- (\bar{Y}_C - \theta(\bar{X}_C - \bar{X}))
= (\bar{Y}_T - \bar{Y}_C) - \theta(\bar{X}_T - \bar{X}_C)$$

The global centring constant $\bar{X}$ **cancels exactly** in the difference.
And because X is pre-experiment and assignment is random,
$E[\bar{X}_T] = E[\bar{X}_C]$, so:

$$E[\hat{\Delta}_{\text{cuped}}] = E[\bar{Y}_T - \bar{Y}_C] = \Delta$$

Unbiased. The correction term has mean zero, and it removes *shared* noise from
both arms.

The plain-English version, which is what you should lead with: *X was measured
before we flipped the coin, so the treatment cannot possibly have changed it.
Subtracting something the treatment can't affect can't move the treatment
effect — it only removes noise.*

### Why θ is pooled across arms

`compute_theta` is called on the **combined** sample, not per-arm.

- Under randomization X has the same distribution in both arms, so pooled θ is a
  treatment-independent constant, and the unbiasedness argument above holds
  exactly.
- Estimating θ separately per arm makes θ a function of that arm's outcomes,
  which reintroduces a small bias and adds estimation noise for nothing.
- Pooling also halves the estimation error in θ itself.

### Why centring matters

$Y - \theta X$ would reduce variance just as well, but it shifts the metric off
its natural scale — an "adjusted revenue" of −$12 is meaningless in a report.
Subtracting $\theta(X - \bar{X})$ preserves the mean exactly
(`test_cuped_preserves_mean_and_reduces_variance`), so adjusted values stay
interpretable as dollars.

### Why revenue gained 39% but conversion only 6%

This is the most-asked CUPED question on this project. Have **two** answers.

**Answer 1 — the correlation.** ρ(revenue, pre-period spend) = 0.625 →
ρ² = 39%. ρ(converted, pre-period sessions) = 0.251 → ρ² = 6.3%. Spending
habits persist strongly; a rare binary event is far less predictable.

**Answer 2 — the law of total variance (the deep answer).** For a binary Y with
propensity $p(X)$:

$$\text{Var}(Y) = \underbrace{E[p(X)(1-p(X))]}_{\text{irreducible Bernoulli noise}}
+ \underbrace{\text{Var}(p(X))}_{\text{explainable by }X}$$

The best achievable $R^2$ — even with a *perfect* model of the propensity — is
$\text{Var}(p(X))/\text{Var}(Y)$. When p ≈ 0.035, the Bernoulli term is around
0.0338 and dominates completely, because propensity variation across users is
tiny by comparison. So the ceiling on ρ² is low **as a mathematical property of
rare binary outcomes**, not a failure of the covariate.

Answer 2 is what distinguishes you. It says the limitation is structural, so no
amount of covariate engineering fixes it — which is also why the correct
response in practice is to pick a more sensitive *metric*, not a better
covariate.

### The real-data reality check (notebook 04)

On Hillstrom: ρ(two-week spend, prior-year history) = **0.0195** → variance
reduction **0.038%**. Effectively nothing.

Why: spend is zero for ~99% of users in a two-week window (same rare-event
ceiling as above), *and* a year-long aggregate is a coarse predictor of a
two-week outcome. Same method, same math, different data.

This is the most intellectually honest result in the project and you should
volunteer it. "CUPED gave me 39% on simulated data and 0.04% on real data, and
here is exactly why" is a much better story than 39% alone.

### The natural extension: CUPAC

Instead of one covariate, train a model $\hat{f}$ predicting Y from *all*
pre-experiment features and use $\hat{f}(X)$ as the covariate (DoorDash's
CUPAC). CUPED with a single X is the special case where $\hat f$ is a
univariate linear regression. A better predictor raises ρ and therefore the
variance reduction. The one rule: the model must be fit on pre-experiment or
control-only data so it stays treatment-independent.

---

## §4 Non-inferiority testing — the guardrail engine

### The problem it solves

You cannot prove a null hypothesis. "p = 0.4, so there's no harm" is a
**failure to detect**, not evidence of absence — and with a small enough sample
you can fail to detect anything at all. A guardrail built on "p > 0.05 means
we're fine" rewards underpowered experiments, which is exactly backwards.

Non-inferiority flips the burden of proof. Instead of trying to accept a null,
you make "harm at least as bad as m" the **null** and try to reject it.

### The hypotheses

Let $\Delta = \bar{Y}_T - \bar{Y}_C$ and let m > 0 be the margin.

**Harm direction = "decrease"** (order value must not drop more than m):

$$H_0: \Delta \le -m \qquad\text{vs}\qquad H_1: \Delta > -m$$
$$z = \frac{\hat\Delta + m}{SE}, \qquad p = 1 - \Phi(z)$$

**Harm direction = "increase"** (error rate must not rise more than m):

$$H_0: \Delta \ge +m \qquad\text{vs}\qquad H_1: \Delta < +m$$
$$z = \frac{\hat\Delta - m}{SE}, \qquad p = \Phi(z)$$

Rejecting H₀ *establishes* non-inferiority — a positive claim backed by
evidence, not a shrug.

### The equivalent CI formulation (use this one to explain it)

Non-inferiority passes iff the one-sided confidence bound on the harmful side
stays inside the margin:

- decrease: $\hat\Delta - z_{1-\alpha}SE > -m$
- increase: $\hat\Delta + z_{1-\alpha}SE < +m$

*"Even in the worst case the data allows, we are still inside the tolerance the
business agreed to."* That sentence is the entire concept and it is how you
explain it to a non-statistician.

### Three booleans, three different meanings

`non_inferiority_test` returns three flags that are routinely confused.
Being crisp about the difference is a strong signal.

| Flag | Definition | Meaning |
|---|---|---|
| `ni_passed` | worst-case bound is inside the margin | Safety established. |
| `inferior` | the bound *nearest zero* is outside the margin | Harm beyond tolerance is established. **Blocks the ship.** |
| `harm_detected` | the CI excludes **zero** on the harmful side | There is *some* real harm, possibly trivial. Informational only. |

Between `ni_passed` and `inferior` lies a gap: the data is compatible both with
tolerable harm and with intolerable harm. That gap is **INVESTIGATE**. It is not
a bug — it is the honest third answer that a two-outcome test cannot express.

**The critical design decision:** DO-NOT-SHIP triggers on `inferior`, *not* on
`harm_detected`. Why? The margin exists precisely because the business declared
degradation below m acceptable. At n = 1.8M, a +0.1pp error-rate rise is wildly
significant and completely irrelevant — it is inside the +0.5pp tolerance that
was agreed before launch. Blocking on statistical significance rather than on
business materiality would make every large experiment unshippable.

The notebook 03 SHIP scenario shows this explicitly: the error guardrail passes
with the note *"significant but within-margin degradation (accepted cost)."*
That line is the project in miniature — statistical significance and business
significance are different things, and the engine knows it.

### The power formula for a guardrail

What is the chance we establish non-inferiority **if the treatment is truly
harmless** (Δ = 0)?

$$P(\hat\Delta - z_{1-\alpha}SE > -m \mid \Delta = 0)
= P\!\left(\frac{\hat\Delta}{SE} > z_{1-\alpha} - \frac{m}{SE}\right)
= \Phi\!\left(\frac{m}{SE} - z_{1-\alpha}\right)$$

That is `src/tests_stats.py:184`. It depends on the ratio m/SE — how big the
tolerance is relative to the noise. Wide margin or small SE → high power.

**If this number is low, a "pass" means little and a "fail" means nothing**,
because even a perfectly harmless treatment would usually come back
inconclusive. That is why the engine gates on it.

### Is this "post-hoc power"? (The sharpest critique you will face)

**Know this distinction cold.** Observed/post-hoc power — computing power at the
*observed* effect size — is genuinely discredited, because it is a deterministic
monotone function of the p-value and therefore adds zero information.

This is **not** that. Power here is evaluated at a **fixed hypothetical
alternative (Δ = 0, a harmless treatment)**, which is a property of the *design*
— margin, sample size, metric variance — and not of the observed effect. Change
the observed effect and this number barely moves; change the margin or n and it
moves a lot. It is a design diagnostic, computed after the fact.

**The honest caveat, which you should volunteer:** the *realized* SE is plugged
in rather than a pre-experiment variance estimate, so it isn't purely a priori.
The fully rigorous version computes it at design time from historical variance.
In practice they are very close at these sample sizes, and computing it from the
realized data makes it available without a separate planning artifact.

Say the caveat before the interviewer finds it. It converts a potential
gotcha into evidence that you understand the subtlety.

### Guardrail power is brutally expensive (the project's best finding)

At the primary-powered n = 70,229/arm, the AOV guardrail has **20% power**.

Why:
1. AOV only exists for converters — ~3.5% of users. 70,229 users → ~2,400
   converters per arm.
2. Order values are heavy-tailed lognormal: mean ≈ $59, SD ≈ $52.
3. SE ≈ $1.44, while the 2% margin is only ≈ $1.18. The margin is *smaller than
   one standard error*. The test cannot possibly resolve it.

To reach 80% power you need SE ≈ $0.474, which is a factor of
$(1.44/0.474)^2 \approx 9.3$ more users — roughly **650,000 per arm**. The
project uses 900,000/arm (≈12.8× the primary's n) for the SHIP/DO-NOT-SHIP
demos, which buys ≈91% power.

Contrast the error-rate guardrail: binary, 1.2% base rate, all users,
SE ≈ 0.00059 against a 0.005 margin — 8.4 SEs of room, so power ≈ 100%.

**The general lesson:** guardrail power is driven by *margin ÷ standard error*.
Tight margins on high-variance, small-subpopulation metrics are untestable at
realistic traffic. Real teams respond by widening the margin, moving to an
all-user formulation, or accepting the Type II risk explicitly. This engine's
contribution is that it **surfaces the trade-off instead of hiding it.**

---

## §5 Multiple comparisons and Benjamini-Hochberg

### The problem

Test m independent metrics at α = 0.05 with all nulls true. P(at least one false
positive) = $1 - 0.95^m$: 23% at m = 5, 40% at m = 10. Test enough metrics and
you will always find a "win."

### Two different things you might want to control

**FWER** (family-wise error rate) = P(≥1 false positive). Controlled by
Bonferroni: test each at α/m. Very conservative; power collapses as m grows.

**FDR** (false discovery rate) = E[false positives / total rejections].
Controlled by Benjamini-Hochberg. Much more powerful. Says: *"of the wins I
declare, at most 5% are expected to be spurious"* — which is the right framing
for a screening/discovery process.

### The BH procedure

1. Sort p-values ascending: $p_{(1)} \le \dots \le p_{(m)}$
2. Find the **largest** k with $p_{(k)} \le \frac{k}{m}q$
3. Reject $H_{(1)}, \dots, H_{(k)}$ — **all** of them, including any whose own
   p-value exceeds its own threshold

Step 3 is the "step-up" property and it is the part people get wrong. The unit
test makes it explicit: with p = [0.03, 0.04] and q = 0.05, the thresholds are
0.025 and 0.05. p = 0.03 alone would *fail* its threshold of 0.025 — but
p₍₂₎ = 0.04 ≤ 0.05 passes, and so **both** are rejected. A larger p-value
rescues a smaller one.

The implementation (`src/tests_stats.py:206-215`) does exactly this:
`np.max(np.nonzero(passing)[0])` finds the largest passing index, then
`rejected[order[:k+1]] = True` rejects everything up to it.

BH controls FDR at $q \cdot m_0/m$ where $m_0$ is the number of true nulls, under
independence or positive regression dependence (PRDS). Gate G3b verifies this
empirically: with 5 true nulls out of 10, the theoretical FDR is
0.05 × 5/10 = 0.025, and the simulation lands there.

### Why BH and not Bonferroni here?

Success metrics are a *discovery* family: we want to find improvements, and a
few false leads are recoverable (they get re-tested, or the next experiment
contradicts them). FDR is the natural error rate for that. Bonferroni's FWER
guarantee is what you want when a single false positive is catastrophic — a
drug approval, not a checkout button.

### Why guardrails are deliberately NOT corrected

**This is the most important conceptual question the project invites. Rehearse
the answer until it is automatic.**

Alpha correction makes it *harder to reject a null*. For a guardrail, the null
is "there is harm." Making it harder to reject means making it harder to declare
safety — and, more damningly, an analyst who wants to ship is *rewarded* for
adding more guardrails, because each one loosens the others. The incentive runs
exactly the wrong way.

The deeper reason: correction exists to control **Type I** error inflation. For
guardrails the costly error is **Type II** — missing real harm. Spending effort
suppressing the error you don't fear, at the cost of the one you do, is
backwards.

So guardrails get uncorrected tests at full α, and their Type II risk is
reported explicitly as **power** — with a power floor that triggers INVESTIGATE
rather than allowing a silent pass. Type I risk is controlled by correction;
Type II risk is controlled by disclosure and a floor.

The framing comes from Kohavi, Tang & Xu (*Trustworthy Online Controlled
Experiments*) and Spotify's published guardrail decision framework.

### Honest limitation

With only two success metrics, BH at q = 0.05 has thresholds 0.025 and 0.05 —
barely different from no correction, and in every scenario in this project both
p-values are far below either. **The correction changes no verdict here.** Say
so. The value is that the *structure* is correct and scales: add eight more
secondary metrics and the correction starts doing real work. Claiming it
mattered when it didn't is the kind of overstatement interviewers pounce on.

---

## §6 Post-treatment conditioning — the trap the project fell into and fixed

### What happened (a real incident, mid-build)

The SHIP demo would not pass. With the true AOV effect set to **exactly zero**,
treatment AOV kept landing ~2% *below* control, across every seed — silently
consuming the entire 2% non-inferiority margin.

### The diagnosis

The original generator used a **single latent "user quality" factor** driving
both conversion propensity and order value. So:

1. Treatment lifts conversion by 8%.
2. The extra converters are **marginal** users — those just below the old
   threshold, i.e. lower on the quality latent.
3. Lower quality ⇒ smaller baskets under the single-factor model.
4. Treatment's converter pool now contains users the control pool never had.
5. Average order value in treatment falls — **with no causal effect on order
   value whatsoever.**

This is **selection bias from conditioning on a post-treatment variable**. AOV
is `revenue | converted`, and `converted` is affected by treatment. Conditioning
on it breaks the comparability that randomization bought. In the causal
inference literature this is collider-stratification bias; the closely related
statistical phenomenon is Lord's paradox.

### The fix

Two **independent** latent factors — the classic frequency/monetary
decomposition:

- `q_freq` → conversion propensity, pre-period sessions, pre-period spend
- `q_value` → order value, pre-period spend

Now a conversion lift shifts composition on `q_freq`, but order value depends
only on `q_value`. The marginal converters differ in *frequency*, not in *basket
size*, so AOV is unbiased by construction. Every Phase 1 and Phase 2 gate was
re-run and passed after the change.

Read `config.py:38-56` — the comment block there is the record of this fix.

### The transferable lesson (and how it changed notebook 04)

**Guardrails belong on all-user metrics whenever possible.** Per-converter
ratio metrics condition on a post-treatment variable and can show "harm" that
is pure composition shift.

Notebook 04 applies the lesson directly: the Hillstrom guardrail is **spend per
ALL users** (zeros included), not spend per converter. Its denominator is the
set of randomized users, which treatment cannot move. Randomization protects it
by construction.

### Why this story is your best asset

It demonstrates, in one anecdote: debugging a statistical (not software) bug;
recognizing a named causal-inference failure mode; fixing the root cause rather
than the symptom; re-running the full validation suite afterwards; and carrying
the lesson forward into a design decision on a different dataset. That is a
complete engineering-judgement narrative, and very few candidates have one.

Have a 90-second version ready for "tell me about a hard bug you fixed."

---

## §7 The simulation design

### Why simulate at all?

Because with real data you never know the truth, so you cannot verify a
*method*. With a generator you set the true effect yourself and check that the
machinery recovers it at the advertised rate. This is how you validate a
statistical pipeline: **known truth in, known error rates out.**

### The probit threshold trick

```python
w = CONVERSION_FREQ_LOADING                       # 0.95
latent = w*q_freq + sqrt(1 - w**2) * noise        # exactly N(0,1)
converted = latent > norm.ppf(1 - p)              # marginal rate exactly p
```

The loadings are chosen so $w^2 + (1-w^2) = 1$, making the latent index exactly
standard normal. Thresholding a standard normal at $\Phi^{-1}(1-p)$ gives
P(exceed) = p **exactly**, while the index still correlates with `q_freq` at
w = 0.95.

Two properties at once: an exact marginal rate (so "the true lift is 8%" means
precisely that) *and* user heterogeneity (so CUPED has signal to exploit). A
naive `Bernoulli(p_i)` with a user-varying $p_i$ gives you the second but not
the first, and then "the true effect" becomes fuzzy. `test_generator_marginal_rates`
asserts the exactness to within 0.002 on 400,000 users.

### How the treatment effects are injected

| Metric | Mechanism | Ground truth |
|---|---|---|
| Conversion | threshold shifted so marginal rate = `p·(1+lift)` | +8% relative |
| Order value | multiplicative `× (1 + aov_effect)` on converters | −1% relative |
| Error rate | additive on the Bernoulli parameter | +0.1pp absolute |

Relative for rates and order value, absolute for the error rate — matching how
each guardrail's margin is expressed, so effect and margin are in the same
units.

### What the simulation deliberately does NOT model

Know these, because "what are the limitations of your simulation?" is a
certainty:

- **Network effects / interference** — users are independent. Violated by social
  features, marketplaces, two-sided platforms. Needs cluster randomization.
- **Novelty and primacy effects** — no time dimension, so no effect decay.
- **Seasonality** — a single static window.
- **Heterogeneous treatment effects** — the effect is identical for every user.
  Real effects vary by segment, and that is usually the interesting question.
- **Sample ratio mismatch** — assignment is exactly 50/50 by construction, so
  the generator can never produce the single most common real-world data-quality
  failure.
- **Outliers and bot traffic** — clean lognormal tails, no capping needed.
- **Multiple sessions per user** — one row per user, so no within-user
  clustering.

The README states most of these. Volunteering them is a strength; being caught
by one is not.
