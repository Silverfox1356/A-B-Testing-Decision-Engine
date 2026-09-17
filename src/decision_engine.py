"""Risk-aware ship/no-ship decision engine.

Runs a sample ratio mismatch (SRM) data-quality gate, then combines one-sided
superiority tests on success metrics (BH-corrected as a family) with
non-inferiority tests on guardrail metrics (uncorrected, with Type II risk
reported as power) into a single verdict:

  INVALID       the assignment split does not match the intended one, so the
                arms are not comparable and no metric can be trusted.
  SHIP          primary metric significantly improved (after BH) AND every
                guardrail established non-inferiority with adequate power.
  DO NOT SHIP   primary failed, or any guardrail shows statistically
                significant harm.
  INVESTIGATE   otherwise: some guardrail is inconclusive (usually because
                the experiment is underpowered for that guardrail).

Metrics may declare a pre-experiment covariate, in which case the metric is
CUPED-adjusted before testing, which shrinks its standard error and (for
guardrails) raises its power against the margin.

Modeled on the Microsoft ExP metric hierarchy and Spotify's guardrail
decision framework.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config
from src.cuped import cuped_adjust
from src.tests_stats import (
    NonInferiorityResult,
    SampleRatioResult,
    SuperiorityResult,
    benjamini_hochberg,
    non_inferiority_test,
    sample_ratio_mismatch,
    superiority_test,
)


@dataclass
class MetricSpec:
    """Declares how one metric is measured and judged.

    kind:       "success" (must improve) or "guardrail" (must not degrade)
    column:     DataFrame column holding the per-user value
    test:       "proportion" (binary column) or "mean" (continuous column).
                Both take the same code path -- a proportion test on a 0/1
                column IS a difference in means -- so this is a label for the
                report, telling the reader what kind of metric it is.
    direction:  for success metrics, the improvement direction (always
                "increase" here); for guardrails, the direction of HARM
    margin:     guardrails only; the non-inferiority margin, expressed per
                margin_type
    margin_type:"absolute" (e.g. +0.5pp on an error rate) or "relative"
                (e.g. 2% of the control mean)
    filter_column: restrict the analysis to rows where this column equals 1
                (e.g. "converted", for average order value). None means all
                randomized users.
    covariate:  pre-experiment column to CUPED-adjust the metric with, or
                None for the raw metric.
    is_primary: exactly one success metric drives the SHIP verdict

    filter_column and covariate cannot be combined, and __post_init__ rejects
    the pair. A filter on a post-treatment column selects a different
    subpopulation in each arm, which breaks the E[x | treatment] =
    E[x | control] identity CUPED's unbiasedness rests on. Measured on this
    project's generator with a TRUE average-order-value effect of exactly
    zero, CUPED on converters-only revenue returns +$0.70 (12 Monte Carlo
    standard errors from zero over 400 simulations) against a $1.18 margin --
    the raw estimator stays unbiased. The bias points toward passing, which
    is the worst possible direction for a safety check, so the combination is
    refused rather than documented.
    """

    name: str
    kind: str
    column: str
    test: str
    direction: str = "increase"
    margin: float | None = None
    margin_type: str = "absolute"
    filter_column: str | None = None
    covariate: str | None = None
    is_primary: bool = False

    def __post_init__(self) -> None:
        if self.kind not in ("success", "guardrail"):
            raise ValueError(f"kind must be 'success' or 'guardrail', got {self.kind!r}")
        if self.covariate is not None and self.filter_column is not None:
            raise ValueError(
                f"metric {self.name!r}: covariate={self.covariate!r} cannot be combined "
                f"with filter_column={self.filter_column!r}. Filtering on a "
                f"post-treatment column breaks CUPED's unbiasedness (see MetricSpec "
                f"docstring); drop the covariate or analyse all randomized users."
            )
        if self.kind == "guardrail" and self.margin is None:
            raise ValueError(f"guardrail metric {self.name!r} requires a margin")


@dataclass
class MetricResult:
    spec: MetricSpec
    result: SuperiorityResult | NonInferiorityResult
    margin_absolute: float | None = None
    bh_significant: bool | None = None   # success metrics, after BH
    variance_reduction: float | None = None  # CUPED metrics; share of variance removed
    status: str = ""                     # "pass" / "fail" / "harm" / "inconclusive"
    note: str = ""


@dataclass
class DecisionReport:
    verdict: str
    reasoning: list[str]
    metrics: list[MetricResult] = field(default_factory=list)
    srm: SampleRatioResult | None = None
    alpha: float = config.ALPHA
    power_floor: float = config.POWER_TARGET

    def render(self) -> str:
        """Render the report as a markdown block."""
        lines = [
            f"# Decision report",
            "",
            f"## VERDICT: {self.verdict}",
            "",
            *[f"- {reason}" for reason in self.reasoning],
            "",
            f"alpha = {self.alpha}, guardrail power floor = {self.power_floor:.0%}",
            "",
        ]
        if self.srm is not None:
            srm = self.srm
            lines += [
                f"### sample ratio check "
                f"({'MISMATCH' if srm.mismatch else 'ok'})",
                f"- treatment {srm.n_treatment:,} / control {srm.n_control:,} "
                f"= {srm.observed_share:.4%} vs {srm.expected_share:.2%} intended",
                f"- chi-square = {srm.chi2:.3f}, p = {srm.p_value:.3g}",
                "",
            ]
        for m in self.metrics:
            r = m.result
            lines.append(f"### {m.spec.name} ({m.spec.kind}, {m.spec.test} test)")
            if m.spec.kind == "success":
                lines += [
                    f"- effect: {r.estimate:+.5f} (one-sided 95% lower bound {r.ci_low:+.5f})",
                    f"- one-sided superiority p = {r.p_value:.4f}; "
                    f"significant after BH: {'YES' if m.bh_significant else 'NO'}",
                ]
            else:
                direction = "+" if m.spec.direction == "increase" else "-"
                lines += [
                    f"- effect: {r.estimate:+.5f}, "
                    f"margin: {direction}{m.margin_absolute:.5f} "
                    f"({m.spec.margin_type} {m.spec.margin}), "
                    f"worst-case bound: {r.ci_bound:+.5f}",
                    f"- non-inferiority p = {r.p_value:.4f} "
                    f"({'established' if r.ni_passed else 'NOT established'}); "
                    f"power to clear margin if harmless = {r.power:.0%}",
                ]
            if m.variance_reduction is not None:
                lines.append(
                    f"- CUPED on '{m.spec.covariate}': "
                    f"{m.variance_reduction:.1%} of metric variance removed"
                )
            lines.append(f"- status: {m.status.upper()}{'  (' + m.note + ')' if m.note else ''}")
            lines.append("")
        return "\n".join(lines)


def _metric_arrays(
    df: pd.DataFrame, spec: MetricSpec
) -> tuple[np.ndarray, np.ndarray, float | None]:
    """Per-arm value arrays for a metric, plus the CUPED variance reduction.

    Applies the spec's row filter, then -- if a covariate is declared --
    CUPED-adjusts the metric on the POOLED sample before splitting by arm.
    Pooling is what keeps theta a treatment-independent constant; adjusting
    each arm separately would make theta a function of that arm's outcomes.
    Returns (treatment values, control values, variance reduction or None).
    """
    rows = df[df[spec.filter_column] == 1] if spec.filter_column else df
    values = rows[spec.column].values.astype(float)
    is_treatment = (rows["group"] == "treatment").values

    variance_reduction = None
    if spec.covariate is not None:
        covariate = rows[spec.covariate].values.astype(float)
        adjusted = cuped_adjust(values, covariate)
        raw_variance = float(np.var(values, ddof=1))
        if raw_variance > 0.0:
            variance_reduction = 1.0 - float(np.var(adjusted, ddof=1)) / raw_variance
        values = adjusted

    return values[is_treatment], values[~is_treatment], variance_reduction


def evaluate_experiment(
    df: pd.DataFrame,
    metric_specs: list[MetricSpec],
    alpha: float = config.ALPHA,
    power_floor: float = config.POWER_TARGET,
    expected_treatment_share: float = 0.5,
    srm_alpha: float = config.SRM_ALPHA,
) -> DecisionReport:
    """Run the SRM gate and every metric's test, and combine into a verdict.

    The sample ratio check runs FIRST and short-circuits: if the realized
    split does not match `expected_treatment_share`, the arms are not
    comparable and no metric is evaluated at all. Reporting metrics from an
    experiment with a known assignment bug invites someone to act on them, so
    the engine withholds them and returns INVALID.

    Success metrics then get one-sided superiority tests, BH-corrected as one
    family at level alpha. Guardrails get uncorrected non-inferiority tests
    (see benjamini_hochberg docstring for why) plus an a priori power check
    against power_floor; a guardrail that neither establishes
    non-inferiority nor shows significant harm is inconclusive.
    """
    success = [s for s in metric_specs if s.kind == "success"]
    guardrails = [s for s in metric_specs if s.kind == "guardrail"]
    primaries = [s for s in success if s.is_primary]
    if len(primaries) != 1:
        raise ValueError(f"exactly one primary success metric required, got {len(primaries)}")

    is_treatment = (df["group"] == "treatment").values
    srm = sample_ratio_mismatch(
        n_treatment=int(is_treatment.sum()),
        n_control=int((~is_treatment).sum()),
        expected_treatment_share=expected_treatment_share,
        alpha=srm_alpha,
    )
    if srm.mismatch:
        return DecisionReport(
            verdict="INVALID",
            reasoning=[
                f"sample ratio mismatch: treatment share {srm.observed_share:.4%} vs "
                f"{srm.expected_share:.2%} intended "
                f"(chi-square p = {srm.p_value:.3g} < {srm_alpha})",
                "the arms are not comparable, so no metric was evaluated; "
                "fix assignment or logging and re-run the experiment",
            ],
            metrics=[],
            srm=srm,
            alpha=alpha,
            power_floor=power_floor,
        )

    results: list[MetricResult] = []

    success_results, success_reductions = [], []
    for spec in success:
        y_t, y_c, reduction = _metric_arrays(df, spec)
        success_results.append(superiority_test(y_t, y_c, alpha))
        success_reductions.append(reduction)
    bh_mask = benjamini_hochberg([r.p_value for r in success_results], q=alpha)

    primary_ok = False
    for spec, r, reduction, significant in zip(
        success, success_results, success_reductions, bh_mask
    ):
        status = "pass" if significant else "fail"
        if spec.is_primary:
            primary_ok = bool(significant)
        results.append(MetricResult(
            spec=spec, result=r, bh_significant=bool(significant),
            variance_reduction=reduction, status=status,
        ))

    any_harm, any_inconclusive = False, False
    for spec in guardrails:
        y_t, y_c, reduction = _metric_arrays(df, spec)
        margin_abs = spec.margin
        if spec.margin_type == "relative":
            margin_abs = spec.margin * float(np.mean(y_c))
        r = non_inferiority_test(y_t, y_c, margin_abs, spec.direction, alpha)

        if r.inferior:
            status, note = "harm", "harm beyond the margin is statistically established"
            any_harm = True
        elif r.ni_passed and r.power >= power_floor:
            status, note = "pass", ""
            if r.harm_detected:
                note = "significant but within-margin degradation (accepted cost)"
        elif r.ni_passed:
            status, note = "inconclusive", f"non-inferior but power {r.power:.0%} below floor"
            any_inconclusive = True
        else:
            reason = (f"underpowered ({r.power:.0%} < {power_floor:.0%})"
                      if r.power < power_floor else "estimate too close to the margin")
            status, note = "inconclusive", f"non-inferiority not established: {reason}"
            any_inconclusive = True
        results.append(MetricResult(
            spec=spec, result=r, margin_absolute=margin_abs,
            variance_reduction=reduction, status=status, note=note,
        ))

    reasoning = []
    primary_name = primaries[0].name
    if any_harm:
        verdict = "DO NOT SHIP"
        reasoning.append("harm beyond a guardrail margin is statistically established")
    elif not primary_ok:
        verdict = "DO NOT SHIP"
        reasoning.append(f"primary metric '{primary_name}' shows no significant improvement after BH correction")
    elif any_inconclusive:
        verdict = "INVESTIGATE"
        reasoning.append("primary improved, but at least one guardrail is inconclusive")
    else:
        verdict = "SHIP"
        reasoning.append(f"primary metric '{primary_name}' significantly improved after BH correction")
        reasoning.append("all guardrails non-inferior with adequate power")

    return DecisionReport(
        verdict=verdict, reasoning=reasoning, metrics=results, srm=srm,
        alpha=alpha, power_floor=power_floor,
    )


def default_metric_specs() -> list[MetricSpec]:
    """The checkout experiment's metric hierarchy, margins from config.

    Covariate choices (variance removed at the designed 70k/arm sample size):
      conversion      <- pre_exp_spend     18.9%
      revenue/user    <- pre_exp_spend     39.0%
    pre_exp_spend beats pre_exp_sessions on BOTH (sessions give only 5.7% on
    conversion), because spend loads far more heavily on the frequency latent
    that drives conversion. Notebook 02 keeps the sessions covariate to
    contrast a strong and a weak one; the engine uses the better of the two.

    The two guardrails go uncovariated for opposite reasons. Average order
    value is measured on converters only, and CUPED is unsafe behind a
    post-treatment filter (see MetricSpec). The checkout error rate is
    independent of pre-experiment behavior by construction -- its correlation
    with pre_exp_sessions is 0.002 -- so a covariate would buy nothing.
    """
    return [
        MetricSpec(
            name="checkout conversion rate", kind="success", column="converted",
            test="proportion", covariate="pre_exp_spend", is_primary=True,
        ),
        MetricSpec(
            name="revenue per user", kind="success", column="revenue", test="mean",
            covariate="pre_exp_spend",
        ),
        MetricSpec(
            name="average order value", kind="guardrail", column="revenue",
            test="mean", direction="decrease",
            margin=config.AOV_NI_MARGIN_RELATIVE, margin_type="relative",
            filter_column="converted",
        ),
        MetricSpec(
            name="checkout error rate", kind="guardrail", column="checkout_error",
            test="proportion", direction="increase",
            margin=config.ERROR_NI_MARGIN_ABSOLUTE, margin_type="absolute",
        ),
    ]
