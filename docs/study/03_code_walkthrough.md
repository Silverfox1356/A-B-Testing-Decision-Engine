# 03 — Complete code walkthrough

Read this with the files open beside you. Every file, every function, what it
does, why it is written that way, and what would break it.

Repo totals: ~1,580 lines of Python across 11 files, plus 4 notebooks.

---

## `config.py` — 100 lines, zero imports

Five labelled sections.

### 1. Reproducibility
```python
RANDOM_SEED = 42
```
Used as the default seed everywhere so notebook 01, notebook 02 and the
dashboard all analyse *the same simulated experiment*. That is why notebook 02
can say "same experiment as notebook 01" and mean it literally.

### 2. Ground-truth effects
```python
CONTROL_CONVERSION_RATE = 0.035   # realistic e-commerce checkout baseline
TRUE_CONVERSION_LIFT    = 0.08    # relative
TRUE_AOV_EFFECT         = -0.01   # relative, slightly negative
CONTROL_ERROR_RATE      = 0.012
TRUE_ERROR_RATE_INCREASE= 0.001   # absolute, +0.1pp
```

Each number is chosen to make a specific teaching point:

- `TRUE_AOV_EFFECT = -0.01` is **negative but inside the 2% margin**. This makes
  the AOV guardrail genuinely interesting: there really is harm, it really is
  tolerable, and the question is whether the test can resolve it. A zero effect
  would have been a boring pass.
- `TRUE_ERROR_RATE_INCREASE = +0.001` against a 0.005 margin creates the
  "statistically significant but within tolerance" case that demonstrates why
  DO-NOT-SHIP triggers on materiality rather than significance.
- The 3.5% baseline is low enough that rare-event problems (expensive sample
  sizes, the CUPED correlation ceiling) show up naturally.

**Interview question you should expect:** "You chose the ground truth so the
scenarios would be interesting. Isn't that circular?" Answer: choosing the truth
is what makes the *validation* possible — you can only check that a method
recovers an effect at the advertised rate if you know the effect. The generator
is a test harness for the method, not evidence about checkout flows. And the
whole pipeline then runs unchanged on real data in notebook 04, where nothing
was chosen.

### 3. The latent user model
```python
CONVERSION_FREQ_LOADING = 0.95
SESSIONS_LOG_MEAN, SESSIONS_FREQ_LOADING = 1.6, 0.25
SPEND_LOG_MEAN, SPEND_FREQ_LOADING, SPEND_VALUE_LOADING, SPEND_NOISE_SD = 3.6, 1.1, 0.8, 0.2
ORDER_LOG_MEAN, ORDER_VALUE_LOADING, ORDER_NOISE_SD = 3.8, 0.7, 0.25
```

These are **calibrated**, not arbitrary: tuned so realized correlations land in
the target windows ρ(revenue, pre-spend) ∈ [0.55, 0.75] and
ρ(converted, pre-sessions) ∈ [0.08, 0.30]. Gate G1d and
`test_generator_correlations_in_target_ranges` both assert this, so the
calibration cannot silently drift.

Note `SPEND_LOG_MEAN = 3.6` → median pre-spend ≈ $36.6 over 4 weeks, and
`ORDER_LOG_MEAN = 3.8` → median order ≈ $44.7 (mean ≈ $59 after the lognormal
variance inflation). Plausible e-commerce numbers, which matters for the memo.

The comment block above these constants explains the two-latent design and is
the surviving record of the selection-bias incident. Read it.

### 4. Statistical design
```python
ALPHA = 0.05; POWER_TARGET = 0.80; MDE_RELATIVE = 0.08
```
Conventional. Be ready to say these are *conventions*, not laws — α = 0.05 comes
from Fisher's rule of thumb, and the right value is a business decision about
the relative cost of the two errors.

### 5. Margins and traffic
```python
AOV_NI_MARGIN_RELATIVE   = 0.02    # 2% relative
ERROR_NI_MARGIN_ABSOLUTE = 0.005   # 0.5pp absolute
USERS_PER_DAY            = 10_000
```
Relative for AOV (a 2% basket dip means the same thing at any price point),
absolute for the error rate (percentage points are how ops teams talk about
errors). `USERS_PER_DAY` is what turns a sample size into a *runtime in days*,
which is the unit stakeholders actually care about.

---

## `data/generate_data.py` — 141 lines

