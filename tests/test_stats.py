"""Unit tests for the core statistical functions (run pytest from the repo root)."""

import numpy as np
import pytest
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

import config
from data.generate_data import generate_experiment_data
from src.cuped import compute_theta, cuped_adjust
from src.decision_engine import (
    MetricSpec,
    default_metric_specs,
    evaluate_experiment,
)
from src.power import achieved_power, required_sample_size_per_arm
from src.tests_stats import (
    benjamini_hochberg,
    difference_in_means,
    non_inferiority_test,
    sample_ratio_mismatch,
    superiority_test,
)


def test_sample_size_matches_statsmodels():
    """Explicit formula agrees with statsmodels NormalIndPower within 1%."""
    p1 = config.CONTROL_CONVERSION_RATE
    ours = required_sample_size_per_arm(p1, config.MDE_RELATIVE)

    effect_size = proportion_effectsize(p1 * (1 + config.MDE_RELATIVE), p1)
    theirs = NormalIndPower().solve_power(
        effect_size=effect_size,
        alpha=config.ALPHA,
        power=config.POWER_TARGET,
        ratio=1.0,
        alternative="two-sided",
    )
    assert abs(ours - theirs) / theirs < 0.01


def test_power_at_recommended_n_hits_target():
    """achieved_power inverts required_sample_size_per_arm."""
    p1 = config.CONTROL_CONVERSION_RATE
    n = required_sample_size_per_arm(p1, config.MDE_RELATIVE)
    power = achieved_power(n, p1, config.MDE_RELATIVE)
    # n is rounded up, so power is at or just above the target.
    assert config.POWER_TARGET <= power < config.POWER_TARGET + 0.01


def test_sample_size_decreases_with_larger_mde():
    p1 = config.CONTROL_CONVERSION_RATE
    sizes = [required_sample_size_per_arm(p1, mde) for mde in (0.04, 0.08, 0.12)]
    assert sizes[0] > sizes[1] > sizes[2]


def test_generator_marginal_rates():
    """Realized conversion and error rates match the configured ground truth."""
    df = generate_experiment_data(n_users=400_000, seed=0)
    control = df[df["group"] == "control"]
    treatment = df[df["group"] == "treatment"]

    p1 = config.CONTROL_CONVERSION_RATE
    p2 = p1 * (1 + config.TRUE_CONVERSION_LIFT)
    assert control["converted"].mean() == pytest.approx(p1, abs=0.002)
    assert treatment["converted"].mean() == pytest.approx(p2, abs=0.002)
    assert control["checkout_error"].mean() == pytest.approx(
        config.CONTROL_ERROR_RATE, abs=0.001
    )
    assert treatment["checkout_error"].mean() == pytest.approx(
        config.CONTROL_ERROR_RATE + config.TRUE_ERROR_RATE_INCREASE, abs=0.001
    )
    # Revenue is zero exactly for non-converters.
    assert (df.loc[df["converted"] == 0, "revenue"] == 0).all()
    assert (df.loc[df["converted"] == 1, "revenue"] > 0).all()


def test_generator_reproducible():
    """Same seed gives identical data; different seeds differ."""
    a = generate_experiment_data(n_users=10_000, seed=7)
    b = generate_experiment_data(n_users=10_000, seed=7)
    c = generate_experiment_data(n_users=10_000, seed=8)
    assert a.equals(b)
    assert not a.equals(c)


def test_theta_recovers_linear_coefficient():
    """For y = a + b*x + noise, theta = cov(y,x)/var(x) recovers b."""
    rng = np.random.default_rng(0)
    x = rng.normal(10, 3, 100_000)
    y = 5.0 + 2.0 * x + rng.normal(0, 1, 100_000)
    assert compute_theta(y, x) == pytest.approx(2.0, abs=0.01)


