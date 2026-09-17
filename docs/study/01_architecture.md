# 01 — Architecture

## The shape of the system

This is a **layered, dependency-inverted analysis library** with three
presentation surfaces on top of it. Every arrow points downward; there are no
cycles.

```
                 PRESENTATION
   notebooks/01..04      dashboard/app.py      reports/decision_memo.md
          |                     |
          +----------+----------+
                     |
                 ORCHESTRATION
           src/decision_engine.py
           (MetricSpec, evaluate_experiment, DecisionReport)
                     |
        +------------+------------+-------------+
        |            |            |             |
      STATISTICAL CORE (pure functions, no I/O, no state)
   src/power.py  src/cuped.py  src/tests_stats.py  src/plots.py
        |            |            |             |
        +------------+------------+-------------+
                     |
                 DATA LAYER
        data/generate_data.py      (+ Hillstrom CSV, notebook 04)
                     |
                 CONFIGURATION
                   config.py

   VERIFICATION (cuts across all layers, depends on everything)
   tests/test_stats.py        validate_phase1.py / 2 / 3
```

### Exact import graph

| Module | Imports from the project |
|---|---|
| `config.py` | nothing |
| `src/cuped.py` | nothing (pure numpy) |
| `src/power.py` | `config` |
| `src/tests_stats.py` | `config` |
| `src/plots.py` | `config`, `src.power` |
| `data/generate_data.py` | `config` |
| `src/decision_engine.py` | `config`, `src.cuped`, `src.tests_stats` |
| `dashboard/app.py` | `config`, `data`, `src.cuped`, `src.decision_engine`, `src.power`, `src.tests_stats` |
| `notebooks/01–04` | various, via `sys.path.insert(0, "..")` |
| `validate_phase1/2/3.py` | various |

Two facts to notice and be able to state:

1. **`src/cuped.py` imports nothing from the project.** It is 51 lines of pure
   math over numpy arrays. That is deliberate: CUPED is a general-purpose
   transformation, not something tied to this experiment's schema. It is the
   most reusable file in the repo.
2. **`src/decision_engine.py` is the only orchestrator.** It is the single place
   where statistics, business rules and metric definitions meet. Everything
   below it is context-free math; everything above it is presentation.

---

## Layer 1: `config.py` — the single source of truth

Every tunable number lives here: ground-truth effect sizes, latent-model
loadings, α, target power, MDE, guardrail margins, traffic assumption, seed.

**Why a config module rather than function defaults or a YAML file?**

- Against scattering constants at call sites: changing the ground truth in one
  place must change what the generator produces *and* what the validation
  scripts assert against. Scattered constants guarantee the two drift apart.
- Against YAML/JSON: a Python module gives you typed values, comments,
  arithmetic (`0.035 * 1.08`) and IDE navigation for free, with no parsing
  layer. The cost is that config is code — acceptable in a single-author
  analysis project, less so in a multi-tenant production platform where you
  would want config as data so it can be versioned and audited separately.
- Functions take config values as **default arguments**
  (`alpha: float = config.ALPHA`), not by reading the module inside the body.
  That keeps every function individually overridable — which is exactly what
  the Streamlit dashboard needs, since its sliders pass user-chosen α and
  power. Read-config-inside-the-body would have made the dashboard impossible
  without a refactor.

The config file is also the project's **documentation of intent**. The comment
block explaining the two-latent user model is arguably the most important
prose in the repo (see the incident in `04_decisions_and_alternatives.md`).

---

## Layer 2: `data/generate_data.py` — the simulator

One function, `generate_experiment_data(...)`, returns a per-user DataFrame:

```
user_id | group | pre_exp_sessions | pre_exp_spend | converted | revenue | checkout_error
```

This is the **schema contract** for the whole project. The decision engine
consumes a DataFrame in this shape; notebook 04 proves the contract is loose
enough that real data can be coerced into it (Hillstrom needs only a `group`
column added).

Design points worth defending:

- **Two independent latent factors per user** (`q_freq`, `q_value`) instead of
  one "user quality" factor. This is the fix to a real bug; see the incident
  write-up. Short version: one shared factor made a conversion lift
  mechanically depress treatment AOV through selection, not causation.
- **Pre-experiment columns are generated from the same latents as outcomes.**
  That is what makes CUPED have anything to work with. If the pre-period were
  independent noise, ρ = 0 and CUPED would be a no-op — which the unit test
  `test_cuped_uncorrelated_covariate_changes_nothing` verifies.
- **Probit threshold for conversion.** `converted = 1[w·q_f + √(1−w²)·ε > Φ⁻¹(1−p)]`.
  The latent index is exactly standard normal by construction, so thresholding
  at `Φ⁻¹(1−p)` gives a marginal conversion rate of exactly `p` while still
  correlating with `q_freq`. Getting both properties simultaneously is the
  whole trick.
- **Seeded `np.random.default_rng(seed)`**, not the legacy global
  `np.random.seed`. Generator objects are independent and don't leak state
  between calls — essential when validation scripts run 1,000 simulations in a
  loop.