### `generate_experiment_data(n_users, seed, control_conversion_rate, conversion_lift, aov_effect, error_rate_increase)`

Returns a 7-column DataFrame, one row per user.

**Line by line:**

```python
rng = np.random.default_rng(seed)
```
Modern `Generator` API. Independent per call — no global state. Matters because
validation scripts call this 1,000 times in a loop with `seed=base+i`.

```python
q_freq  = rng.standard_normal(n_users)
q_value = rng.standard_normal(n_users)
```
The two independent latents. **The single most important design decision in the
file** (see §6 of the theory doc).

```python
group = rng.permuted(np.array(["control","treatment"]).repeat([n//2, n - n//2]))
```
Note: this builds an **exactly balanced** split and shuffles it, rather than
drawing `rng.choice(["control","treatment"], n)`.

- Exact balance removes assignment-ratio noise from the simulation, so the
  variance you measure is metric variance and nothing else. Cleaner for
  validating a *method*.
- The cost: the generator **cannot produce a sample ratio mismatch**, so SRM
  detection can never be exercised or demonstrated. That is an honest
  limitation, and a good "what would you add" answer.
- The `[n//2, n - n//2]` split handles odd n by giving the extra user to
  treatment.

```python
session_rate = np.exp(SESSIONS_LOG_MEAN + SESSIONS_FREQ_LOADING * q_freq)
pre_exp_sessions = rng.poisson(session_rate)
```
A Poisson with a lognormal rate — i.e. a **Poisson-lognormal mixture**, which is
overdispersed relative to a plain Poisson. That is realistic: real session
counts have variance well above their mean.

```python
pre_exp_spend = np.exp(SPEND_LOG_MEAN + 1.1*q_freq + 0.8*q_value + 0.2*noise)
```
Lognormal, loaded on **both** latents. This is what makes it a good CUPED
covariate for revenue: revenue depends on `q_freq` (via conversion) and
`q_value` (via basket size), and pre-spend sees both.

```python
w = CONVERSION_FREQ_LOADING                              # 0.95
conversion_latent = w*q_freq + sqrt(1 - w**2)*noise      # exactly N(0,1)
p_conversion = where(is_treatment, base*(1+lift), base)
converted = (conversion_latent > norm.ppf(1 - p_conversion)).astype(int)
```
The probit threshold. `norm.ppf(1 - p)` is **vectorized over the array**
`p_conversion`, so each user gets their arm's threshold in one call. Marginal
rate is exactly p per arm; correlation with `q_freq` is preserved. See theory §7.

```python
order_value = np.exp(ORDER_LOG_MEAN + ORDER_VALUE_LOADING*q_value + noise)
order_value = np.where(is_treatment, order_value*(1 + aov_effect), order_value)
revenue = converted * order_value
```
**`q_value` only — `q_freq` does not appear.** This is the selection-bias fix.
Basket size is independent of conversion propensity, so a conversion lift
cannot mechanically move AOV.

`revenue = converted * order_value` makes revenue exactly zero for
non-converters — a **zero-inflated** distribution with a heavy lognormal tail.
That structure is why revenue-per-user is high-variance and why CUPED helps it
so much. Asserted by `test_generator_marginal_rates`.

```python
p_error = np.where(is_treatment, CONTROL_ERROR_RATE + increase, CONTROL_ERROR_RATE)
checkout_error = rng.binomial(1, p_error)
```
Independent of both latents — errors are a property of the *flow*, not the user.
Deliberately simple: this guardrail is meant to be the easy, well-powered
contrast to AOV.

### `print_summary(df)`
Diagnostic only. Prints per-arm metrics and the two CUPED-relevant realized
correlations with their target windows inline — so running the module as a
script immediately tells you whether the calibration still holds.

**Failure modes to know:** `n_users < 2` breaks the group split;
`conversion_lift` large enough to push `p > 1` makes `norm.ppf` return `inf`
(everything fails to convert — silently wrong rather than raising). Neither is
guarded. An interviewer asking "how would you harden this?" wants exactly that
answer.

---

## `src/power.py` — 77 lines, 2 functions

### `required_sample_size_per_arm(baseline_rate, mde_relative, alpha, power) -> int`

