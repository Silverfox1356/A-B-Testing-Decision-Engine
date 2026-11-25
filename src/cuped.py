"""CUPED: Controlled-experiment Using Pre-Experiment Data.

Reduces the variance of an experiment metric by regressing out a
pre-experiment covariate, which tightens confidence intervals and shortens
experiments without biasing the treatment effect.
Reference: Deng, Xu, Kohavi & Walker (2013), "Improving the Sensitivity of
Online Controlled Experiments by Utilizing Pre-Experiment Data" (WSDM 2013).
"""

import numpy as np


def compute_theta(y: np.ndarray, x: np.ndarray) -> float:
    """OLS-optimal CUPED coefficient.

    Formula: theta = Cov(y, x) / Var(x)

    This theta minimizes Var(y - theta * x), the variance of the adjusted
    metric (Deng et al. 2013, section 3.1).

    Assumptions: x is measured BEFORE the experiment (so treatment cannot
    affect it) and both variables have finite variance. y and x should be
    passed pooled across both arms: under randomization x has the same
    distribution in each arm, so a pooled theta is a treatment-independent
    constant and introduces no bias.

    A constant covariate carries no information, so theta is defined as 0
    there rather than left as the 0/0 the formula would produce; the
    adjustment then correctly reduces to a no-op.
    """
    covariance_matrix = np.cov(y, x)
    variance_x = covariance_matrix[1, 1]
    if variance_x == 0.0:
        return 0.0
    return covariance_matrix[0, 1] / variance_x


def cuped_adjust(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Return the CUPED-adjusted metric.

    Formula: y_cuped = y - theta * (x - mean(x)),  theta = Cov(y, x) / Var(x)

    Properties (Deng et al. 2013):
    - Var(y_cuped) = Var(y) * (1 - rho^2), where rho = Corr(y, x), so the
      variance reduction grows with the covariate correlation.
    - Centering x keeps mean(y_cuped) = mean(y), so adjusted values stay on
      the metric's original scale.
    - The difference in adjusted group means is an unbiased estimate of the
      treatment effect because randomization gives E[x | treatment] =
      E[x | control], so the subtracted term has the same expectation in
      both arms.

    Works for binary y as well (it is a linear adjustment; no distributional
    assumption on y is needed), though the gain is small when the achievable
    correlation is low, as with rare conversion outcomes.

    IMPORTANT -- the unbiasedness argument above rests on
    E[x | treatment] = E[x | control], which randomization guarantees only on
    the FULL randomized population. Applying this within a subgroup selected
    by a post-treatment variable (converters, say) breaks it: treatment
    changes who is in the subgroup, so the arms' covariate means genuinely
    differ and the subtracted term no longer has equal expectations. The
    correction then injects bias rather than removing noise. See
    decision_engine.MetricSpec, which refuses the combination outright.
    """
    theta = compute_theta(y, x)
    return y - theta * (x - np.mean(x))
