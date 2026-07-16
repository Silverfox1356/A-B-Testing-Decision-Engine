"""Power analysis for a two-proportion z-test (checkout conversion rate).

Implements the standard sample-size and power formulas explicitly so every
step is inspectable; unit tests cross-check against statsmodels.
Reference: Fleiss, Levin & Paik (2003), "Statistical Methods for Rates and
Proportions", ch. 4; Kohavi et al. (2020), "Trustworthy Online Controlled
Experiments", ch. 17.
"""

import math

from scipy.stats import norm

import config


def required_sample_size_per_arm(
    baseline_rate: float,
    mde_relative: float,
    alpha: float = config.ALPHA,
    power: float = config.POWER_TARGET,
) -> int:
    """Users needed PER ARM to detect a relative lift with a two-proportion z-test.

    Formula (two-sided alpha, equal arm sizes):

        n = (z_{1-alpha/2} * sqrt(2 * p_bar * (1 - p_bar))
             + z_{power} * sqrt(p1*(1-p1) + p2*(1-p2)))^2 / (p2 - p1)^2

    where p1 = baseline_rate, p2 = p1 * (1 + mde_relative), and
    p_bar = (p1 + p2) / 2. The first term uses the pooled variance under the
    null (p1 = p2), the second the unpooled variance under the alternative.

    Assumptions: independent Bernoulli outcomes, 50/50 assignment, and a
    normal approximation to the binomial (fine at these n and rates).
    Reference: Fleiss, Levin & Paik (2003), eq. 4.14.
    """
    p1 = baseline_rate
    p2 = baseline_rate * (1.0 + mde_relative)
    p_bar = (p1 + p2) / 2.0

    z_alpha = norm.ppf(1.0 - alpha / 2.0)
    z_power = norm.ppf(power)

    numerator = (
        z_alpha * math.sqrt(2.0 * p_bar * (1.0 - p_bar))
        + z_power * math.sqrt(p1 * (1.0 - p1) + p2 * (1.0 - p2))
    ) ** 2
    return math.ceil(numerator / (p2 - p1) ** 2)


def achieved_power(
    n_per_arm: int,
    baseline_rate: float,
    mde_relative: float,
    alpha: float = config.ALPHA,
) -> float:
    """Power of the two-proportion z-test at a given per-arm sample size.

    Inverts the sample-size formula: solve for z_power and apply Phi.

        z_power = (|p2 - p1| * sqrt(n) - z_{1-alpha/2} * sqrt(2 * p_bar * (1-p_bar)))
                  / sqrt(p1*(1-p1) + p2*(1-p2))
        power   = Phi(z_power)

    Same assumptions and reference as required_sample_size_per_arm.
    """
    p1 = baseline_rate
    p2 = baseline_rate * (1.0 + mde_relative)
    p_bar = (p1 + p2) / 2.0

    z_alpha = norm.ppf(1.0 - alpha / 2.0)
    z_power = (
        abs(p2 - p1) * math.sqrt(n_per_arm)
        - z_alpha * math.sqrt(2.0 * p_bar * (1.0 - p_bar))
    ) / math.sqrt(p1 * (1.0 - p1) + p2 * (1.0 - p2))
    return float(norm.cdf(z_power))