---

## Layer 3: the statistical core

Four modules, all pure functions, all independently unit-testable.

### `src/power.py` (77 lines)
Two functions that are exact inverses of each other:
`required_sample_size_per_arm(...)` and `achieved_power(...)`.
No state, no I/O. The test `test_power_at_recommended_n_hits_target` asserts
the round trip.

### `src/cuped.py` (51 lines)
`compute_theta(y, x)` and `cuped_adjust(y, x)`. Two functions, one formula each.

### `src/tests_stats.py` (216 lines)
The largest core module. Four public entry points, three result dataclasses:

| Function | Returns | Used for |
|---|---|---|
| `sample_ratio_mismatch` | `SampleRatioResult` | the data-quality gate that runs before any metric |
| `difference_in_means` | `MeanDifferenceResult` | two-sided estimation + CI (notebooks, dashboard) |
| `superiority_test` | `SuperiorityResult` | success metrics (one-sided) |
| `non_inferiority_test` | `NonInferiorityResult` | guardrail metrics (shifted null) |
| `benjamini_hochberg` | boolean mask | multiplicity across the success family |

**Why dataclasses instead of tuples or dicts?** A tuple return of five floats is
unreadable at the call site (`r[3]` — which one is that?). A dict is readable
but untyped and typo-prone. A dataclass gives named, typed, IDE-completable
fields and is self-documenting in the report renderer. `NonInferiorityResult`
carries eight fields, including three separate booleans with genuinely
different meanings (`ni_passed`, `inferior`, `harm_detected`) — that would be
unmaintainable as a tuple.

### `src/plots.py` (146 lines)
Pure presentation: three chart builders that return matplotlib `Figure` objects
and never call `plt.show()` or write files. Returning the figure instead of
displaying it means the same function serves a notebook, a script saving a PNG,
and a Streamlit `st.pyplot()` call.

---

## Layer 4: `src/decision_engine.py` — the orchestrator

This is the architectural heart, and the thing to talk about if an interviewer
asks about *software design* rather than statistics.

### The key idea: metrics are declarative data, not code

```python
MetricSpec(
    name="average order value", kind="guardrail", column="revenue",
    test="mean", direction="decrease",
    margin=config.AOV_NI_MARGIN_RELATIVE, margin_type="relative",
    filter_column="converted",
)
```

A `MetricSpec` is a **declaration** of how a metric is measured and judged.
`evaluate_experiment(df, specs)` walks the list, dispatches each spec to the
right test, and combines the outcomes into a verdict.

**Why this matters:** notebook 04 runs the engine on a completely different
real-world dataset by writing three `MetricSpec` objects. Zero lines of engine
code changed. That is the payoff of separating *what to measure* from *how to
test it* — and it is the single strongest software-design point in the project.

The alternative — a function per metric, or a big `if metric_name == ...`
chain — would have required editing the engine for every new experiment.

### The three-stage pipeline inside `evaluate_experiment`

```
0. SRM GATE      chi-square on the assignment split, at SRM_ALPHA = 0.0005
                 mismatch -> return INVALID with NO metrics, short-circuit
1. VALIDATE      exactly one primary success metric, else ValueError
                 (MetricSpec.__post_init__ has already rejected a bad kind,
                  a guardrail with no margin, and covariate + filter_column)
2. SUCCESS FAMILY
     for each success spec -> _metric_arrays (filter, CUPED) -> superiority_test
     collect p-values -> benjamini_hochberg -> rejection mask
     record primary_ok
3. GUARDRAIL FAMILY
     for each guardrail spec:
       resolve relative margin against the CONTROL mean
       non_inferiority_test
       classify -> harm | pass | inconclusive
4. COMBINE       precedence: harm > primary failure > inconclusive > ship
```

### Verdict precedence (memorize this order)

```python
if srm.mismatch:        "INVALID"       # arms not comparable, no metrics at all
if any_harm:            "DO NOT SHIP"   # established harm vetoes everything
elif not primary_ok:    "DO NOT SHIP"   # no improvement, nothing to ship
elif any_inconclusive:  "INVESTIGATE"   # can't confirm safety
else:                   "SHIP"
```

INVALID sits outside the other three deliberately. DO NOT SHIP is a statement
about the *feature* -- we learned it is not good enough. INVALID is a statement
about the *experiment* -- we learned nothing at all, because the data cannot
support any claim. Collapsing them would tell a stakeholder the feature failed
when the truth is that the pipeline did.

The order encodes a value judgement: **proven harm outranks proven benefit.**
A treatment that lifts conversion but breaks a guardrail does not ship, full
stop. That is the whole point of having guardrails.

### Separation of computation and rendering

`evaluate_experiment` returns a `DecisionReport` — a data object. Formatting
lives in `DecisionReport.render()` (markdown) and separately in the Streamlit
tab (widgets). Two presentations, one computation. If the verdict logic lived
in the renderer, the dashboard and the notebook could disagree.

