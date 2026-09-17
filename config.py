"""Single source of truth for all simulation and analysis parameters.

Business scenario: an e-commerce platform tests a streamlined checkout flow
(Treatment) against the existing flow (Control). Changing a ground-truth
value here changes what the synthetic data generator produces, so every
validation script can be re-run against a modified truth.
"""

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Ground-truth treatment effects (what the generator injects)
# ---------------------------------------------------------------------------
CONTROL_CONVERSION_RATE = 0.035   # baseline checkout conversion rate
TRUE_CONVERSION_LIFT = 0.08       # relative lift: treatment converts at 3.5% * 1.08

TRUE_AOV_EFFECT = -0.01           # relative change in average order value under
                                  # treatment (slightly negative so the guardrail
                                  # analysis is interesting but passes the margin)

CONTROL_ERROR_RATE = 0.012        # baseline checkout error / abandonment rate
TRUE_ERROR_RATE_INCREASE = 0.001  # absolute increase (+0.1pp) under treatment

# ---------------------------------------------------------------------------
# Latent user model (drives the CUPED covariate correlations)
#
# Each user has TWO independent latent factors, mirroring the classic
# frequency/monetary decomposition of customer behavior:
#   q_freq  ~ N(0, 1): purchase FREQUENCY propensity; drives conversion,
#             pre-experiment sessions and (partly) pre-experiment spend
#   q_value ~ N(0, 1): BASKET VALUE; drives order value and (partly)
#             pre-experiment spend
# Keeping order value independent of the conversion latent matters: if one
# factor drove both, a conversion lift would pull lower-quality users into
# the converter pool and mechanically depress treatment AOV (selection
# bias), corrupting the AOV guardrail. Loadings below are calibrated so
# realized correlations land in the spec targets:
#   corr(revenue, pre_exp_spend)      ~ 0.55 - 0.75  (control group)
#   corr(converted, pre_exp_sessions) ~ 0.08 - 0.30  (control group)
# ---------------------------------------------------------------------------
CONVERSION_FREQ_LOADING = 0.95     # corr between conversion latent and q_freq

SESSIONS_LOG_MEAN = 1.6            # Poisson(exp(mean + loading * q_freq)) sessions
SESSIONS_FREQ_LOADING = 0.25

SPEND_LOG_MEAN = 3.6               # lognormal 4-week pre-experiment spend
SPEND_FREQ_LOADING = 1.1
SPEND_VALUE_LOADING = 0.8
SPEND_NOISE_SD = 0.2

ORDER_LOG_MEAN = 3.8               # lognormal order value for converters
ORDER_VALUE_LOADING = 0.7
ORDER_NOISE_SD = 0.25

# ---------------------------------------------------------------------------
# Statistical design
# ---------------------------------------------------------------------------
ALPHA = 0.05                # significance level (two-sided for the baseline test)
POWER_TARGET = 0.80
MDE_RELATIVE = 0.08         # minimum detectable effect, relative lift on conversion

# Sample ratio mismatch (SRM) gate. Deliberately far stricter than ALPHA: this
# chi-square runs on EVERY experiment, so at alpha = 0.05 one healthy
# experiment in twenty would be thrown out. 0.0005 is the threshold Kohavi et
# al. (2020, ch. 21) recommend -- a genuine SRM is an assignment or logging
# bug and produces p-values orders of magnitude below this, while random
# imbalance almost never does.
SRM_ALPHA = 0.0005

# ---------------------------------------------------------------------------
# Guardrail non-inferiority margins (used from Phase 3 onward)
# ---------------------------------------------------------------------------
AOV_NI_MARGIN_RELATIVE = 0.02      # AOV must not drop by more than 2%
ERROR_NI_MARGIN_ABSOLUTE = 0.005   # error rate must not rise by more than 0.5pp

# ---------------------------------------------------------------------------
# Traffic assumption (used to translate sample size into runtime)
# ---------------------------------------------------------------------------
USERS_PER_DAY = 10_000
