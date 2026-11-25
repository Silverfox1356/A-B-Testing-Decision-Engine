"""Statistical tests for experiment analysis.

Contains the sample ratio mismatch (SRM) data-quality gate, the
difference-in-means estimator (used for raw and CUPED-adjusted metrics),
one-sided superiority tests for success metrics, shifted-hypothesis
non-inferiority tests for guardrail metrics, and the Benjamini-Hochberg
correction for the success-metric family.

Tail probabilities use norm.sf / chi2.sf rather than 1 - cdf: the complement
form loses all precision once the cdf rounds to 1.0, reporting p = 0.0 for
what is really 1e-20. It changes no decision here, but a p-value that is
exactly zero is a reporting artifact, not a result.
"""

from dataclasses import dataclass

import numpy as np
from scipy.stats import chi2 as chi2_dist
from scipy.stats import norm

import config


@dataclass
class SampleRatioResult:
    """Chi-square goodness-of-fit check on the assignment split."""

    n_treatment: int
    n_control: int
    observed_share: float   # treatment share of all assigned users
    expected_share: float
    chi2: float
    p_value: float
    mismatch: bool          # True means the experiment is not trustworthy


def sample_ratio_mismatch(
    n_treatment: int,
    n_control: int,
    expected_treatment_share: float = 0.5,
    alpha: float = config.SRM_ALPHA,
) -> SampleRatioResult:
    """Test whether the realized assignment split matches the intended one.

    Chi-square goodness of fit on two cells (1 degree of freedom):

        E_t = N * share,  E_c = N * (1 - share),  N = n_t + n_c
        chi2 = (n_t - E_t)^2 / E_t + (n_c - E_c)^2 / E_c
        p    = P(chi2_1 > observed)

    A significant result means users did not reach the arms in the intended
    proportion. That is almost never chance: it points at a bug in assignment,
    logging, bot filtering or the analysis join. It matters because every
    other test in this module assumes the two arms are exchangeable apart from
    treatment, and an SRM is direct evidence that they are not -- the users
    who went missing are usually a non-random subset, so the comparison is
    confounded and NO metric from the experiment can be trusted.

    This is why the gate runs before any metric is evaluated and why a failure
    invalidates the experiment rather than producing a ship/no-ship answer:
    the correct response is to fix the pipeline and re-run, not to reason
    about the metrics.

    `alpha` defaults to config.SRM_ALPHA (0.0005), far stricter than the
    project's 0.05 -- see the comment there for why.
    Reference: Kohavi, Tang & Xu (2020), ch. 21; Fabijan et al. (2019),
    "Diagnosing Sample Ratio Mismatch in Online Controlled Experiments".
    """
    if not 0.0 < expected_treatment_share < 1.0:
        raise ValueError(
            f"expected_treatment_share must be in (0, 1), got {expected_treatment_share!r}"
        )
    total = n_treatment + n_control
    if total == 0:
        raise ValueError("cannot check the sample ratio with zero assigned users")

    expected_t = total * expected_treatment_share
    expected_c = total * (1.0 - expected_treatment_share)
    statistic = (
        (n_treatment - expected_t) ** 2 / expected_t
        + (n_control - expected_c) ** 2 / expected_c
    )
    p_value = float(chi2_dist.sf(statistic, df=1))
    return SampleRatioResult(
        n_treatment=int(n_treatment),
        n_control=int(n_control),
        observed_share=n_treatment / total,
        expected_share=expected_treatment_share,
        chi2=float(statistic),
        p_value=p_value,
        mismatch=p_value < alpha,
    )


@dataclass
class MeanDifferenceResult:
    """Treatment-minus-control difference in means with CI and two-sided p-value."""

    estimate: float
    se: float
    ci_low: float
    ci_high: float
    p_value: float


