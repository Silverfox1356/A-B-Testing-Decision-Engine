# Experimentation Decision Engine

A/B testing with power analysis, CUPED variance reduction, and a risk-aware
ship/no-ship decision engine with guardrail metrics. Built as a data science
portfolio project; every statistical claim is backed by a simulation-based
validation gate you can run yourself.

## Motivation

Most A/B test writeups stop at "p < 0.05, ship it". Real experimentation
platforms (Microsoft ExP, Spotify, Netflix) do three harder things:

1. **Design for power**: know how many users a minimum detectable effect
   requires before running anything.
2. **Reduce variance**: use pre-experiment data (CUPED) so the same traffic
   yields tighter confidence intervals and shorter experiments.
3. **Decide under risk**: a feature ships only if its success metrics improve
   AND its guardrail metrics are proven not to have degraded past a
   business-set tolerance, with multiple-comparison control on the success
   family and explicit Type II risk on the guardrails.

This project implements all three, end to end, on a simulated e-commerce
checkout experiment and on a real 64,000-user e-mail experiment.

## The scenario

An e-commerce platform tests a streamlined checkout flow (treatment) against
the existing flow (control).

| role | metric | criterion |
|---|---|---|
| primary success | checkout conversion rate | significant improvement (one-sided, BH-corrected) |
| secondary success | revenue per user | significant improvement (one-sided, BH-corrected) |
| guardrail | average order value | must not drop more than 2% (non-inferiority) |
| guardrail | checkout error rate | must not rise more than 0.5pp (non-inferiority) |

Verdicts: **SHIP** (primary improved and every guardrail cleared with adequate
power), **DO NOT SHIP** (primary failed or harm beyond a margin established),
**INVESTIGATE** (a guardrail is inconclusive, usually underpowered).

## Methodology and references

- **Power analysis**: explicit two-proportion z-test formula (Fleiss, Levin &
  Paik 2003), cross-checked against statsmodels within 1%.
- **CUPED**: theta = Cov(Y,X)/Var(X) computed from the covariance formula,
  pooled across arms (Deng, Xu, Kohavi & Walker 2013, "Improving the
  Sensitivity of Online Controlled Experiments by Utilizing Pre-Experiment
  Data", WSDM).
- **Superiority + non-inferiority testing**: one-sided z-tests; guardrails use
  shifted-hypothesis tests against the margin, reporting the CI relative to
  the margin and the a priori power (Kohavi, Tang & Xu 2020, "Trustworthy
  Online Controlled Experiments"; Spotify engineering's guardrail decision
  framework, which motivates why guardrails report Type II risk instead of
  receiving alpha correction).
- **Multiplicity**: Benjamini-Hochberg (1995) across the success-metric family
  only.

## Repository structure

```
config.py                    all parameters: ground truth, alpha, power, margins, traffic
data/generate_data.py        synthetic generator (two-latent user model, exact marginal rates)
src/power.py                 sample size and power, explicit formulas
src/cuped.py                 theta and the CUPED adjustment
src/tests_stats.py           superiority, non-inferiority, BH correction
src/decision_engine.py       MetricSpec, evaluate_experiment, DecisionReport
src/plots.py                 shared plotting utilities
notebooks/01..04             power design, CUPED, decision engine, real data
dashboard/app.py             Streamlit dashboard (dark theme, three tabs)
tests/test_stats.py          pytest unit tests for the statistical core
validate_phase1..3.py        simulation-based validation gates (see below)
reports/decision_memo.md     one-page stakeholder memo
```

## How to run everything

```bash
pip install -r requirements.txt

# validation gates (each prints PASS/FAIL per gate)
python validate_phase1.py     # power ~80%, A/A ~5%, formula vs statsmodels, correlations
python validate_phase2.py     # CUPED variance reduction = 1-rho^2, unbiasedness, A/A FPR
python validate_phase3.py     # NI test size and power, BH FDR control, scenario verdicts

# unit tests
python -m pytest tests/ -q

# notebooks (or open interactively)
jupyter nbconvert --to notebook --execute --inplace notebooks/01_power_analysis.ipynb

# dashboard
streamlit run dashboard/app.py
```

Notebook 04 downloads the Hillstrom CSV (~5 MB) into `data/` on first run.

## Key results

- Detecting a +8% relative lift on a 3.5% conversion baseline needs ~70k users
  per arm (14 days at 10k users/day):

  ![Power curves](reports/figures/power_curves.png)

- CUPED removes ~39% of revenue-per-user variance (exactly the theoretical
  rho^2 for the realized rho = 0.62 covariate correlation) but only ~6% for
  the rare binary conversion metric, matching published industry experience:

  ![Raw vs CUPED confidence intervals](reports/figures/cuped_ci_comparison.png)

  ![Experiment duration by method](reports/figures/experiment_duration.png)

- On the real Hillstrom experiment (Womens E-Mail vs No E-Mail), conversion
  and visits improve decisively, the all-user spend guardrail clears its
  margin, and the engine still says INVESTIGATE because the guardrail design
  had only ~13% power. Real-data CUPED with a year-long history covariate
  yields a real but tiny 0.04% variance reduction (rho = 0.02): the method is
  identical to the synthetic case; the covariate quality decides the gain.

## An incident worth reading about

Midway through Phase 3, the SHIP demo refused to pass: with a ZERO true
order-value effect, treatment AOV kept landing ~2% below control across seeds.
The diagnosis was post-treatment conditioning: one latent "user quality"
factor drove both conversion propensity and order value, so lifting conversion
pulled lower-quality marginal users into the treatment converter pool and
mechanically depressed their average order value, silently consuming the
entire 2% non-inferiority margin. The fix was a two-latent generator
(purchase frequency vs basket value, independent), after which AOV is unbiased
by construction; every Phase 1 and Phase 2 gate was re-run and passed. The
industry lesson, applied in notebook 04: prefer ALL-USER metrics for
guardrails; per-converter ratio metrics condition on a post-treatment variable
and can show "harm" that is pure composition shift. Full story in
`project_log.md` (local, gitignored) and summarized in notebook 04.

## Limitations and extensions

- **CUPAC**: CUPED with a single covariate is the base case; predicting the
  outcome from all pre-experiment features (CUPAC) is the natural upgrade and
  would materially help the real-data case, where one year-long covariate
  correlates at only 0.02 with two-week spend.
- **Sequential testing**: this project analyzes fixed-horizon experiments;
  production platforms add always-valid inference or group-sequential
  boundaries so experiments can be peeked at safely.
- **Heterogeneous treatment effects**: everything here estimates average
  effects; segment-level analysis (HTE) is the standard next question after a
  SHIP verdict.
- **Guardrail power is expensive**: powering a 2% AOV margin needs ~13x the
  traffic of the primary conversion test. Real teams widen margins, switch to
  all-user formulations, or accept explicit Type II risk; the engine surfaces
  the trade-off rather than hiding it.
- The synthetic generator uses homogeneous treatment effects and independent
  users; no network effects, novelty decay, or seasonality.
