"""Phase 2 validation gates. Run from the repo root: python validate_phase2.py

G2a: across-simulation variance of the CUPED effect estimator, relative to
     the raw estimator, matches the theoretical 1 - rho^2. Gated on all
     1,000 simulations: a variance ratio from only 200 sims has a Monte
     Carlo standard error of ~0.05, so a 200-sim gate false-alarms on
     roughly 1 run in 20; at 1,000 sims the 0.10 tolerance is ~4 SEs.
     The 200-sim value is still printed for reference.
     (The IN-SAMPLE metric variance ratio equals 1 - r^2 exactly by algebra
     whenever theta is estimated in-sample; the estimator-level check below
     is the non-tautological version, so that is what is gated.)
G2b: unbiasedness across 1,000 simulations: the mean CUPED conversion effect
     equals the true absolute effect, and the mean CUPED revenue effect
     shows no systematic shift vs the raw estimator.
G2c: A/A with CUPED: false positive rate still ~5% (4-6%, as in G1b).
"""

import numpy as np

import config
from data.generate_data import generate_experiment_data
from src.cuped import cuped_adjust
from src.power import required_sample_size_per_arm
from src.tests_stats import difference_in_means

N_SIMULATIONS = 1_000
G2A_SIMULATIONS = 200


def run_simulations(conversion_lift: float, aov_effect: float, base_seed: int) -> dict:
    """Simulate experiments; return per-sim effects, p-values and correlations."""
    n_per_arm = required_sample_size_per_arm(
        config.CONTROL_CONVERSION_RATE, config.TRUE_CONVERSION_LIFT
    )
    out = {key: [] for key in [
        "raw_conv", "cuped_conv", "raw_rev", "cuped_rev",
        "p_conv_cuped", "p_rev_cuped", "rho_conv", "rho_rev",
    ]}
    for i in range(N_SIMULATIONS):
        df = generate_experiment_data(
            n_users=2 * n_per_arm, seed=base_seed + i,
            conversion_lift=conversion_lift, aov_effect=aov_effect,
        )
        is_t = (df["group"] == "treatment").values

        for metric, covariate, prefix in [
            ("converted", "pre_exp_sessions", "conv"),
            ("revenue", "pre_exp_spend", "rev"),
        ]:
            y = df[metric].values.astype(float)
            x = df[covariate].values.astype(float)
            y_adj = cuped_adjust(y, x)

            raw = difference_in_means(y[is_t], y[~is_t])
            adj = difference_in_means(y_adj[is_t], y_adj[~is_t])
            out[f"raw_{prefix}"].append(raw.estimate)
            out[f"cuped_{prefix}"].append(adj.estimate)
            out[f"p_{prefix}_cuped"].append(adj.p_value)
            out[f"rho_{prefix}"].append(np.corrcoef(y, x)[0, 1])
    return {key: np.array(values) for key, values in out.items()}


def report(gate: str, passed: bool, detail: str) -> bool:
    print(f"{gate}: {'PASS' if passed else 'FAIL'}  ({detail})")
    return passed


def main() -> None:
    all_passed = True

    print(f"Running {N_SIMULATIONS} simulations with the true effects...")
    sims = run_simulations(
        config.TRUE_CONVERSION_LIFT, config.TRUE_AOV_EFFECT, base_seed=30_000
    )

    # G2a: estimator-level variance reduction vs theory, all 1,000 sims.
    print(f"\nG2a: estimator variance ratio vs 1 - rho^2 ({N_SIMULATIONS} sims)")
    g2a_passed = True
    for prefix, label in [("rev", "revenue"), ("conv", "conversion")]:
        raw = sims[f"raw_{prefix}"]
        cuped = sims[f"cuped_{prefix}"]
        ratio = np.var(cuped, ddof=1) / np.var(raw, ddof=1)
        ratio_200 = (np.var(cuped[:G2A_SIMULATIONS], ddof=1)
                     / np.var(raw[:G2A_SIMULATIONS], ddof=1))
        predicted = 1.0 - np.mean(sims[f"rho_{prefix}"] ** 2)
        ok = abs(ratio - predicted) <= 0.10
        g2a_passed &= ok
        print(f"  {label:>10}: observed ratio = {ratio:.3f}, "
              f"predicted 1 - rho^2 = {predicted:.3f}, diff = {abs(ratio - predicted):.3f} "
              f"(200-sim ratio would be {ratio_200:.3f})")
    all_passed &= report("G2a", g2a_passed, "both metrics within 0.10 of theory")

    # G2b: unbiasedness across all 1,000 sims.
    true_conv_effect = config.CONTROL_CONVERSION_RATE * config.TRUE_CONVERSION_LIFT
    conv_bias = np.mean(sims["cuped_conv"]) - true_conv_effect
    conv_tol = 4.0 * np.std(sims["cuped_conv"], ddof=1) / np.sqrt(N_SIMULATIONS)

    rev_gap = np.mean(sims["cuped_rev"] - sims["raw_rev"])
    rev_tol = 4.0 * np.std(sims["cuped_rev"] - sims["raw_rev"], ddof=1) / np.sqrt(N_SIMULATIONS)

    all_passed &= report(
        "\nG2b", abs(conv_bias) <= conv_tol and abs(rev_gap) <= rev_tol,
        f"conversion bias = {conv_bias:+.2e} (tol {conv_tol:.2e}), "
        f"revenue CUPED-vs-raw gap = {rev_gap:+.2e} (tol {rev_tol:.2e})"
    )

    # G2c: A/A false positive rate with CUPED (all true effects zeroed).
    print(f"\nG2c: running {N_SIMULATIONS} A/A simulations (all true effects = 0)...")
    aa = run_simulations(conversion_lift=0.0, aov_effect=0.0, base_seed=40_000)
    fpr_conv = np.mean(aa["p_conv_cuped"] < config.ALPHA)
    fpr_rev = np.mean(aa["p_rev_cuped"] < config.ALPHA)
    all_passed &= report(
        "G2c", 0.04 <= fpr_conv <= 0.06,
        f"CUPED conversion FPR = {fpr_conv:.3f}, expect 0.04-0.06 "
        f"(revenue FPR = {fpr_rev:.3f}, informational)"
    )

    print(f"\n{'ALL GATES PASS' if all_passed else 'SOME GATES FAILED'}")


if __name__ == "__main__":
    main()
