"""Phase 1 validation gates. Run from the repo root: python validate_phase1.py

G1a: at the recommended n for 80% power against the true +8% lift, the
     two-proportion z-test is significant in roughly 78-82% of 1,000 sims.
G1b: A/A check with true lift 0: significant in roughly 4-6% of 1,000 sims.
G1c: explicit sample-size formula matches statsmodels within 1%.
G1d: realized generator correlations land in the calibration targets.
"""

import numpy as np
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize, proportions_ztest

import config
from data.generate_data import generate_experiment_data
from src.power import required_sample_size_per_arm

N_SIMULATIONS = 1_000


def significant_fraction(true_lift: float, n_per_arm: int, base_seed: int) -> float:
    """Fraction of simulated experiments where the two-sided z-test rejects."""
    rejections = 0
    for i in range(N_SIMULATIONS):
        df = generate_experiment_data(
            n_users=2 * n_per_arm, seed=base_seed + i, conversion_lift=true_lift
        )
        counts = df.groupby("group")["converted"].agg(["sum", "size"])
        _, p_value = proportions_ztest(counts["sum"].values, counts["size"].values)
        rejections += p_value < config.ALPHA
    return rejections / N_SIMULATIONS


def report(gate: str, passed: bool, detail: str) -> bool:
    print(f"{gate}: {'PASS' if passed else 'FAIL'}  ({detail})")
    return passed


def main() -> None:
    p1 = config.CONTROL_CONVERSION_RATE
    n_per_arm = required_sample_size_per_arm(p1, config.TRUE_CONVERSION_LIFT)
    print(f"Recommended sample size: {n_per_arm:,} per arm "
          f"(baseline {p1:.1%}, MDE +{config.TRUE_CONVERSION_LIFT:.0%}, "
          f"alpha {config.ALPHA}, power {config.POWER_TARGET:.0%})\n")
    all_passed = True

    # G1a: empirical power at the recommended n should be ~80%.
    print(f"G1a: running {N_SIMULATIONS} simulations with the true lift...")
    power = significant_fraction(config.TRUE_CONVERSION_LIFT, n_per_arm, base_seed=10_000)
    all_passed &= report("G1a", 0.78 <= power <= 0.82, f"empirical power = {power:.3f}, expect 0.78-0.82")

    # G1b: with no true effect, rejections should be ~alpha.
    print(f"\nG1b: running {N_SIMULATIONS} A/A simulations (true lift = 0)...")
    fpr = significant_fraction(0.0, n_per_arm, base_seed=20_000)
    all_passed &= report("G1b", 0.04 <= fpr <= 0.06, f"false positive rate = {fpr:.3f}, expect 0.04-0.06")

    # G1c: explicit formula vs statsmodels (arcsine effect size, same alpha/power).
    effect_size = proportion_effectsize(p1 * (1 + config.MDE_RELATIVE), p1)
    statsmodels_n = NormalIndPower().solve_power(
        effect_size=effect_size, alpha=config.ALPHA, power=config.POWER_TARGET,
        ratio=1.0, alternative="two-sided",
    )
    ours = required_sample_size_per_arm(p1, config.MDE_RELATIVE)
    rel_diff = abs(ours - statsmodels_n) / statsmodels_n
    all_passed &= report(
        "\nG1c", rel_diff < 0.01,
        f"ours = {ours:,}, statsmodels = {statsmodels_n:,.0f}, diff = {rel_diff:.2%}"
    )

    # G1d: realized correlations from one large simulated experiment.
    df = generate_experiment_data(n_users=140_000, seed=config.RANDOM_SEED)
    control = df[df["group"] == "control"]
    rho_revenue = control["revenue"].corr(control["pre_exp_spend"])
    rho_conversion = control["converted"].corr(control["pre_exp_sessions"])
    all_passed &= report(
        "\nG1d", (0.55 <= rho_revenue <= 0.75) and (0.08 <= rho_conversion <= 0.30),
        f"rho(revenue, pre_exp_spend) = {rho_revenue:.3f} [0.55-0.75], "
        f"rho(converted, pre_exp_sessions) = {rho_conversion:.3f} [0.08-0.30]"
    )

    print(f"\n{'ALL GATES PASS' if all_passed else 'SOME GATES FAILED'}")


if __name__ == "__main__":
    main()
