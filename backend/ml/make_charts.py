"""Render the PR charts for the lead model into docs/pr-assets/.

Usage (from backend/):  uv run --group ml python -m ml.make_charts
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from ml.compare_splits import run_scenario  # noqa: E402
from ml.train_model import HERE, load, train  # noqa: E402

OUT = HERE.parent.parent / "docs" / "pr-assets"
# Reference palette (dataviz skill), validated: blue/orange categorical, blue/red diverging.
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e4e3df"
BLUE, ORANGE, RED, NEUTRAL = "#2a78d6", "#eb6834", "#e34948", "#b5b3ad"
# One-hot names of fields with no true effect in the generator (browser_language does have one).
NO_EFFECT = (
    "cat__browser_chrome",
    "cat__browser_edge",
    "cat__browser_firefox",
    "cat__browser_safari",
    "cat__browser_samsung",
    "cat__browser_other",
    "cat__os_",
)

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK2,
        "axes.titlecolor": INK,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK2,
        "ytick.labelcolor": INK2,
        "font.size": 10.5,
        "legend.frameon": False,
        "legend.labelcolor": INK2,
    }
)


def _save(fig, name: str) -> None:
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / name)


def split_chart(stable: list[dict], drift: list[dict]) -> None:
    """PR-AUC: what each split method promised (bar) vs what it delivered on the future (line)."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, (title, runs) in zip(
        axes, [("Stable market", stable), ("Market changes over time", drift)], strict=True
    ):
        for i, (method, color) in enumerate([("random", BLUE), ("time", ORANGE)]):
            est = np.mean([r[method]["cv_mean"]["average_precision"] for r in runs])
            actual = np.mean([r[method]["future"]["average_precision"] for r in runs])
            ax.bar(i, est, width=0.55, color=color, edgecolor=SURFACE, linewidth=2)
            ax.hlines(actual, i - 0.36, i + 0.36, color=INK, linewidth=2)
            ax.text(i, max(est, actual) + 0.012, f"{est:.3f}", ha="center", color=INK, fontsize=10)
            ax.text(i, actual - 0.03, f"{actual:.3f}", ha="center", color="white", fontsize=9.5)
        ax.set_xticks([0, 1], ["Random split", "Time-based split"])
        ax.set_title(title, loc="left")
        ax.set_ylim(0, 0.55)
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_xlim(-0.6, 1.6)
    axes[0].set_ylabel("PR-AUC (mean of 10 runs)")
    axes[1].legend(
        [plt.Rectangle((0, 0), 1, 1, color=MUTED), plt.Line2D([], [], color=INK, linewidth=2)],
        ["Estimate from the split (bar)", "Actual on an unseen future year"],
        loc="upper right",
    )
    fig.tight_layout()
    _save(fig, "ml-split-comparison.png")


def calibration_chart(r: dict) -> None:
    cal = r["calibration"]
    x = np.arange(len(cal))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    pred = [c["predicted"] * 100 for c in cal]
    act = [c["actual"] * 100 for c in cal]
    ax.bar(x - 0.2, pred, 0.4, color=BLUE, edgecolor=SURFACE, linewidth=2, label="Predicted")
    ax.bar(x + 0.2, act, 0.4, color=ORANGE, edgecolor=SURFACE, linewidth=2, label="Actual")
    ax.axhline(r["base_rate_test"] * 100, color=MUTED, linestyle="--", linewidth=1.2)
    ax.text(-0.45, r["base_rate_test"] * 100 + 1, "average lead", color=INK2, fontsize=9)
    for xi, a in zip(x, act, strict=True):
        ax.text(xi + 0.2, a + 0.8, f"{a:.0f}%", ha="center", color=INK, fontsize=9.5)
    ax.set_xticks(x, ["Lowest 20%", "2", "3", "4", "Highest 20%"])
    ax.set_xlabel("Leads grouped by model score (test period)")
    ax.set_ylabel("Purchase rate (%)")
    ax.set_title("Calibration: predicted vs actual purchase rate", loc="left")
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left")
    _save(fig, "ml-calibration.png")


def coefficient_chart(r: dict, top: int = 15) -> None:
    coefs = r["coefficients"].head(top)[::-1]
    labels = [n.split("__", 1)[1].replace("_", " ") for n in coefs.index]
    labels = [
        lbl.replace("event type בר או בת מצווה", "event type: bar/bat mitzvah")
        .replace("event type אחר", "event type: other")
        .replace("event type חגיגה פרטית", "event type: private party")
        for lbl in labels
    ]
    noise = [n.startswith(NO_EFFECT) for n in coefs.index]
    colors = [NEUTRAL if z else (BLUE if v > 0 else RED) for v, z in zip(coefs, noise, strict=True)]
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    bars = ax.barh(labels, coefs.values, color=colors, edgecolor=SURFACE, linewidth=2, height=0.7)
    for b, z in zip(bars, noise, strict=True):
        if z:
            b.set_hatch("///")
            b.set_edgecolor(INK2)
            b.set_linewidth(0.6)
    ax.axvline(0, color=INK2, linewidth=1)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("Effect on purchase log-odds (per 1 SD, or vs. other categories)")
    ax.set_title(f"Top {top} features of the final model", loc="left")
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=BLUE),
        plt.Rectangle((0, 0), 1, 1, color=RED),
        plt.Rectangle((0, 0), 1, 1, facecolor=NEUTRAL, hatch="///", edgecolor=INK2),
    ]
    ax.legend(
        handles,
        ["Raises purchase chance", "Lowers purchase chance", "Noise (no true effect)"],
        loc="upper left",
    )
    _save(fig, "ml-coefficients.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    r = train(load(HERE / "data" / "leads_synthetic.csv"))
    calibration_chart(r)
    coefficient_chart(r)
    split_chart(run_scenario(0.0, 10, 5000), run_scenario(1.0, 10, 5000))


if __name__ == "__main__":
    main()