```python
p1 = baseline_rate
p2 = baseline_rate * (1.0 + mde_relative)
p_bar = (p1 + p2) / 2.0
z_alpha = norm.ppf(1.0 - alpha / 2.0)     # two-sided
z_power = norm.ppf(power)
numerator = (z_alpha*sqrt(2*p_bar*(1-p_bar)) + z_power*sqrt(p1*(1-p1)+p2*(1-p2)))**2
return math.ceil(numerator / (p2 - p1)**2)
```

Points to be able to make:

- The **two square roots are different on purpose**: the first is the pooled
  null variance (the test's critical value is computed under H₀), the second is
  the unpooled alternative variance (the estimator's actual distribution under
  H₁). Conflating them is the most common error in hand-rolled power code.
- `math.ceil` — you cannot recruit a fraction of a user, and rounding *up* keeps
  achieved power at or above target. `test_power_at_recommended_n_hits_target`
  asserts `0.80 ≤ power < 0.81`, pinning both the direction and the size of the
  rounding effect.
- `norm.ppf(power)` not `norm.ppf(1 - power)`: z_{1−β} at β = 0.20 is
  z_{0.80} = 0.8416. A sign slip here is a classic bug and the statsmodels
  cross-check (G1c, `test_sample_size_matches_statsmodels`) is what catches it.
- Written out longhand **deliberately**, rather than calling
  `statsmodels.NormalIndPower`. The point of the project is to show the formula
  is understood, and the library then serves as an independent oracle. Note
  statsmodels uses the **arcsine-transformed (Cohen's h)** effect size, a
  genuinely different parameterization — which is why the agreement tolerance is
  1% rather than exact. Knowing *why* they differ slightly is a good detail.

### `achieved_power(n_per_arm, baseline_rate, mde_relative, alpha) -> float`

Algebraic inverse: solve the same equation for `z_power`, apply `Φ`. Used for
the power **curves** (sweep n, plot power) in `plots.py` and the dashboard.

Edge behaviour: at small n, `z_power` goes strongly negative and `norm.cdf`
returns ≈ 0 — correct, and it is what makes the power curves start at the origin
and rise smoothly.

---

## `src/cuped.py` — 51 lines, 2 functions, zero project imports

### `compute_theta(y, x) -> float`
```python
covariance_matrix = np.cov(y, x)
return covariance_matrix[0, 1] / covariance_matrix[1, 1]
```
`np.cov(y, x)` returns the 2×2 matrix `[[Var(y), Cov(y,x)], [Cov(y,x), Var(x)]]`,
so `[0,1]/[1,1]` is `Cov(y,x)/Var(x)`. Defaults to `ddof=1`.

Why `np.cov` rather than `np.polyfit(x, y, 1)[0]` or an `sklearn`
`LinearRegression`? Same number, but this is one allocation with no model
object, no fitting API, and it makes the formula visible in the source. For a
one-parameter estimator, pulling in a fitting framework is pure overhead.

**Edge case:** constant `x` ⇒ `Var(x) = 0` ⇒ division by zero ⇒ `nan`/`inf`.
Not guarded. Correct answer if asked: guard it and return θ = 0, since a
constant covariate carries no information and the adjustment should be a no-op.

### `cuped_adjust(y, x) -> np.ndarray`
```python
theta = compute_theta(y, x)
return y - theta * (x - np.mean(x))
```
Two lines implementing the whole method. Three properties, all in the docstring
and all unit-tested:
1. `Var(y_cuped) = Var(y)(1 − ρ²)`
2. `mean(y_cuped) = mean(y)` exactly (because x is centred)
3. unbiased for the treatment effect (because x is pre-experiment)

**Note what this function does NOT do:** it takes no `group` argument. It is
applied to the **pooled** array, and the arms are split *afterwards* by the
caller. That is the pooled-θ decision made structural — the API makes the
per-arm mistake awkward to commit.

**Note also what the project does not do:** `cuped_adjust` is never called
inside `evaluate_experiment`. CUPED is demonstrated in notebook 02 and the
dashboard, but the decision engine runs on raw metrics. This is a genuine gap —
see `04_decisions_and_alternatives.md`. Know it before you are asked.

---

## `src/tests_stats.py` — 216 lines, 3 dataclasses + 4 functions

### `difference_in_means(y_treatment, y_control, alpha) -> MeanDifferenceResult`

Two-sided estimation with CI and p-value. Used by the notebooks and dashboard
for *reporting* effects; the decision engine uses the one-sided tests instead.

```python
se = sqrt(np.var(y_t, ddof=1)/n_t + np.var(y_c, ddof=1)/n_c)
z_crit = norm.ppf(1 - alpha/2)
p_value = 2*(1 - norm.cdf(abs(estimate)/se))
```
`ddof=1` on both. `abs(estimate)` makes the two-sided p symmetric.

**Numerical note worth raising:** for very large |z|, `1 - norm.cdf(z)`
underflows to exactly 0.0 (catastrophic cancellation). `norm.sf(z)` is the
numerically stable form. Irrelevant here — a p-value of 1e-20 and a p-value of
0.0 lead to the same decision — but recognizing the issue signals numerical
literacy.

### `superiority_test(y_treatment, y_control, alpha) -> SuperiorityResult`

One-sided: H₀: μ_T ≤ μ_C vs H₁: μ_T > μ_C.
```python
p_value = 1 - norm.cdf(estimate / se)         # note: NOT abs()
ci_low  = estimate - norm.ppf(1 - alpha)*se   # one-sided lower bound
```
No `abs()` — direction matters. A negative estimate gives p > 0.5, correctly
reporting "no evidence of improvement."

`ci_low` is a **one-sided 95% lower confidence bound**, using `z_{0.95} = 1.645`,
not `z_{0.975} = 1.96`. `ci_low > 0` is exactly equivalent to `p < α`. That
equivalence is what `test_superiority_detects_improvement_and_not_null` checks.

**The justification for one-sided (be ready, it gets challenged):** the decision
is binary — ship or don't. "No effect" and "harm" lead to the identical action,
so they belong in the same null. Spending α on a two-sided alternative buys
information you will not act on, at the cost of power on the side you care
about. The counterargument — that one-sided tests are abused to manufacture
significance — is fair, and the defence is that the direction is fixed by the
*decision rule* before the data, not chosen after.

Nice touch in the test: the null case compares `control` against `control.copy()`
so the estimate is exactly 0.0 and p is exactly 0.5 — **deterministic**, not a
coin flip on whether a random draw happened to land significant. That is how you
write a non-flaky statistical test.

### `non_inferiority_test(y_t, y_c, margin, harm_direction, alpha) -> NonInferiorityResult`

The most substantial function in the repo. Validates `harm_direction` up front
and raises `ValueError` on anything else — fail fast rather than silently
choosing a branch.

```python
z_crit = norm.ppf(1 - alpha)                  # 1.645, one-sided
if harm_direction == "increase":
    p_value      = norm.cdf((estimate - margin)/se)
    ci_bound     = estimate + z_crit*se        # worst case: MOST harm
    best_case    = estimate - z_crit*se        # least harm
    ni_passed    = ci_bound  < margin
    inferior     = best_case > margin
    harm_detected= best_case > 0.0
else:                                          # "decrease", mirrored
    p_value      = 1 - norm.cdf((estimate + margin)/se)
    ci_bound     = estimate - z_crit*se
    best_case    = estimate + z_crit*se
    ni_passed    = ci_bound  > -margin
    inferior     = best_case < -margin
    harm_detected= best_case < 0.0
power = norm.cdf(margin/se - z_crit)
```

The two branches are **exact mirror images** — every comparison and sign flips.
Writing them out rather than multiplying by a sign variable makes each branch
independently readable and verifiable against the docstring. The unit test
`test_non_inferiority_directions` exercises both, plus all three outcome
classes.

`ci_bound` and `best_case` are the two ends of the same one-sided reasoning:
`ci_bound` is the most harm the data is compatible with, `best_case` the least.
`ni_passed` and `inferior` are two separate one-sided tests at level α; the gap
between them is INVESTIGATE.

`power = Φ(m/SE − z_{1−α})` — derived in theory §4. Depends only on the
**margin-to-noise ratio**, which is why it is a design diagnostic rather than a
data finding.

### `benjamini_hochberg(p_values, q) -> np.ndarray[bool]`

```python
order = np.argsort(p_values)
thresholds = (np.arange(1, m+1)/m) * q
passing = p_values[order] <= thresholds
rejected = np.zeros(m, dtype=bool)
if passing.any():
    k = np.max(np.nonzero(passing)[0])   # LARGEST passing index
    rejected[order[:k+1]] = True         # reject everything up to it
return rejected
```

Three things to point out:

1. **`np.max`, not `np.min`.** Step-**up**: find the largest k that passes, then
   reject all smaller ranks too, whether or not they individually passed. Using
   the first passing index would be wrong and would silently under-reject.
2. **`order[:k+1]`** maps back from sorted position to original position, so the
   returned mask aligns with the caller's input order. Getting this wrong
   attributes significance to the wrong metric — a silent, nasty bug.
3. **Returns a mask, not corrected p-values.** The caller needs a yes/no per
   metric; adjusted p-values would be a second concept to explain in the report
   for no decision-making gain.

The docstring carries the *policy* statement — why guardrails are excluded from
this family. Policy documented next to the mechanism that enforces it.

---

## `src/decision_engine.py` — 233 lines

### `MetricSpec` (dataclass)

Nine fields declaring how one metric is measured and judged: `name`, `kind`
("success"/"guardrail"), `column`, `test` ("proportion"/"mean"), `direction`,
`margin`, `margin_type` ("absolute"/"relative"), `converted_only`, `is_primary`.

`test` is **reporting metadata only** — both values take the identical code path,
because a proportion test on 0/1 data *is* a difference-in-means test. Say this
proactively if asked; it looks like a dispatch key and isn't.

`converted_only` is the escape hatch for converter-level metrics like AOV. Its
existence in the API is a reminder that such metrics are supported but
dangerous (theory §6).

### `MetricResult` and `DecisionReport` (dataclasses)

`MetricResult` pairs a spec with its result plus derived fields:
`margin_absolute` (the resolved margin after relative→absolute conversion),
`bh_significant`, `status`, `note`.

`DecisionReport` holds the verdict, the reasoning lines, all metric results, and
the α/power-floor settings used — so a report is **self-documenting**: you can
tell from the artifact alone what thresholds produced it. That matters for
auditability months later.

`DecisionReport.render()` builds markdown, branching on `kind` because success
and guardrail metrics have different fields worth showing. Note it is a method
on the data object, not a free function — but the *computation* is not, so the
Streamlit tab can render the same report differently without duplicating logic.

### `_metric_arrays(df, spec)` (private helper)
```python
rows = df[df["converted"] == 1] if spec.converted_only else df
values = rows[spec.column].values.astype(float)
is_treatment = (rows["group"] == "treatment").values
return values[is_treatment], values[~is_treatment]
```
Filter, extract, split. `.astype(float)` normalizes int columns (like `converted`)
so downstream variance math is uniform.

**The hidden coupling to be honest about:** the column names `"converted"` and
`"group"` are hardcoded. `"group"` with values `"control"`/`"treatment"` is the
engine's data contract and is reasonable; `"converted"` is a leak of the
synthetic schema into a general-purpose engine. The clean fix is a
`filter_column` field on `MetricSpec` (or a predicate callable). In practice it
does not bite notebook 04, because that analysis deliberately uses no
`converted_only` metric — but it *would* bite the next dataset.

### `evaluate_experiment(df, metric_specs, alpha, power_floor) -> DecisionReport`

**Stage 0 — partition and validate.**
```python
success    = [s for s in metric_specs if s.kind == "success"]
guardrails = [s for s in metric_specs if s.kind == "guardrail"]
primaries  = [s for s in success if s.is_primary]
if len(primaries) != 1:
    raise ValueError(...)
```
Exactly one primary, enforced. Zero primaries means no defined ship criterion;
two means an ambiguous one. This is the "one metric to rule them all" discipline
that experimentation platforms enforce, encoded as a precondition rather than a
convention.

**Stage 1 — success family.**
```python
for spec in success: success_results.append(superiority_test(y_t, y_c, alpha))
bh_mask = benjamini_hochberg([r.p_value for r in success_results], q=alpha)
```
All success tests run **first**, then BH is applied to the whole family at once.
It has to be that way — BH needs every p-value before it can decide any of them.
Structurally this is why the loop is split in two.

**Stage 2 — guardrail family.**
```python
margin_abs = spec.margin
if spec.margin_type == "relative":
    margin_abs = spec.margin * float(np.mean(y_c))
```
Relative margins resolve against the **control** mean, never the pooled mean.
Important: the pooled mean contains treatment's effect, so a relative margin
anchored on it would move with the very thing being tested — the tolerance would
shrink exactly when treatment did harm. Control is the pre-agreed reference
point. Small line, real statistical content, easy to get wrong.

**Stage 3 — classification.**
```python
if r.inferior:                            -> "harm",         any_harm = True
elif r.ni_passed and r.power >= floor:    -> "pass"  (+note if harm_detected)
elif r.ni_passed:                         -> "inconclusive"  (passed but underpowered)
else:                                     -> "inconclusive"  (not established)
```
The third branch is the interesting one: **non-inferiority passed, but power was
below the floor, so the verdict is still inconclusive.** Exactly the Hillstrom
case — NI established, 13% power, INVESTIGATE.

Be ready to argue both sides. *For:* under 13% power, even a harmless treatment
would be inconclusive ~87% of the time, so a pass reflects a large observed
effect rather than an adequate design, and the margin was never realistically
testable. *Against:* the confidence bound already contains all the evidence;
if the bound clears the margin, the claim is established at level α regardless
of what would have happened in other worlds. The engine takes the conservative
side and — crucially — **flags rather than blocks**: INVESTIGATE, not
DO NOT SHIP. That is the right response to a design concern as opposed to an
evidence concern.

The fourth branch distinguishes its two causes in the note text ("underpowered"
vs "estimate too close to the margin"), which is what makes the report
actionable — run longer versus the effect is genuinely borderline are different
problems with different fixes.

**Stage 4 — verdict precedence.**
```python
if any_harm:            "DO NOT SHIP"
elif not primary_ok:    "DO NOT SHIP"
elif any_inconclusive:  "INVESTIGATE"
else:                   "SHIP"
```
Harm first, deliberately: established harm vetoes a ship even when the primary
improved. Notebook 03's DO-NOT-SHIP scenario is precisely this — conversion
up and BH-significant, revenue up, but AOV harm beyond the margin. Verdict:
no ship. That ordering *is* the project's point of view.

### `default_metric_specs()`
The checkout experiment's metric hierarchy as data: conversion (primary
success), revenue per user (secondary success), AOV (guardrail, decrease, 2%
relative, converters only), checkout error rate (guardrail, increase, 0.5pp
absolute). Margins pulled from `config`.

Its existence keeps the "which metrics" question out of `evaluate_experiment`,
which is what lets notebook 04 pass a completely different list.

---

## `src/plots.py` — 146 lines, 3 chart builders

Design choices to be able to defend:

- **A single-hue blue ramp** (`BLUE_RAMP`, light → dark) for *ordered* series
  like increasing MDEs. Ordered data deserves an ordered (sequential) palette; a
  categorical rainbow would imply the series are unrelated categories.
- **Direct labels at line ends *and* a legend** — no series is identified by
  colour alone, which is the baseline accessibility requirement for
  colour-vision deficiency.
- **Recessive grid and axes** (`#e1e0d9` grid, `#898781` axes) so data is the
  most salient thing on the canvas.
- **Separate panels, never a dual axis**, in `plot_ci_comparison` — conversion
  (absolute pp) and revenue ($) live on different scales, and a twin y-axis
  invites false visual comparisons.
- **Every function returns the `Figure`** and never calls `plt.show()` or
  `savefig`. One function then serves notebooks, PNG export, and
  `st.pyplot(fig)`. Side-effect-free plotting.

`plot_power_curves` calls `achieved_power` across a 200-point grid of n;
`plot_ci_comparison` draws horizontal error bars from result dataclasses;
`plot_duration_comparison` draws labelled horizontal bars of days.

---

## `dashboard/app.py` — 191 lines, Streamlit, 3 tabs

```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
Repo root on the path so `config`/`src`/`data` import when Streamlit runs the
file from an arbitrary cwd. The `abspath`/`dirname`/`dirname` chain makes it
work regardless of where it is launched from — more robust than the notebooks'
relative `".."`, though the real fix is still packaging.

```python
plt.rcParams.update({... dark theme ...})
```
Set **once at module import**, not per figure. Matplotlib's default dark text is
invisible on Streamlit's dark background, so every colour is overridden
explicitly. `.streamlit/config.toml` sets `base = "dark"` for the chrome.

**Tab 1 — Design.** Four sliders (baseline, MDE, α, power) feeding
`required_sample_size_per_arm` live, with `st.metric` cards for users/arm, total
users, and **days at 10k/day**. The power-curve plot recomputes on every slider
move. This is the tab that makes power analysis *tangible*: drag the MDE slider
down and watch the sample size explode quadratically. If you demo one thing
live, demo this.

**Tab 2 — Variance Reduction.** `@st.cache_data` on `cuped_results()` — without
it, Streamlit re-simulates 140,458 users on every interaction. The cache is
keyed on function arguments, so this zero-argument function computes once per
session. Shows ρ, variance reduction, runtime saved, and raw-vs-CUPED CI plots
side by side.

**Tab 3 — Decision.** Three preset scenarios (as-designed 70k/arm; SHIP at
900k/arm with zero AOV harm; DO NOT SHIP at 900k/arm with −5% AOV harm), a radio
selector, and a colour-coded verdict banner via
`BANNER = {"SHIP": st.success, "DO NOT SHIP": st.error, "INVESTIGATE": st.warning}`
— a dict dispatch to Streamlit functions, which is a tidy way to avoid a
three-branch if. Then a bordered container per metric with effect, bound, p,
power and status.

Note the 1.8M-user scenarios are genuinely slow to simulate, which is exactly
why `run_scenario` is cached too, and why there is an `st.spinner`.

---

## `tests/test_stats.py` — 196 lines, 13 tests, ~1 second

| Test | What it pins down |
|---|---|
| `test_sample_size_matches_statsmodels` | our formula vs an independent implementation, <1% |
| `test_power_at_recommended_n_hits_target` | the two power functions are exact inverses; `ceil` pushes power into [0.80, 0.81) |
| `test_sample_size_decreases_with_larger_mde` | monotonicity — cheap, catches sign errors |
| `test_generator_marginal_rates` | realized rates match config; revenue is 0 iff not converted |
| `test_generator_reproducible` | same seed ⇒ identical frame; different seed ⇒ different |
| `test_theta_recovers_linear_coefficient` | θ = OLS slope, on `y = 5 + 2x + ε` |
| `test_cuped_preserves_mean_and_reduces_variance` | mean preserved; variance ratio = 1 − r² to 1e-9 |
| `test_cuped_uncorrelated_covariate_changes_nothing` | θ ≈ 0 ⇒ no-op (the null behaviour) |
| `test_difference_in_means_known_case` | estimate, CI ordering, and an A/A non-rejection |
| `test_superiority_detects_improvement_and_not_null` | detects a real lift; p = 0.5 exactly on a self-comparison |
| `test_non_inferiority_directions` | pass / inferior / within-margin-harm, in both directions |
| `test_benjamini_hochberg_known_cases` | hand-worked BH, including the step-up rescue |
| `test_generator_correlations_in_target_ranges` | the calibration cannot drift silently |

**The testing craft point worth making in an interview:** statistical tests are
prone to flakiness because they assert on random draws. This suite avoids it
three ways — comparing a sample against *itself* so the estimate is exactly
zero; using a deliberate mean shift of ~5 SEs so the assertion is effectively
deterministic; and asserting on **algebraic identities** (1 − r² to 1e-9)
rather than on statistical outcomes wherever possible. The comments in
`test_non_inferiority_directions` and
`test_superiority_detects_improvement_and_not_null` state this reasoning
explicitly.

---

## `validate_phase1.py` / `2` / `3` — simulation gates

Same shape in all three: a `report(gate, passed, detail)` helper prints
`PASS`/`FAIL` with the observed number and the expected range, and `main()`
accumulates with `all_passed &=`.

**Phase 1** (`significant_fraction` over 1,000 sims): G1a empirical power
0.78–0.82; G1b A/A false-positive rate 0.04–0.06; G1c formula vs statsmodels
<1%; G1d realized correlations in range.

**Phase 2** (1,000 sims): G2a estimator-level variance ratio within 0.10 of
1 − ρ̄²; G2b unbiasedness within 4 Monte-Carlo standard errors; G2c A/A
false-positive rate with CUPED still 0.04–0.06.

The G2a docstring is the most sophisticated piece of reasoning in the repo and
worth quoting nearly verbatim in an interview: the in-sample variance ratio
equals 1 − r² *as an algebraic identity* when θ is fit in-sample, so checking it
proves nothing; the non-tautological check is the variance of the **effect
estimator across independent simulations**. And the sim count is justified with
error bars — a ratio from 200 sims has MC standard error ≈ 0.05, so a 0.10
tolerance would be only 2 SEs and would false-alarm about 1 run in 20; at 1,000
sims it is ≈4 SEs. The 200-sim value is still printed for reference.

Also note G2b's tolerance is **derived, not hardcoded**:
`4 * std / sqrt(n_sims)` — four Monte-Carlo standard errors. A hardcoded
tolerance either flakes or hides bias depending on how lucky you got; a tolerance
in SE units is the right way to gate a stochastic assertion.

**Phase 3** (2,000–5,000 sims): G3a the NI test's size and power at a sample
size where analytic power is exactly 80% — checking that it passes ~5% of the
time when true harm sits *exactly at the margin* (that is the definition of test
size for a shifted null) and ~80% when harm is zero. G3b BH's empirical FDR
against the theoretical `q·m0/m = 0.025`, gated on both `fdr ≤ q` and within
3 MC standard errors. G3c the three canonical scenarios produce their verdicts.

`SHIP_SCENARIO_N_PER_ARM = 900_000` with a comment explaining *why* that number:
the AOV guardrail needs ~13× the primary's traffic to be adequately powered. The
constant documents the finding.

G3c's honest framing, stated in the module docstring: scenario seeds are **fixed
representative draws**, not rate estimates. The underlying rates are what G3a
and G1a validate. In other words the scenario gate is a regression test, not a
statistical claim — and saying so prevents overclaiming.

---

## The four notebooks

**01 — Power analysis.** Sample size at several MDEs, the power-curve figure,
then one simulated experiment at the recommended n analysed with
`statsmodels.proportions_ztest`. Result: +0.3161pp absolute (+8.92% relative),
95% CI [+0.119pp, +0.514pp], z = 3.138, p = 0.0017. The takeaway section makes
the key honest point — with 80% power, **1 in 5 identical experiments would miss
this real effect**, and that a single run is one draw.

**02 — CUPED.** Same experiment (same seed), both metrics adjusted.
Revenue: θ = 0.0433, ρ = 0.625, variance −39.0%, CI −21.9%, p 0.0018 → 0.0003.
Conversion: θ = 0.0182, ρ = 0.251, variance −6.3%, CI −3.2%. Then converts
variance reduction into days: revenue 14 → 8.6 days, conversion 14 → 13.2.
The observed reduction matches theoretical ρ² to the decimal, in both cases.

**03 — Decision engine.** The three scenarios with full rendered reports. The
framing to steal for interviews: *"the sample size that suffices for conversion
leaves the AOV guardrail at only ~20% power — relative to what the guardrails
need, the primary-powered sample size IS the underpowered case."*

**04 — Real data (Hillstrom).** 64,000 customers, MineThatData 2008.
Restricted to Womens E-Mail vs No E-Mail (dropping the Mens arm, because the
engine models a single treatment-vs-control contrast and three arms would need
their own multiplicity treatment). Three specs, zero engine changes.

Results: conversion +0.311pp (p = 0.0001, BH-significant), visit +4.52pp
(p < 0.0001), spend guardrail +$0.424 with worst-case bound +$0.210, clearing
the −$0.065 margin — yet **power is 13%**, so the verdict is INVESTIGATE. Then
real-data CUPED: ρ(spend, history) = 0.0195, variance reduction 0.038%.

Two design decisions are called out explicitly in the notebook: the two-arm
restriction, and the **all-user spend guardrail** rather than spend-per-converter
— carrying forward the selection-bias lesson from the synthetic incident. The
notebook also lists what a real analyst would request (recent per-user
pre-period panels, richer covariates, CUPAC, and a business-set margin reviewed
for power *at design time*).

---

## `reports/decision_memo.md`

The stakeholder deliverable, and the thing that distinguishes a data *scientist*
from a *statistician* in a hiring loop. Structure: recommendation first,
evidence second, projected impact third, caveats fourth, bottom line.

The recommendation is not "SHIP" or "DO NOT SHIP" — it is **"phased rollout with
live order-value monitoring and a pre-agreed automatic pause rule."** That is
what INVESTIGATE translates to in business terms: capture the upside while the
growing sample settles the open question.

It quantifies the upside (+$0.18/user × 10,000 users/day × 365 ≈ **$660k/year**,
~11,600 extra checkouts) and immediately labels it an *if-the-lift-holds
extrapolation, not a guarantee*. It explains the inconclusive guardrail in plain
language ("order value is only measurable on the ~3.5% of users who buy, so
verifying it at our standards needs roughly 13× the traffic — about six months")
and explicitly separates analytics calls from business calls ("widening the
tolerance needs finance's sign-off; that is a business call, not an analytics
call").

If you have 60 seconds to show one artifact to a hiring manager, show this one.
