"""Risk-aware ship/no-ship decision engine.

Combines one-sided superiority tests on success metrics (BH-corrected as a
family) with non-inferiority tests on guardrail metrics (uncorrected, with
Type II risk reported as power) into a single verdict:

  SHIP          primary metric significantly improved (after BH) AND every
                guardrail established non-inferiority with adequate power.
  DO NOT SHIP   primary failed, or any guardrail shows harm BEYOND its
                margin (statistically established). Significant harm that
                stays within the margin is an accepted cost, not a blocker.
  INVESTIGATE   otherwise: some guardrail is inconclusive (usually because
                the experiment is underpowered for that guardrail).

Modeled on the Microsoft ExP metric hierarchy and Spotify's guardrail
decision framework.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config
from src.tests_stats import (
    NonInferiorityResult,
    SuperiorityResult,
    benjamini_hochberg,
    non_inferiority_test,
    superiority_test,
)


@dataclass
class MetricSpec:
    """Declares how one metric is measured and judged.

    kind:       "success" (must improve) or "guardrail" (must not degrade)
    column:     DataFrame column holding the per-user value
    test:       "proportion" (binary column) or "mean" (continuous column);
                both use the same large-sample z machinery, the label is
                reported so the reader knows what the metric is
    direction:  for success metrics, the improvement direction (always
                "increase" here); for guardrails, the direction of HARM
    margin:     guardrails only; the non-inferiority margin, expressed per
                margin_type
    margin_type:"absolute" (e.g. +0.5pp on an error rate) or "relative"
                (e.g. 2% of the control mean)
    converted_only: restrict to converted users (for average order value)
    is_primary: exactly one success metric drives the SHIP verdict
    """

    name: str
    kind: str
    column: str
    test: str
    direction: str = "increase"
    margin: float | None = None
    margin_type: str = "absolute"
    converted_only: bool = False
    is_primary: bool = False


@dataclass
class MetricResult:
    spec: MetricSpec
    result: SuperiorityResult | NonInferiorityResult
    margin_absolute: float | None = None
    bh_significant: bool | None = None  # success metrics, after BH
    status: str = ""                    # "pass" / "fail" / "harm" / "inconclusive"
    note: str = ""


@dataclass
class DecisionReport:
    verdict: str
    reasoning: list[str]
    metrics: list[MetricResult] = field(default_factory=list)
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
            lines.append(f"- status: {m.status.upper()}{'  (' + m.note + ')' if m.note else ''}")
            lines.append("")
        return "\n".join(lines)


def _metric_arrays(df: pd.DataFrame, spec: MetricSpec) -> tuple[np.ndarray, np.ndarray]:
    """Per-arm value arrays for a metric, applying the converters-only filter."""
    rows = df[df["converted"] == 1] if spec.converted_only else df
    values = rows[spec.column].values.astype(float)
    is_treatment = (rows["group"] == "treatment").values
    return values[is_treatment], values[~is_treatment]


def evaluate_experiment(
    df: pd.DataFrame,
    metric_specs: list[MetricSpec],
    alpha: float = config.ALPHA,
    power_floor: float = config.POWER_TARGET,
) -> DecisionReport:
    """Run every metric's test and combine them into a verdict.

    Success metrics get one-sided superiority tests, BH-corrected as one
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

    results: list[MetricResult] = []

    success_results = []
    for spec in success:
        y_t, y_c = _metric_arrays(df, spec)
        success_results.append(superiority_test(y_t, y_c, alpha))
    bh_mask = benjamini_hochberg([r.p_value for r in success_results], q=alpha)

    primary_ok = False
    for spec, r, significant in zip(success, success_results, bh_mask):
        status = "pass" if significant else "fail"
        if spec.is_primary:
            primary_ok = bool(significant)
        results.append(MetricResult(
            spec=spec, result=r, bh_significant=bool(significant), status=status,
        ))

    any_harm, any_inconclusive = False, False
    for spec in guardrails:
        y_t, y_c = _metric_arrays(df, spec)
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
            spec=spec, result=r, margin_absolute=margin_abs, status=status, note=note,
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
        verdict=verdict, reasoning=reasoning, metrics=results,
        alpha=alpha, power_floor=power_floor,
    )


def default_metric_specs() -> list[MetricSpec]:
    """The checkout experiment's metric hierarchy, margins from config."""
    return [
        MetricSpec(
            name="checkout conversion rate", kind="success", column="converted",
            test="proportion", is_primary=True,
        ),
        MetricSpec(
            name="revenue per user", kind="success", column="revenue", test="mean",
        ),
        MetricSpec(
            name="average order value", kind="guardrail", column="revenue",
            test="mean", direction="decrease",
            margin=config.AOV_NI_MARGIN_RELATIVE, margin_type="relative",
            converted_only=True,
        ),
        MetricSpec(
            name="checkout error rate", kind="guardrail", column="checkout_error",
            test="proportion", direction="increase",
            margin=config.ERROR_NI_MARGIN_ABSOLUTE, margin_type="absolute",
        ),
    ]
