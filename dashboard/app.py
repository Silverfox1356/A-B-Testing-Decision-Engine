"""Streamlit dashboard for the A/B testing decision engine.

Run from the repo root:  streamlit run dashboard/app.py
Dark theme (.streamlit/config.toml); all chart text and ticks are white.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

import config
from data.generate_data import generate_experiment_data
from src.cuped import cuped_adjust
from src.decision_engine import default_metric_specs, evaluate_experiment
from src.power import achieved_power, required_sample_size_per_arm
from src.tests_stats import difference_in_means

WHITE = "#ffffff"
DARK_BG = "#0e1117"
RAW_COLOR = "#86b6ef"
CUPED_COLOR = "#3987e5"

plt.rcParams.update({
    "figure.facecolor": DARK_BG, "axes.facecolor": DARK_BG,
    "text.color": WHITE, "axes.labelcolor": WHITE, "axes.titlecolor": WHITE,
    "xtick.color": WHITE, "ytick.color": WHITE,
    "axes.edgecolor": "#44464e", "grid.color": "#2c2e36",
})

st.set_page_config(page_title="A/B Testing Decision Engine", layout="wide")
st.title("A/B Testing Decision Engine")
st.caption("Checkout-flow experiment: power design, CUPED variance reduction, "
           "and a risk-aware ship/no-ship decision.")

tab_design, tab_cuped, tab_decision = st.tabs(
    ["Design", "Variance Reduction", "Decision"]
)


# ---------------------------------------------------------------- Tab 1
with tab_design:
    st.subheader("Power calculator: two-proportion z-test")
    col1, col2 = st.columns([1, 2])
    with col1:
        baseline = st.slider("Baseline conversion rate (%)", 0.5, 10.0, 3.5, 0.1) / 100
        mde = st.slider("MDE, relative lift (%)", 2, 20, 8, 1) / 100
        alpha = st.slider("Alpha (two-sided)", 0.01, 0.10, 0.05, 0.01)
        power = st.slider("Target power", 0.70, 0.95, 0.80, 0.05)

        n = required_sample_size_per_arm(baseline, mde, alpha, power)
        days = 2 * n / config.USERS_PER_DAY
        st.metric("Required users per arm", f"{n:,}")
        st.metric("Total users", f"{2 * n:,}")
        st.metric(f"Duration at {config.USERS_PER_DAY:,} users/day", f"{days:.0f} days")

    with col2:
        n_grid = np.linspace(1_000, max(2 * n, 20_000), 150).astype(int)
        fig, ax = plt.subplots(figsize=(7, 4))
        for i, m in enumerate(sorted({mde, 0.5 * mde, 1.5 * mde})):
            color = ["#86b6ef", "#3987e5", "#1c5cab"][i]
            ax.plot(n_grid, [achieved_power(x, baseline, m, alpha) for x in n_grid],
                    color=color, linewidth=2, label=f"MDE +{m:.1%}")
        ax.axhline(power, color=WHITE, linewidth=1, linestyle="--", alpha=0.6)
        ax.axvline(n, color=WHITE, linewidth=1, linestyle=":", alpha=0.6)
        ax.set_xlabel("Users per arm")
        ax.set_ylabel("Power")
        ax.set_ylim(0, 1.02)
        ax.grid(linewidth=0.6)
        ax.legend(frameon=False, labelcolor=WHITE)
        st.pyplot(fig)


# ---------------------------------------------------------------- Tab 2
@st.cache_data
def cuped_results():
    """Raw vs CUPED estimates on the default experiment (notebook 01's)."""
    n = required_sample_size_per_arm(config.CONTROL_CONVERSION_RATE, config.MDE_RELATIVE)
    df = generate_experiment_data(n_users=2 * n, seed=config.RANDOM_SEED)
    is_t = (df["group"] == "treatment").values
    out = {}
    for label, metric, covariate in [
        ("conversion", "converted", "pre_exp_sessions"),
        ("revenue per user", "revenue", "pre_exp_spend"),
    ]:
        y = df[metric].values.astype(float)
        x = df[covariate].values.astype(float)
        y_adj = cuped_adjust(y, x)
        rho = float(np.corrcoef(y, x)[0, 1])
        out[label] = {
            "raw": difference_in_means(y[is_t], y[~is_t]),
            "cuped": difference_in_means(y_adj[is_t], y_adj[~is_t]),
            "rho": rho,
        }
    return out, n


with tab_cuped:
    st.subheader("CUPED: pre-experiment data as a variance dampener")
    results, n_default = cuped_results()
    days_raw = 2 * n_default / config.USERS_PER_DAY

    cols = st.columns(2)
    for col, (label, r) in zip(cols, results.items()):
        with col:
            reduction = r["rho"] ** 2
            st.markdown(f"**{label}**  (rho = {r['rho']:.3f})")
            st.metric("Variance reduction", f"{reduction:.1%}")
            st.metric("Runtime for equal precision",
                      f"{days_raw * (1 - reduction):.1f} days",
                      delta=f"-{days_raw * reduction:.1f} vs {days_raw:.0f} raw",
                      delta_color="inverse")

            fig, ax = plt.subplots(figsize=(5.5, 2.4))
            for y_pos, (name, color) in enumerate([("raw", RAW_COLOR), ("cuped", CUPED_COLOR)]):
                e = r[name]
                ax.errorbar(e.estimate, y_pos,
                            xerr=[[e.estimate - e.ci_low], [e.ci_high - e.estimate]],
                            fmt="o", color=color, capsize=4, markersize=7, linewidth=2)
            ax.axvline(0, color=WHITE, linewidth=1, linestyle="--", alpha=0.5)
            ax.set_yticks([0, 1], ["raw", "CUPED"])
            ax.set_ylim(-0.6, 1.6)
            ax.set_title(f"{label}: effect and 95% CI", fontsize=10)
            ax.grid(axis="x", linewidth=0.6)
            st.pyplot(fig)

    st.caption("Same experiment, same users: CUPED subtracts the part of each "
               "metric predictable from pre-experiment behavior. Continuous "
               "revenue benefits dramatically; rare binary conversion only "
               "modestly (its correlation with any covariate is capped).")


# ---------------------------------------------------------------- Tab 3
SCENARIOS = {
    "Experiment as designed (70k/arm)": dict(
        n_users=2 * 70_229, seed=204),
    "SHIP: no true AOV harm, guardrail-powered n (900k/arm)": dict(
        n_users=1_800_000, seed=202, aov_effect=0.0),
    "DO NOT SHIP: -5% true AOV harm (900k/arm)": dict(
        n_users=1_800_000, seed=203, aov_effect=-0.05),
    "INVALID: broken assignment, 49/51 split (70k/arm)": dict(
        n_users=2 * 70_229, seed=204, treatment_share=0.49),
}
BANNER = {"SHIP": st.success, "DO NOT SHIP": st.error,
          "INVESTIGATE": st.warning, "INVALID": st.error}


@st.cache_data
def run_scenario(name: str):
    df = generate_experiment_data(**SCENARIOS[name])
    return evaluate_experiment(df, default_metric_specs())


with tab_decision:
    st.subheader("Ship / no-ship decision")
    choice = st.radio("Scenario", list(SCENARIOS), label_visibility="collapsed")
    with st.spinner("Simulating experiment and running every test..."):
        report = run_scenario(choice)

    BANNER[report.verdict](f"## {report.verdict}")
    for reason in report.reasoning:
        st.markdown(f"- {reason}")
    st.markdown(f"alpha = {report.alpha}, guardrail power floor = {report.power_floor:.0%}")

    if report.srm is not None:
        srm = report.srm
        label = "MISMATCH" if srm.mismatch else "ok"
        st.caption(
            f"sample ratio check ({label}): treatment {srm.n_treatment:,} / "
            f"control {srm.n_control:,} = {srm.observed_share:.4%} vs "
            f"{srm.expected_share:.2%} intended, chi-square p = {srm.p_value:.3g}"
        )
    if not report.metrics:
        st.info("No metrics were evaluated: the sample ratio check failed, so the "
                "arms are not comparable and any metric read from this experiment "
                "would be confounded.")

    for m in report.metrics:
        r = m.result
        icon = {"pass": "PASS", "fail": "FAIL", "harm": "HARM",
                "inconclusive": "INCONCLUSIVE"}[m.status]
        with st.container(border=True):
            left, mid, right = st.columns([2, 2, 1])
            with left:
                st.markdown(f"**{m.spec.name}**")
                st.caption(f"{m.spec.kind} - {m.spec.test} test")
            with mid:
                if m.spec.kind == "success":
                    st.markdown(f"effect **{r.estimate:+.5f}** "
                                f"(one-sided lower bound {r.ci_low:+.5f})")
                    st.caption(f"one-sided p = {r.p_value:.4f}, "
                               f"BH-significant: {'yes' if m.bh_significant else 'no'}")
                else:
                    sign = "+" if m.spec.direction == "increase" else "-"
                    st.markdown(f"effect **{r.estimate:+.5f}** vs margin "
                                f"{sign}{m.margin_absolute:.5f} "
                                f"(worst-case bound {r.ci_bound:+.5f})")
                    st.caption(f"non-inferiority p = {r.p_value:.4f}, "
                               f"power if harmless = {r.power:.0%}")
                if m.variance_reduction is not None:
                    st.caption(f"CUPED on '{m.spec.covariate}': "
                               f"{m.variance_reduction:.1%} of variance removed")
            with right:
                st.markdown(f"### {icon}")
                if m.note:
                    st.caption(m.note)