def difference_in_means(
    y_treatment: np.ndarray,
    y_control: np.ndarray,
    alpha: float = config.ALPHA,
) -> MeanDifferenceResult:
    """Two-sample difference in means with an unpooled (Welch) standard error.

    Formulas:
        estimate = mean(y_t) - mean(y_c)
        se       = sqrt(var(y_t)/n_t + var(y_c)/n_c)
        CI       = estimate +/- z_{1-alpha/2} * se
        p        = 2 * (1 - Phi(|estimate| / se))    (two-sided z-test)

    Uses the normal approximation instead of a t distribution, which is
    appropriate at the sample sizes this project works with (tens of
    thousands per arm; the CLT covers binary, adjusted and zero-inflated
    metrics alike). Reference: standard large-sample z-test, e.g. Kohavi
    et al. (2020), ch. 17.
    """
    n_t, n_c = len(y_treatment), len(y_control)
    estimate = float(np.mean(y_treatment) - np.mean(y_control))
    se = float(np.sqrt(np.var(y_treatment, ddof=1) / n_t + np.var(y_control, ddof=1) / n_c))

    z_crit = norm.ppf(1.0 - alpha / 2.0)
    p_value = 2.0 * norm.sf(abs(estimate) / se)
    return MeanDifferenceResult(
        estimate=estimate,
        se=se,
        ci_low=estimate - z_crit * se,
        ci_high=estimate + z_crit * se,
        p_value=float(p_value),
    )


@dataclass
class SuperiorityResult:
    """One-sided test that treatment improves the metric (higher mean)."""

    estimate: float
    se: float
    ci_low: float   # one-sided lower confidence bound; > 0 means improvement
    p_value: float  # one-sided


def superiority_test(
    y_treatment: np.ndarray,
    y_control: np.ndarray,
    alpha: float = config.ALPHA,
) -> SuperiorityResult:
    """One-sided z-test of H0: mean(treatment) <= mean(control) vs H1: >.

    Formulas (unpooled SE; equals the two-proportion z-test when y is binary):
        estimate = mean(y_t) - mean(y_c)
        se       = sqrt(var(y_t)/n_t + var(y_c)/n_c)
        p        = 1 - Phi(estimate / se)
        lower confidence bound = estimate - z_{1-alpha} * se

    One-sided is justified for a ship decision: the feature ships only on
    IMPROVEMENT, so "no effect" and "harm" trigger the same action (do not
    ship) and belong in the same null hypothesis. Alpha is spent entirely on
    the improvement direction. Reference: Kohavi et al. (2020), ch. 17.

    Assumptions: independent users, large samples (normal approximation).
    The unpooled SE is used for both the test and the bound; at this
    project's sample sizes it is indistinguishable from the pooled version.
    """
    n_t, n_c = len(y_treatment), len(y_control)
    estimate = float(np.mean(y_treatment) - np.mean(y_control))
    se = float(np.sqrt(np.var(y_treatment, ddof=1) / n_t + np.var(y_control, ddof=1) / n_c))

    p_value = float(norm.sf(estimate / se))
    ci_low = estimate - norm.ppf(1.0 - alpha) * se
    return SuperiorityResult(estimate=estimate, se=se, ci_low=ci_low, p_value=p_value)


@dataclass
class NonInferiorityResult:
    """Shifted-hypothesis one-sided test that harm is smaller than the margin."""

    estimate: float       # treatment - control
    se: float
    margin: float         # absolute margin, in the harm direction's units
    ci_bound: float       # one-sided worst-case bound on the harm-direction side
    p_value: float        # one-sided; < alpha means non-inferiority established
    ni_passed: bool
    inferior: bool        # harm BEYOND the margin is established (ship blocker)
    harm_detected: bool   # CI excludes zero on the harmful side (informational)
    power: float          # a priori power to establish NI if true degradation is 0


