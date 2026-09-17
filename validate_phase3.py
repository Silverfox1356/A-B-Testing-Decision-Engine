"""Phase 3 validation gates. Run from the repo root: python validate_phase3.py

G3a: non-inferiority sanity at a sample size where analytic NI power is 80%:
     with TRUE degradation exactly at the margin the test passes ~alpha
     (5%) of the time; with zero true degradation it passes ~power (80%).
G3b: Benjamini-Hochberg on 10 metrics (5 true nulls): empirical FDR is
     controlled at q and sits near the theoretical q * m0/m = 0.025.
G3c: the SHIP / DO NOT SHIP / INVESTIGATE scenarios produce their verdicts.
     Scenario seeds are fixed representative draws; the underlying rates
     (power, alpha) are what G3a and G1a validate.
G3d: the SRM gate has the right size and power: on a genuinely fair coin it
     fires at about SRM_ALPHA (so healthy experiments are essentially never
     thrown out), and on a 49/51 assignment bug it fires nearly always.
"""

import math

import numpy as np
from scipy.stats import norm

import config
from data.generate_data import generate_experiment_data
from src.decision_engine import default_metric_specs, evaluate_experiment
from src.power import required_sample_size_per_arm
from src.tests_stats import benjamini_hochberg, non_inferiority_test, sample_ratio_mismatch

N_SIMULATIONS = 2_000
# SHIP/DO-NOT-SHIP scenarios need the AOV guardrail adequately powered,
# which takes far more users than the primary metric does (heavy-tailed
# order values on a 3.5% converter subpopulation): ~900k/arm gives ~91%
# a priori NI power at the 2% margin.
SHIP_SCENARIO_N_PER_ARM = 900_000


def report(gate: str, passed: bool, detail: str) -> bool:
    print(f"{gate}: {'PASS' if passed else 'FAIL'}  ({detail})")
    return passed


def gate_g3a() -> bool:
    """Error-rate style guardrail: pass rate at the margin and at zero harm."""
    p_base = config.CONTROL_ERROR_RATE
    margin = config.ERROR_NI_MARGIN_ABSOLUTE
    z_alpha, z_beta = norm.ppf(1 - config.ALPHA), norm.ppf(config.POWER_TARGET)
    # n per arm at which analytic NI power is exactly the 80% target.
    n = math.ceil(2 * p_base * (1 - p_base) * ((z_alpha + z_beta) / margin) ** 2)
    print(f"G3a: n = {n:,}/arm (analytic NI power {config.POWER_TARGET:.0%}), "
          f"{N_SIMULATIONS} sims per case")

    rng = np.random.default_rng(60_000)
    passes_at_margin, passes_at_zero = 0, 0
    for _ in range(N_SIMULATIONS):
        control = rng.binomial(1, p_base, n).astype(float)
        at_margin = rng.binomial(1, p_base + margin, n).astype(float)
        harmless = rng.binomial(1, p_base, n).astype(float)
        passes_at_margin += non_inferiority_test(at_margin, control, margin, "increase").ni_passed
        passes_at_zero += non_inferiority_test(harmless, control, margin, "increase").ni_passed

    rate_margin = passes_at_margin / N_SIMULATIONS
    rate_zero = passes_at_zero / N_SIMULATIONS
    ok = (0.035 <= rate_margin <= 0.065) and abs(rate_zero - config.POWER_TARGET) <= 0.03
    return report(
        "G3a", ok,
        f"pass rate at margin = {rate_margin:.3f} (expect ~0.05), "
        f"at zero harm = {rate_zero:.3f} (expect ~{config.POWER_TARGET:.2f})"
    )


