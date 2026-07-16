"""Shared plotting utilities.

Styling choices: a single-hue blue ramp (light to dark) for ordered series
like increasing MDEs, recessive gray grid and axes, and direct labels plus a
legend so no series is identified by color alone.
"""

import matplotlib.pyplot as plt
import numpy as np

import config
from src.power import achieved_power

# Ordinal blue ramp, light to dark, for series ordered by magnitude.
BLUE_RAMP = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
GRID_COLOR = "#e1e0d9"
AXIS_COLOR = "#898781"
TEXT_COLOR = "#0b0b0b"
SURFACE_COLOR = "#fcfcfb"


def plot_power_curves(
    baseline_rate: float,
    mde_relative_list: list[float],
    n_max_per_arm: int,
    alpha: float = config.ALPHA,
    power_target: float = config.POWER_TARGET,
):
    """Plot statistical power vs per-arm sample size for several relative MDEs.

    Returns the matplotlib Figure. Darker lines are larger (easier to detect)
    effects. A horizontal line marks the target power.
    """
    n_grid = np.linspace(1_000, n_max_per_arm, 200).astype(int)

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor(SURFACE_COLOR)
    ax.set_facecolor(SURFACE_COLOR)

    # Largest MDE gets the darkest color: reverse-index into the ramp.
    mdes = sorted(mde_relative_list)
    for i, mde in enumerate(mdes):
        color = BLUE_RAMP[min(i, len(BLUE_RAMP) - 1)]
        powers = [achieved_power(n, baseline_rate, mde, alpha) for n in n_grid]
        ax.plot(n_grid, powers, color=color, linewidth=2, label=f"MDE +{mde:.0%}")
        # Direct label at the line's right end.
        ax.annotate(
            f" +{mde:.0%}",
            xy=(n_grid[-1], powers[-1]),
            color=color,
            fontsize=9,
            va="center",
        )

    ax.axhline(power_target, color=AXIS_COLOR, linewidth=1, linestyle="--")
    ax.annotate(
        f"target power {power_target:.0%}",
        xy=(n_grid[0], power_target),
        xytext=(0, 4),
        textcoords="offset points",
        color=AXIS_COLOR,
        fontsize=9,
    )

    ax.set_xlabel("Users per arm", color=TEXT_COLOR)
    ax.set_ylabel("Power", color=TEXT_COLOR)
    ax.set_title(
        f"Power vs sample size (baseline conversion {baseline_rate:.1%}, "
        f"alpha {alpha})",
        color=TEXT_COLOR,
    )
    ax.set_ylim(0, 1.02)
    ax.grid(color=GRID_COLOR, linewidth=0.8)
    ax.tick_params(colors=AXIS_COLOR)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    return fig


RAW_COLOR = "#86b6ef"    # light blue: baseline method
CUPED_COLOR = "#1c5cab"  # dark blue: improved method


def _style_axis(ax, title):
    ax.set_facecolor(SURFACE_COLOR)
    ax.set_title(title, color=TEXT_COLOR, fontsize=11)
    ax.grid(color=GRID_COLOR, linewidth=0.8, axis="x")
    ax.tick_params(colors=AXIS_COLOR)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)


def plot_ci_comparison(results: dict):
    """Side-by-side raw vs CUPED confidence intervals, one panel per metric.

    results maps a panel title (e.g. "Conversion (pp)") to a dict with keys
    "raw" and "cuped", each a MeanDifferenceResult. Separate panels because
    the metrics live on different scales (never a dual axis).
    """
    fig, axes = plt.subplots(1, len(results), figsize=(5 * len(results), 3.2))
    fig.patch.set_facecolor(SURFACE_COLOR)

    for ax, (title, pair) in zip(np.atleast_1d(axes), results.items()):
        for y_pos, (label, color) in enumerate([("raw", RAW_COLOR), ("cuped", CUPED_COLOR)]):
            r = pair[label]
            ax.errorbar(
                r.estimate, y_pos,
                xerr=[[r.estimate - r.ci_low], [r.ci_high - r.estimate]],
                fmt="o", color=color, capsize=4, markersize=8, linewidth=2,
            )
        ax.axvline(0, color=AXIS_COLOR, linewidth=1, linestyle="--")
        ax.set_yticks([0, 1], ["raw", "CUPED"])
        ax.set_ylim(-0.6, 1.6)
        _style_axis(ax, title)
        ax.tick_params(axis="y", colors=TEXT_COLOR)
    fig.tight_layout()
    return fig


def plot_duration_comparison(days: dict):
    """Horizontal bars of experiment duration (days) for raw vs CUPED.

    days maps a metric label to {"raw": days, "cuped": days}: the days
    needed to reach the same precision the raw method reaches.
    """
    labels, values, colors = [], [], []
    for metric, pair in days.items():
        for method, color in [("raw", RAW_COLOR), ("cuped", CUPED_COLOR)]:
            labels.append(f"{metric}, {method}")
            values.append(pair[method])
            colors.append(color)

    fig, ax = plt.subplots(figsize=(8, 0.7 * len(labels) + 1))
    fig.patch.set_facecolor(SURFACE_COLOR)
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, color=colors, height=0.62)
    for yi, v in zip(y, values):
        ax.annotate(f" {v:.1f}d", xy=(v, yi), va="center", color=TEXT_COLOR, fontsize=9)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Days to reach the same precision", color=TEXT_COLOR)
    _style_axis(ax, "Experiment duration by method")
    ax.tick_params(axis="y", colors=TEXT_COLOR)
    fig.tight_layout()
    return fig