def non_inferiority_test(
    y_treatment: np.ndarray,
    y_control: np.ndarray,
    margin: float,
    harm_direction: str,
    alpha: float = config.ALPHA,
) -> NonInferiorityResult:
    """Shifted-hypothesis one-sided z-test against a non-inferiority margin.

    With diff = mean(y_t) - mean(y_c) and an absolute margin m > 0:

        harm_direction = "increase" (e.g. error rate must not rise by more
        than m):   H0: diff >= +m   vs   H1: diff < +m
                   z = (diff - m) / se,        p = Phi(z)
                   worst-case bound = diff + z_{1-alpha} * se  (must be < m)

        harm_direction = "decrease" (e.g. order value must not drop by more
        than m):   H0: diff <= -m   vs   H1: diff > -m
                   z = (diff + m) / se,        p = 1 - Phi(z)
                   worst-case bound = diff - z_{1-alpha} * se  (must be > -m)

    Passing means: even the one-sided worst-case confidence bound stays
    inside the margin, so degradation of m or worse is rejected at level
    alpha. The test also reports:
    - inferior: whether harm BEYOND the margin is established, i.e. even the
      one-sided bound nearest to zero lies outside the margin. This is the
      DO-NOT-SHIP trigger. Note it is deliberately NOT "any significant
      harm": the margin exists because the business accepts degradation
      smaller than m, so a statistically significant but within-margin
      change must not block a ship.
    - harm_detected: whether the CI excludes ZERO on the harmful side.
      Informational only; with large samples tiny accepted degradations
      become statistically significant.
    - power: the a priori probability of establishing non-inferiority at
      this n if the true degradation is zero, Phi(m/se - z_{1-alpha}).
      Low power means "no verdict" is likely even for a harmless treatment,
      which is what flags a guardrail as underpowered (Type II risk: for
      guardrails the costly error is MISSING real harm).

    Reference: standard non-inferiority testing, e.g. FDA/ICH E9 framing;
    guardrail usage per Spotify's experimentation decision framework.
    Assumptions: independent users, large-sample normal approximation.
    """
    if harm_direction not in ("increase", "decrease"):
        raise ValueError(f"harm_direction must be 'increase' or 'decrease', got {harm_direction!r}")

    n_t, n_c = len(y_treatment), len(y_control)
    estimate = float(np.mean(y_treatment) - np.mean(y_control))
    se = float(np.sqrt(np.var(y_treatment, ddof=1) / n_t + np.var(y_control, ddof=1) / n_c))

    z_crit = norm.ppf(1.0 - alpha)
    if harm_direction == "increase":
        p_value = float(norm.cdf((estimate - margin) / se))
        ci_bound = estimate + z_crit * se        # worst case: most harm
        best_case = estimate - z_crit * se       # least harm
        ni_passed = ci_bound < margin
        inferior = best_case > margin
        harm_detected = best_case > 0.0
    else:
        p_value = float(norm.sf((estimate + margin) / se))
        ci_bound = estimate - z_crit * se
        best_case = estimate + z_crit * se
        ni_passed = ci_bound > -margin
        inferior = best_case < -margin
        harm_detected = best_case < 0.0

    power = float(norm.cdf(margin / se - z_crit))
    return NonInferiorityResult(
        estimate=estimate, se=se, margin=margin, ci_bound=ci_bound,
        p_value=p_value, ni_passed=ni_passed,
        inferior=inferior, harm_detected=harm_detected, power=power,
    )


def benjamini_hochberg(p_values: np.ndarray, q: float = config.ALPHA) -> np.ndarray:
    """Benjamini-Hochberg step-up procedure; returns a boolean rejection mask.

    Procedure (Benjamini & Hochberg 1995): sort the m p-values ascending,
    find the largest k with p_(k) <= (k/m) * q, and reject hypotheses 1..k.
    Controls the false discovery rate at level q under independence or
    positive dependence of the tests.

    Applied to the family of SUCCESS metrics only (primary + secondary).
    Guardrail non-inferiority tests are deliberately NOT alpha-corrected:
    correcting them would make it HARDER to detect harm, and for guardrails
    the costly error is missing real harm (Type II), not a false alarm.
    Their risk is reported as power instead (Spotify decision framework).
    """
    p_values = np.asarray(p_values, dtype=float)
    m = len(p_values)
    order = np.argsort(p_values)
    thresholds = (np.arange(1, m + 1) / m) * q

    passing = p_values[order] <= thresholds
    rejected = np.zeros(m, dtype=bool)
    if passing.any():
        k = np.max(np.nonzero(passing)[0])  # largest index meeting its threshold
        rejected[order[: k + 1]] = True
    return rejected