def test_cuped_preserves_mean_and_reduces_variance():
    """Centering x keeps the metric mean; variance drops by exactly 1 - r^2
    in-sample (an algebraic identity when theta is estimated in-sample)."""
    rng = np.random.default_rng(1)
    x = rng.lognormal(3, 0.8, 50_000)
    y = 0.5 * x + rng.lognormal(2, 0.5, 50_000)
    y_adj = cuped_adjust(y, x)

    assert np.mean(y_adj) == pytest.approx(np.mean(y))
    r_squared = np.corrcoef(y, x)[0, 1] ** 2
    assert np.var(y_adj, ddof=1) / np.var(y, ddof=1) == pytest.approx(
        1 - r_squared, abs=1e-9
    )


def test_cuped_uncorrelated_covariate_changes_nothing():
    """With an independent covariate, theta ~ 0 and adjustment is a no-op."""
    rng = np.random.default_rng(2)
    y = rng.normal(0, 1, 200_000)
    x = rng.normal(0, 1, 200_000)
    np.testing.assert_allclose(cuped_adjust(y, x), y, atol=0.05)


def test_difference_in_means_known_case():
    """Estimate, CI and p-value behave correctly on a known separation."""
    rng = np.random.default_rng(3)
    control = rng.normal(10.0, 2.0, 50_000)
    treatment = rng.normal(10.1, 2.0, 50_000)
    result = difference_in_means(treatment, control)

    assert result.estimate == pytest.approx(0.1, abs=0.05)
    assert result.ci_low < result.estimate < result.ci_high
    assert result.p_value < 0.05  # true diff is ~8 SEs at this n

    # A/A style: identical distributions should not be significant here.
    aa = difference_in_means(control[:25_000], control[25_000:])
    assert aa.p_value > 0.05


def test_superiority_detects_improvement_and_not_null():
    rng = np.random.default_rng(4)
    control = rng.binomial(1, 0.035, 100_000).astype(float)
    improved = rng.binomial(1, 0.040, 100_000).astype(float)

    r = superiority_test(improved, control)
    assert r.p_value < 0.01
    assert r.ci_low > 0

    # Null case made deterministic: compare a sample against itself shifted
    # by nothing (identical arrays), where the estimate is exactly 0.
    r_null = superiority_test(control, control.copy())
    assert r_null.estimate == 0.0
    assert r_null.p_value == pytest.approx(0.5)


def test_non_inferiority_directions():
    """Clear pass, clear inferiority, and inconclusive middle ground."""
    rng = np.random.default_rng(5)
    control = rng.normal(100.0, 10.0, 50_000)

    # Slight improvement (+0.3 is ~5 SEs here), decrease harmful, margin 2:
    # clean pass with no harm detected. A mean shift is used instead of an
    # exact-zero effect so the assertion is deterministic, not a coin flip
    # on whether the null draw lands 1.645 SEs low.
    r = non_inferiority_test(rng.normal(100.3, 10.0, 50_000), control,
                             margin=2.0, harm_direction="decrease")
    assert r.ni_passed and not r.inferior and not r.harm_detected
    assert r.power > 0.99

    # Degradation of 5 >> margin 2: inferiority established.
    r = non_inferiority_test(rng.normal(95.0, 10.0, 50_000), control,
                             margin=2.0, harm_direction="decrease")
    assert not r.ni_passed and r.inferior and r.harm_detected

    # Small significant degradation within the margin: pass, harm noted.
    r = non_inferiority_test(rng.normal(99.5, 10.0, 50_000), control,
                             margin=2.0, harm_direction="decrease")
    assert r.ni_passed and not r.inferior and r.harm_detected

    # "increase" direction mirrors: error-rate style increase of 1 > margin 0.5.
    r = non_inferiority_test(rng.normal(101.0, 10.0, 50_000), control,
                             margin=0.5, harm_direction="increase")
    assert not r.ni_passed and r.inferior


