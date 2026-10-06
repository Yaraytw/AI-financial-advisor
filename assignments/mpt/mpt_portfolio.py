"""
Robo-Advisor Assignment 2 — Part III
Portfolio opportunity set, Minimum Variance Portfolio (MVP), efficient frontier.

Reads output/return_matrix.csv written by mpt_analysis.py (daily returns, one
column per asset) and:
  1. Simulates random long-only portfolios (weights >= 0, sum to 1) to draw the
     opportunity set in (volatility, expected return) space.
  2. Finds the MVP two ways: the closed-form solution (shorting allowed) and the
     long-only numerical solution.
  3. Traces the long-only efficient frontier.

Expected return is the arithmetic mean daily return x 252 so that portfolio
return is linear in the weights, E(Rp) = sum(w_i * E(R_i)); risk is
sqrt(w' Sigma w) with Sigma the daily covariance matrix x 252.

Usage:
  python mpt_portfolio.py
  python mpt_portfolio.py --n 20000 --seed 7 --rf 0.015
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize

TRADING_DAYS_PER_YEAR = 252

INK = "#0b0b0b"
INK_MUTED = "#52514e"
SURFACE = "#fcfcfb"
GRID = "#e3e2dd"
BLUE = "#2a78d6"
ORANGE = "#eb6834"


def portfolio_stats(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float):
    ret = weights @ mu
    vol = np.sqrt(np.einsum("...i,ij,...j->...", weights, cov, weights))
    return ret, vol, (ret - rf) / vol


def simulate_portfolios(mu: np.ndarray, cov: np.ndarray, n: int, seed: int, rf: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    weights = rng.dirichlet(np.ones(len(mu)), size=n)
    ret, vol, sharpe = portfolio_stats(weights, mu, cov, rf)
    return pd.DataFrame({"Return": ret, "Volatility": vol, "Sharpe": sharpe}), weights


def mvp_closed_form(cov: np.ndarray) -> np.ndarray:
    """w = Sigma^-1 1 / (1' Sigma^-1 1); negative entries mean short positions."""
    ones = np.ones(len(cov))
    inv_ones = np.linalg.solve(cov, ones)
    return inv_ones / (ones @ inv_ones)


def min_variance_long_only(mu: np.ndarray, cov: np.ndarray, target: float | None = None) -> np.ndarray:
    n = len(mu)
    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    if target is not None:
        constraints.append({"type": "eq", "fun": lambda w, t=target: w @ mu - t})
    result = minimize(
        lambda w: w @ cov @ w,
        x0=np.full(n, 1 / n),
        jac=lambda w: 2 * cov @ w,
        bounds=[(0, 1)] * n,
        constraints=constraints,
        method="SLSQP",
        options={"ftol": 1e-12, "maxiter": 500},
    )
    if not result.success:
        raise RuntimeError(f"Optimization failed (target={target}): {result.message}")
    return np.clip(result.x, 0, None) / np.clip(result.x, 0, None).sum()


def efficient_frontier(mu: np.ndarray, cov: np.ndarray, points: int = 60) -> pd.DataFrame:
    w_mvp = min_variance_long_only(mu, cov)
    targets = np.linspace(w_mvp @ mu, mu.max(), points)
    rows = []
    for target in targets:
        w = min_variance_long_only(mu, cov, target)
        rows.append({"Return": w @ mu, "Volatility": np.sqrt(w @ cov @ w), **{f"w_{i}": v for i, v in enumerate(w)}})
    return pd.DataFrame(rows)


def plot_opportunity_set(sim, frontier, mvp_long, assets, mu, cov, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    cloud = ax.scatter(
        sim["Volatility"] * 100,
        sim["Return"] * 100,
        c=sim["Sharpe"],
        cmap="Blues",
        s=6,
        alpha=0.55,
        linewidths=0,
        label="Random long-only portfolios",
        rasterized=True,
    )
    ax.plot(
        frontier["Volatility"] * 100,
        frontier["Return"] * 100,
        color=INK,
        linewidth=2,
        label="Efficient frontier (long-only)",
    )

    asset_vol = np.sqrt(np.diag(cov)) * 100
    ax.scatter(asset_vol, mu * 100, color=INK_MUTED, s=36, zorder=4, edgecolors=SURFACE, linewidths=1.5, label="Individual assets")
    for name, x, y in zip(assets, asset_vol, mu * 100):
        ax.annotate(name, (x, y), xytext=(6, 5), textcoords="offset points", fontsize=8.5, color=INK_MUTED)

    mvp_ret, mvp_vol, _ = portfolio_stats(mvp_long, mu, cov, 0.0)
    ax.scatter(
        [mvp_vol * 100], [mvp_ret * 100], marker="*", s=260, color=ORANGE, edgecolors=SURFACE, linewidths=1.5, zorder=5,
        label="Minimum variance portfolio (long-only)",
    )
    ax.annotate(
        f"MVP  vol {mvp_vol:.1%}, ret {mvp_ret:.1%}",
        (mvp_vol * 100, mvp_ret * 100),
        xytext=(14, -14),
        textcoords="offset points",
        fontsize=9,
        color=INK,
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.25", "fc": SURFACE, "ec": "none", "alpha": 0.85},
    )

    ax.margins(x=0.04)
    ax.set_xlabel("Annualized volatility (%)", color=INK_MUTED)
    ax.set_ylabel("Expected annual return (%)", color=INK_MUTED)
    ax.set_title("Portfolio opportunity set, minimum variance portfolio and efficient frontier", color=INK, fontsize=12, loc="left")
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED)

    cbar = fig.colorbar(cloud, ax=ax, pad=0.015)
    cbar.set_label("Sharpe ratio of random portfolios", color=INK_MUTED)
    cbar.ax.tick_params(colors=INK_MUTED)
    cbar.outline.set_visible(False)

    legend = ax.legend(loc="lower right", frameon=False, fontsize=9, labelcolor=INK_MUTED)
    for handle in legend.legend_handles[:1]:
        handle.set_color(BLUE)
    fig.tight_layout()
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--returns", type=Path, default=Path(__file__).parent / "output" / "return_matrix.csv")
    parser.add_argument("--n", type=int, default=10_000, help="Number of random portfolios")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rf", type=float, default=0.0, help="Annual risk-free rate used only for the Sharpe color scale")
    args = parser.parse_args()

    out_dir = args.returns.parent
    returns = pd.read_csv(args.returns, index_col=0, dtype={0: str})
    returns = returns.astype(float)
    assets = list(returns.columns)
    mu = (returns.mean() * TRADING_DAYS_PER_YEAR).to_numpy()
    cov = (returns.cov() * TRADING_DAYS_PER_YEAR).to_numpy()

    sim, sim_weights = simulate_portfolios(mu, cov, args.n, args.seed, args.rf)
    sim_out = pd.concat([sim, pd.DataFrame(sim_weights, columns=[f"w_{a}" for a in assets])], axis=1)
    sim_out.to_csv(out_dir / "portfolios_simulated.csv", index=False)

    w_free = mvp_closed_form(cov)
    w_long = min_variance_long_only(mu, cov)

    frontier = efficient_frontier(mu, cov)
    frontier.columns = ["Return", "Volatility"] + [f"w_{a}" for a in assets]
    frontier.to_csv(out_dir / "efficient_frontier.csv", index=False)

    best_sim = sim.loc[sim["Volatility"].idxmin()]
    mvp_table = pd.DataFrame({"Closed-form MVP (shorting allowed)": w_free, "Long-only MVP": w_long}, index=assets)
    mvp_table.to_csv(out_dir / "mvp_weights.csv")

    plot_opportunity_set(sim, frontier, w_long, assets, mu, cov, out_dir / "opportunity_set.png")

    summary = pd.DataFrame(
        {
            "Expected return": [w_free @ mu, w_long @ mu, best_sim["Return"]],
            "Volatility": [np.sqrt(w_free @ cov @ w_free), np.sqrt(w_long @ cov @ w_long), best_sim["Volatility"]],
        },
        index=["Closed-form MVP (shorting allowed)", "Long-only MVP", f"Lowest-vol of {args.n:,} random portfolios"],
    )
    summary.to_csv(out_dir / "mvp_summary.csv")

    pd.set_option("display.float_format", lambda v: f"{v:.4f}")
    pd.set_option("display.width", 120)
    print(f"Assets: {assets}")
    print(f"Observations: {len(returns)} daily returns, {args.n:,} random portfolios (seed {args.seed})")
    print("\n=== Minimum Variance Portfolio weights ===")
    print(mvp_table)
    print("\n=== MVP risk / return ===")
    print(summary)
    print(f"\nResults written to {out_dir}/ (opportunity_set.png, mvp_weights.csv, mvp_summary.csv, ...)")


if __name__ == "__main__":
    main()
