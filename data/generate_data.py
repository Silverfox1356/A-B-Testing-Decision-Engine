"""Synthetic data generator for the checkout-flow A/B test.

Simulates users of an e-commerce platform in a randomized experiment:
a streamlined checkout flow (treatment) vs the existing flow (control).

The key modeling idea is persistent user heterogeneity via TWO independent
latent factors per user (a frequency/monetary decomposition):
  q_freq  drives conversion propensity, pre-experiment sessions and spend
  q_value drives order value and pre-experiment spend
Because both factors also drive PRE-experiment activity, pre-period
covariates predict in-experiment behavior, which is what makes CUPED
(Deng et al. 2013) reduce variance in later phases. Keeping q_value
independent of the conversion latent keeps average order value free of
selection bias when treatment lifts conversion (the marginal converters
differ in frequency, not in basket value).

All ground-truth effect sizes and distribution parameters live in config.py.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

import config


def generate_experiment_data(
    n_users: int,
    seed: int,
    control_conversion_rate: float = config.CONTROL_CONVERSION_RATE,
    conversion_lift: float = config.TRUE_CONVERSION_LIFT,
    aov_effect: float = config.TRUE_AOV_EFFECT,
    error_rate_increase: float = config.TRUE_ERROR_RATE_INCREASE,
    treatment_share: float = 0.5,
) -> pd.DataFrame:
    """Simulate one experiment and return a per-user DataFrame.

    Columns: user_id, group ('control'/'treatment'), pre_exp_sessions,
    pre_exp_spend, converted, revenue, checkout_error.

    Model, per user with independent latents q_f, q_v ~ N(0, 1):
      pre_exp_sessions ~ Poisson(exp(a_s + b_s * q_f))               (overdispersed count)
      pre_exp_spend    = exp(a_p + b_f * q_f + b_v * q_v + sd_p * noise)
      converted        = 1 if w*q_f + sqrt(1 - w^2)*noise > z_group  (probit threshold)
      revenue          = converted * order_value,
        order_value    = exp(a_o + c_v * q_v + sd_o * noise) * (1 + aov_effect if treated)
      checkout_error   ~ Bernoulli(p_err_group), independent of the latents

    The probit threshold z_group = Phi^-1(1 - p_group) makes the MARGINAL
    conversion rate exactly p_group while still correlating conversion with
    q_f (loading w = config.CONVERSION_FREQ_LOADING). Treatment effects:
    conversion rate is multiplied by (1 + conversion_lift), order value by
    (1 + aov_effect), and the error rate gets +error_rate_increase absolute.

    Assumptions: users are independent, assignment is a random split
    independent of both latents, and treatment effects are homogeneous
    across users.

    `treatment_share` sets the fraction assigned to treatment. The default
    0.5 produces an EXACTLY balanced split rather than a binomial one, which
    keeps assignment-ratio noise out of the simulation so that measured
    variance is metric variance alone. The consequence is that the default
    generator can never produce a sample ratio mismatch; pass a share away
    from the intended one (e.g. 0.49 against an expected 0.5) to simulate the
    broken-assignment case the SRM gate exists to catch.
    """
    if not 0.0 < treatment_share < 1.0:
        raise ValueError(f"treatment_share must be in (0, 1), got {treatment_share!r}")
    rng = np.random.default_rng(seed)

    q_freq = rng.standard_normal(n_users)
    q_value = rng.standard_normal(n_users)
    n_treatment = int(round(n_users * treatment_share))
    group = rng.permuted(
        np.array(["control", "treatment"]).repeat([n_users - n_treatment, n_treatment])
    )
    is_treatment = group == "treatment"

    # Pre-experiment activity (4 weeks before the test), driven by the latents.
    session_rate = np.exp(config.SESSIONS_LOG_MEAN + config.SESSIONS_FREQ_LOADING * q_freq)
    pre_exp_sessions = rng.poisson(session_rate)
    pre_exp_spend = np.exp(
        config.SPEND_LOG_MEAN
        + config.SPEND_FREQ_LOADING * q_freq
        + config.SPEND_VALUE_LOADING * q_value
        + config.SPEND_NOISE_SD * rng.standard_normal(n_users)
    )

    # Conversion via a probit latent threshold: the latent index is standard
    # normal, so cutting it at Phi^-1(1 - p) yields marginal rate exactly p.
    w = config.CONVERSION_FREQ_LOADING
    conversion_latent = w * q_freq + np.sqrt(1.0 - w**2) * rng.standard_normal(n_users)
    p_conversion = np.where(
        is_treatment,
        control_conversion_rate * (1.0 + conversion_lift),
        control_conversion_rate,
    )
    converted = (conversion_latent > norm.ppf(1.0 - p_conversion)).astype(int)

    # Revenue: zero unless converted; order value is lognormal in q_value
    # only (independent of the conversion latent, so a conversion lift does
    # not shift converter composition on basket value), scaled
    # multiplicatively by the treatment's AOV effect.
    order_value = np.exp(
        config.ORDER_LOG_MEAN
        + config.ORDER_VALUE_LOADING * q_value
        + config.ORDER_NOISE_SD * rng.standard_normal(n_users)
    )
    order_value = np.where(is_treatment, order_value * (1.0 + aov_effect), order_value)
    revenue = converted * order_value

    # Checkout errors: independent of quality (not a CUPED metric).
    p_error = np.where(
        is_treatment,
        config.CONTROL_ERROR_RATE + error_rate_increase,
        config.CONTROL_ERROR_RATE,
    )
    checkout_error = rng.binomial(1, p_error)

    return pd.DataFrame(
        {
            "user_id": np.arange(n_users),
            "group": group,
            "pre_exp_sessions": pre_exp_sessions,
            "pre_exp_spend": pre_exp_spend,
            "converted": converted,
            "revenue": revenue,
            "checkout_error": checkout_error,
        }
    )


def print_summary(df: pd.DataFrame) -> None:
    """Print group-level metrics and the realized CUPED-relevant correlations."""
    for name, g in df.groupby("group"):
        aov = g.loc[g["converted"] == 1, "revenue"].mean()
        print(
            f"{name:>9}: n={len(g):,}  conversion={g['converted'].mean():.4f}  "
            f"AOV={aov:.2f}  revenue/user={g['revenue'].mean():.2f}  "
            f"error_rate={g['checkout_error'].mean():.4f}"
        )

    control = df[df["group"] == "control"]
    rho_revenue = control["revenue"].corr(control["pre_exp_spend"])
    rho_conversion = control["converted"].corr(control["pre_exp_sessions"])
    print(f"\nRealized correlations (control group):")
    print(f"  corr(revenue, pre_exp_spend)      = {rho_revenue:.3f}  (target ~0.55-0.75)")
    print(f"  corr(converted, pre_exp_sessions) = {rho_conversion:.3f}  (target ~0.08-0.30)")


if __name__ == "__main__":
    df = generate_experiment_data(n_users=140_000, seed=config.RANDOM_SEED)
    print_summary(df)