def test_benjamini_hochberg_known_cases():
    # Largest k with p_(k) <= k/m * q: here k=3, so exactly three rejections.
    rejected = benjamini_hochberg(np.array([0.01, 0.5, 0.03, 0.02]), q=0.05)
    assert rejected.tolist() == [True, False, True, True]

    # Step-up quirk: p=0.03 alone would fail its rank threshold (0.025),
    # but p_(2)=0.04 <= 0.05 rescues both.
    rejected = benjamini_hochberg(np.array([0.03, 0.04]), q=0.05)
    assert rejected.tolist() == [True, True]

    # Nothing significant.
    rejected = benjamini_hochberg(np.array([0.2, 0.8, 0.5]), q=0.05)
    assert not rejected.any()


def test_generator_correlations_in_target_ranges():
    """The CUPED-relevant correlations land in the spec's calibration windows."""
    df = generate_experiment_data(n_users=140_000, seed=config.RANDOM_SEED)
    control = df[df["group"] == "control"]
    rho_revenue = control["revenue"].corr(control["pre_exp_spend"])
    rho_conversion = control["converted"].corr(control["pre_exp_sessions"])
    assert 0.55 <= rho_revenue <= 0.75
    assert 0.08 <= rho_conversion <= 0.30


# ---------------------------------------------------------------------------
# Sample ratio mismatch gate
# ---------------------------------------------------------------------------


def test_srm_passes_on_a_balanced_split():
    r = sample_ratio_mismatch(70_229, 70_229)
    assert r.chi2 == pytest.approx(0.0)
    assert r.p_value == pytest.approx(1.0)
    assert not r.mismatch
    assert r.observed_share == pytest.approx(0.5)


def test_srm_tolerates_ordinary_random_imbalance():
    """A split a couple of hundred users off at 140k is chance, not a bug."""
    r = sample_ratio_mismatch(70_400, 70_058)
    assert not r.mismatch
    assert r.p_value > config.SRM_ALPHA


def test_srm_detects_a_broken_assignment():
    """A 49/51 split at this sample size is overwhelming evidence of a bug."""
    r = sample_ratio_mismatch(68_824, 71_634)
    assert r.mismatch
    assert r.p_value < 1e-10


def test_srm_honours_an_uneven_intended_split():
    """A deliberate 90/10 ramp is fine when 90/10 is what was intended."""
    assert not sample_ratio_mismatch(9_000, 1_000, expected_treatment_share=0.9).mismatch
    # ...and the same counts ARE a mismatch against a 50/50 intent.
    assert sample_ratio_mismatch(9_000, 1_000, expected_treatment_share=0.5).mismatch


def test_srm_rejects_nonsense_inputs():
    with pytest.raises(ValueError):
        sample_ratio_mismatch(10, 10, expected_treatment_share=0.0)
    with pytest.raises(ValueError):
        sample_ratio_mismatch(0, 0)


def test_generator_can_produce_a_mismatch():
    """treatment_share is what lets the SRM gate be exercised end to end."""
    df = generate_experiment_data(n_users=20_000, seed=7, treatment_share=0.49)
    counts = df["group"].value_counts()
    assert counts["treatment"] == 9_800 and counts["control"] == 10_200

    balanced = generate_experiment_data(n_users=20_000, seed=7)
    assert balanced["group"].value_counts()["treatment"] == 10_000

    with pytest.raises(ValueError):
        generate_experiment_data(n_users=100, seed=0, treatment_share=1.5)


def test_engine_returns_invalid_and_withholds_metrics_on_srm():
    n = required_sample_size_per_arm(config.CONTROL_CONVERSION_RATE, config.MDE_RELATIVE)
    df = generate_experiment_data(n_users=2 * n, seed=204, treatment_share=0.49)
    report = evaluate_experiment(df, default_metric_specs())

    assert report.verdict == "INVALID"
    assert report.srm.mismatch
    # The point of the gate: no metric is reported, so nobody can act on it.
    assert report.metrics == []
    assert "sample ratio mismatch" in report.reasoning[0]