---

## Layer 5: verification — two different kinds

This is a distinction worth making explicitly in an interview, because most
portfolio projects have neither and almost none have both.

### `tests/test_stats.py` — unit tests (26 tests, ~3 seconds)
Deterministic, fast, assert *properties of functions*:
- our formula agrees with `statsmodels` within 1%
- `achieved_power` inverts `required_sample_size_per_arm`
- CUPED preserves the mean and reduces variance by exactly 1 − r² in-sample
- `compute_theta` recovers a known regression slope
- BH produces the textbook answer on hand-worked examples
- the generator's marginal rates match the configured ground truth
- the generator is reproducible under a fixed seed

### `validate_phase1/2/3.py` — simulation gates (thousands of sims, minutes)
Monte-Carlo, assert *statistical properties of the whole pipeline*:

| Gate | Claim under test | Method |
|---|---|---|
| G1a | the design really has 80% power | 1,000 sims at the recommended n, count rejections |
| G1b | α is really 5% | 1,000 A/A sims, count false positives |
| G1c | our formula ≈ statsmodels | direct comparison |
| G1d | generator correlations hit their targets | one large sim |
| G2a | CUPED's *estimator* variance ratio = 1 − ρ² | 1,000 sims, compare across-sim variances |
| G2b | CUPED is unbiased | 1,000 sims, mean effect vs truth, within 4 MC standard errors |
| G2c | CUPED does not inflate α | 1,000 A/A sims with CUPED |
| G3a | NI test has size α at the margin and 80% power at zero harm | 2,000 sims each |
| G3b | BH controls FDR at q | 5,000 sims of 10 tests, 5 true nulls |
| G3c | the three scenarios produce their verdicts | fixed representative seeds |
| G3d | the SRM gate's size and power | 20,000 fair-coin sims, 1,000 broken-split sims |

**The G2a subtlety is a great thing to raise unprompted.** The *in-sample*
variance ratio equals 1 − r² as an algebraic identity whenever θ is estimated
in-sample — checking it proves nothing about the method. So G2a instead
measures the variance of the **effect estimator across 1,000 independent
simulations**, which is not tautological. The docstring says exactly this. It
also explains why the gate uses 1,000 sims and not 200: a variance ratio from
200 sims has a Monte-Carlo standard error around 0.05, so a 0.10 tolerance
would be only 2 SEs and would false-alarm roughly 1 run in 20.

That is the kind of detail that separates "I ran a simulation" from "I
understand the error bars on my simulation."

---

## Layer 6: presentation surfaces

| Surface | Audience | Why it exists |
|---|---|---|
| Notebooks 01–04 | a technical reviewer reading the repo | narrative: design → variance reduction → decision → real data |
| `dashboard/app.py` | a stakeholder who wants to poke at it | interactivity: change MDE/α and watch sample size move |
| `reports/decision_memo.md` | product leadership | the deliverable a real analyst ships: a recommendation, not a p-value |

The memo matters more than it looks. It translates INVESTIGATE into a business
action ("phased rollout with a pre-agreed pause rule"), quantifies the upside
(~$660k/year), and states its own caveats. Interviewers for analytics roles
read that as evidence you can operate with stakeholders, which is usually the
scarcer skill.

---

## Cross-cutting conventions

- **Type hints everywhere**, including `float | None` unions (Python 3.10+).
- **Every public function has a docstring containing the actual formula** plus
  its assumptions and a literature reference. This was a deliberate policy:
  the formula in the docstring is what makes the code auditable by a
  statistician who does not read Python.
- **`ddof=1`** on every variance — sample variance, not population. Irrelevant
  numerically at n = 70,000; correct by principle, and free.
- **`sys.path.insert(0, "..")`** at the top of each notebook and the dashboard,
  so the repo root is importable without packaging. Honest assessment: this is
  the least defensible pattern in the project. The proper fix is a
  `pyproject.toml` with `pip install -e .`. Know this — it is an easy thing for
  an interviewer to spot.

---

## Data flow for one full run (trace this end to end)

```
config.py
   |  CONTROL_CONVERSION_RATE = 0.035, MDE_RELATIVE = 0.08, ALPHA, POWER_TARGET
   v
src/power.required_sample_size_per_arm(0.035, 0.08)  ->  70,229 per arm
   |
   v
data.generate_experiment_data(n_users=140_458, seed=204)  ->  DataFrame
   |
   +--> src.cuped.cuped_adjust(revenue, pre_exp_spend)  ->  39% less variance
   |
   v
src.decision_engine.evaluate_experiment(df, default_metric_specs())
   |
   +-- success:   superiority_test x2  ->  p-values  ->  benjamini_hochberg
   +-- guardrail: non_inferiority_test x2  ->  ni_passed / inferior / power
   |
   v
DecisionReport(verdict="INVESTIGATE", reasoning=[...], metrics=[...])
   |
   +--> .render()          -> markdown (notebook)
   +--> Streamlit widgets  -> dashboard tab 3
```