def gate_g3b() -> bool:
    """FDR of BH across 5,000 sims of 10 one-sided z-tests, 5 true nulls."""
    n_sims, n_null, n_alt, shift = 5_000, 5, 5, 3.0
    rng = np.random.default_rng(61_000)
    is_null = np.array([True] * n_null + [False] * n_alt)

    fdp = np.empty(n_sims)
    for i in range(n_sims):
        z = rng.standard_normal(10) + np.where(is_null, 0.0, shift)
        p = 1.0 - norm.cdf(z)
        rejected = benjamini_hochberg(p, q=config.ALPHA)
        false_discoveries = np.sum(rejected & is_null)
        fdp[i] = false_discoveries / max(np.sum(rejected), 1)

    fdr = fdp.mean()
    se = fdp.std(ddof=1) / np.sqrt(n_sims)
    theoretical = config.ALPHA * n_null / (n_null + n_alt)
    ok = fdr <= config.ALPHA and abs(fdr - theoretical) <= 3 * se
    return report(
        "G3b", ok,
        f"empirical FDR = {fdr:.4f} (theory q*m0/m = {theoretical:.4f}, "
        f"MC SE = {se:.4f}, must stay <= q = {config.ALPHA})"
    )


def gate_g3c() -> bool:
    """The three canonical scenarios produce their intended verdicts."""
    n_default = required_sample_size_per_arm(
        config.CONTROL_CONVERSION_RATE, config.MDE_RELATIVE
    )
    scenarios = [
        ("SHIP", dict(n_users=2 * SHIP_SCENARIO_N_PER_ARM, seed=202, aov_effect=0.0)),
        ("DO NOT SHIP", dict(n_users=2 * SHIP_SCENARIO_N_PER_ARM, seed=203, aov_effect=-0.05)),
        ("INVESTIGATE", dict(n_users=2 * n_default, seed=204)),
    ]
    ok = True
    for expected, kwargs in scenarios:
        df = generate_experiment_data(**kwargs)
        verdict = evaluate_experiment(df, default_metric_specs()).verdict
        ok &= verdict == expected
        print(f"  scenario expecting {expected:12s} -> got {verdict}")
    return report("G3c", ok, "all three verdicts as expected")


def gate_g3d() -> bool:
    """SRM gate: false alarm rate on fair assignment, detection on a broken one."""
    n_users = 2 * required_sample_size_per_arm(
        config.CONTROL_CONVERSION_RATE, config.MDE_RELATIVE
    )
    n_sims = 20_000
    rng = np.random.default_rng(62_000)

    # Size: a genuinely fair coin. Binomial draws, not the generator's exact
    # split, because an exactly balanced split can never trigger the gate.
    fair = rng.binomial(n_users, 0.5, n_sims)
    false_alarms = sum(
        sample_ratio_mismatch(int(n_t), n_users - int(n_t)).mismatch for n_t in fair
    )
    false_alarm_rate = false_alarms / n_sims

    # Power: a 49/51 assignment bug at this sample size.
    broken = rng.binomial(n_users, 0.49, 1_000)
    detected = sum(
        sample_ratio_mismatch(int(n_t), n_users - int(n_t)).mismatch for n_t in broken
    )
    detection_rate = detected / 1_000

    # The false alarm rate is a binomial proportion around SRM_ALPHA; at
    # 20,000 sims its standard error is ~0.00016, so allow 4 SEs of slack.
    ok = false_alarm_rate <= config.SRM_ALPHA + 0.0007 and detection_rate >= 0.99
    return report(
        "G3d", ok,
        f"false alarm rate on fair assignment = {false_alarm_rate:.5f} "
        f"(expect ~{config.SRM_ALPHA}), detection of a 49/51 bug = {detection_rate:.3f} "
        f"(expect ~1.000) at {n_users:,} users"
    )


def main() -> None:
    all_passed = gate_g3a()
    print()
    all_passed &= gate_g3b()
    print()
    all_passed &= gate_g3c()
    print()
    all_passed &= gate_g3d()
    print(f"\n{'ALL GATES PASS' if all_passed else 'SOME GATES FAILED'}")


if __name__ == "__main__":
    main()