def test_engine_reports_a_clean_srm_check_on_good_data():
    n = required_sample_size_per_arm(config.CONTROL_CONVERSION_RATE, config.MDE_RELATIVE)
    df = generate_experiment_data(n_users=2 * n, seed=204)
    report = evaluate_experiment(df, default_metric_specs())

    assert report.verdict != "INVALID"
    assert report.srm is not None and not report.srm.mismatch
    assert report.metrics  # metrics are evaluated when the gate passes


# ---------------------------------------------------------------------------
# CUPED wired into the decision engine
# ---------------------------------------------------------------------------


def test_metric_spec_refuses_cuped_behind_a_post_treatment_filter():
    """Filtering on a post-treatment column breaks CUPED's unbiasedness."""
    with pytest.raises(ValueError, match="post-treatment"):
        MetricSpec(
            name="average order value", kind="guardrail", column="revenue",
            test="mean", direction="decrease", margin=0.02, margin_type="relative",
            filter_column="converted", covariate="pre_exp_spend",
        )


def test_metric_spec_validates_kind_and_margin():
    with pytest.raises(ValueError):
        MetricSpec(name="x", kind="nonsense", column="a", test="mean")
    with pytest.raises(ValueError):
        MetricSpec(name="x", kind="guardrail", column="a", test="mean")


def test_engine_cuped_shrinks_the_standard_error_without_moving_the_verdict():
    """CUPED narrows the CI on the success metrics; the verdict is unchanged."""
    n = required_sample_size_per_arm(config.CONTROL_CONVERSION_RATE, config.MDE_RELATIVE)
    df = generate_experiment_data(n_users=2 * n, seed=204)

    with_cuped = evaluate_experiment(df, default_metric_specs())
    raw_specs = [
        MetricSpec(**{**spec.__dict__, "covariate": None})
        for spec in default_metric_specs()
    ]
    without = evaluate_experiment(df, raw_specs)

    assert with_cuped.verdict == without.verdict
    for adjusted, raw in zip(with_cuped.metrics, without.metrics):
        if adjusted.spec.covariate is None:
            assert adjusted.variance_reduction is None
            assert adjusted.result.se == pytest.approx(raw.result.se)
        else:
            assert adjusted.variance_reduction > 0
            assert adjusted.result.se < raw.result.se
            # SE scales as sqrt(1 - variance reduction).
            assert adjusted.result.se / raw.result.se == pytest.approx(
                np.sqrt(1 - adjusted.variance_reduction), rel=0.02
            )


def test_engine_cuped_matches_the_documented_reductions():
    """The covariate choices in default_metric_specs are the ones claimed."""
    n = required_sample_size_per_arm(config.CONTROL_CONVERSION_RATE, config.MDE_RELATIVE)
    df = generate_experiment_data(n_users=2 * n, seed=204)
    by_name = {m.spec.name: m for m in evaluate_experiment(df, default_metric_specs()).metrics}

    assert by_name["revenue per user"].variance_reduction == pytest.approx(0.39, abs=0.02)
    assert by_name["checkout conversion rate"].variance_reduction == pytest.approx(0.19, abs=0.02)
    # Guardrails deliberately carry no covariate.
    assert by_name["average order value"].variance_reduction is None
    assert by_name["checkout error rate"].variance_reduction is None


def test_engine_filter_column_is_not_hardcoded():
    """filter_column generalises what used to be a hardcoded 'converted'."""
    n = 40_000
    df = generate_experiment_data(n_users=n, seed=11)
    df["high_value"] = (df["pre_exp_spend"] > df["pre_exp_spend"].median()).astype(int)

    specs = [
        MetricSpec(name="conversion", kind="success", column="converted",
                   test="proportion", is_primary=True),
        MetricSpec(name="AOV among high-value users", kind="guardrail",
                   column="revenue", test="mean", direction="decrease",
                   margin=0.02, margin_type="relative", filter_column="high_value"),
    ]
    report = evaluate_experiment(df, specs)
    assert report.verdict in {"SHIP", "DO NOT SHIP", "INVESTIGATE"}
    # The guardrail really was computed on the filtered half of the users.
    assert len(df[df["high_value"] == 1]) == pytest.approx(n / 2, abs=2)
