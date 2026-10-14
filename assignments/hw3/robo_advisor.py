"""
Robo-Advisor Assignment 3 - Investor profiling and optimal portfolio selection.

Pipeline (every portfolio weight below comes from an optimizer, none is typed in):

  1. Load daily returns of 8 Taiwan-listed assets
       --returns FILE    wide daily-return matrix (the Assignment 2 output)
       --prices FILES    TEJ .xlsx / long CSV / wide price CSV (adjusted close);
                         cleaned and converted to returns with the Assignment 2 code
       (neither)         Yahoo Finance download via yfinance - for code testing only
  2. Estimate expected returns (mean daily return x 252) and the covariance matrix
     (daily covariance x 252).
  3. Build the long-only efficient frontier with an optional per-asset weight cap
     (SLSQP minimum variance for every target return).
  4. Score each investor's questionnaire (risk_profile.py) -> score in [0, 100].
  5. Map the score to a target volatility on the frontier,
         sigma*(S) = sigma_MVP + S/100 * (sigma_MAX - sigma_MVP),
     and solve  max w'mu  s.t.  w'Sigma w <= sigma*^2, sum(w)=1, 0 <= w <= cap.
  6. Write charts (efficient frontier, allocation comparison, score mapping),
     CSV tables and results.json, which make_report.py turns into the PDF report.

Usage:
  python robo_advisor.py --returns data/return_matrix.csv
  python robo_advisor.py --prices ../mpt/data/*.xlsx --source "TEJ Pro, adjusted daily close"
  python robo_advisor.py --interactive --returns data/return_matrix.csv   # answer the questionnaire yourself
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize

import risk_profile as rp

HERE = Path(__file__).resolve().parent
TRADING_DAYS = 252

# Same 8 assets as Assignment 2. The Yahoo tickers are only used for the yfinance test fallback.
ASSETS: dict[str, dict] = {
    "0050":   {"name": "Yuanta Taiwan Top 50 ETF",         "group": "Equity ETFs",       "yahoo": "0050.TW"},
    "0056":   {"name": "Yuanta Taiwan High Dividend ETF",  "group": "Equity ETFs",       "yahoo": "0056.TW"},
    "00646":  {"name": "Yuanta S&P 500 ETF",               "group": "Equity ETFs",       "yahoo": "00646.TW"},
    "1216":   {"name": "Uni-President (defensive stock)",  "group": "Defensive stocks",  "yahoo": "1216.TW"},
    "2412":   {"name": "Chunghwa Telecom (defensive stock)", "group": "Defensive stocks", "yahoo": "2412.TW"},
    "00679B": {"name": "Yuanta 20+Y US Treasury Bond ETF", "group": "Bonds",             "yahoo": "00679B.TWO"},
    "00720B": {"name": "Yuanta IG Corporate Bond ETF",     "group": "Bonds",             "yahoo": "00720B.TWO"},
    "00635U": {"name": "Yuanta S&P GSCI Gold ETF",         "group": "Gold",              "yahoo": "00635U.TW"},
}
GROUP_ORDER = ["Equity ETFs", "Defensive stocks", "Bonds", "Gold"]

# Okabe-Ito based, distinguishable for colour-blind readers; one colour per asset.
ASSET_COLORS = {
    "0050": "#0072B2", "0056": "#56B4E9", "00646": "#009E73", "1216": "#E69F00",
    "2412": "#F0E442", "00679B": "#CC79A7", "00720B": "#D55E00", "00635U": "#7F7F7F",
}
PROFILE_COLORS = {"Conservative": "#009E73", "Moderate": "#E69F00", "Aggressive": "#D55E00"}
FALLBACK_PROFILE_COLOR = "#6A3D9A"
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e3e2dd", "#fcfcfb"


# --------------------------------------------------------------------------- data
def load_returns(args: argparse.Namespace) -> tuple[pd.DataFrame, str]:
    """Return (daily returns, human-readable source description)."""
    if args.returns:
        returns = pd.read_csv(args.returns, index_col=0, parse_dates=True).astype(float)
        source = args.source or f"Daily return matrix {args.returns.name}"
    elif args.prices:
        sys.path.insert(0, str(HERE.parent / "mpt"))
        from mpt_analysis import clean_prices, compute_returns, load_prices_from_csv  # Assignment 2 code

        prices = pd.concat([load_prices_from_csv(f, args.price_col) for f in args.prices], axis=1)
        prices = prices.loc[:, ~prices.columns.duplicated()]
        returns = compute_returns(clean_prices(prices))
        source = args.source or "Prices from " + ", ".join(f.name for f in args.prices)
    else:
        import yfinance as yf

        frames = {}
        for code, meta in ASSETS.items():
            data = yf.download(meta["yahoo"], start=args.start, auto_adjust=False, progress=False)
            if data.empty:
                raise RuntimeError(f"No Yahoo Finance data for {meta['yahoo']}; pass --returns or --prices instead.")
            adj = data["Adj Close"]
            frames[code] = adj.iloc[:, 0] if isinstance(adj, pd.DataFrame) else adj
        prices = pd.DataFrame(frames).sort_index().dropna(how="all").ffill().dropna()
        returns = prices.pct_change().dropna()
        source = "Yahoo Finance via yfinance (adjusted close) - TEST DATA ONLY"
    returns.index.name = "Date"
    missing = [a for a in ASSETS if a not in returns.columns]
    if missing:
        raise ValueError(f"Data is missing assets {missing}; found {list(returns.columns)}")
    returns = returns[list(ASSETS)].dropna()
    return returns, source


# ----------------------------------------------------------------------- optimizer
class Universe:
    """Expected returns, covariance and the constraint set shared by every optimization."""

    def __init__(self, returns: pd.DataFrame, max_weight: float, rf: float):
        self.assets = list(returns.columns)
        self.returns = returns
        self.mu = returns.mean().to_numpy() * TRADING_DAYS
        self.cov = returns.cov().to_numpy() * TRADING_DAYS
        self.n = len(self.assets)
        self.cap = max_weight
        self.rf = rf
        if self.cap * self.n < 1 - 1e-9:
            raise ValueError(f"max weight {self.cap} is infeasible for {self.n} assets (need cap >= 1/n)")
        self.bounds = [(0.0, self.cap)] * self.n

    # -- primitives
    def ret(self, w):
        return float(np.asarray(w) @ self.mu)

    def vol(self, w):
        w = np.asarray(w)
        return float(np.sqrt(w @ self.cov @ w))

    @staticmethod
    def _clean(w: np.ndarray) -> np.ndarray:
        w = np.clip(w, 0, None)
        w[w < 1e-6] = 0.0
        return w / w.sum()

    # -- optimizers
    def min_variance(self, target_return: float | None = None) -> np.ndarray:
        cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
        if target_return is not None:
            cons.append({"type": "eq", "fun": lambda w: w @ self.mu - target_return})
        res = minimize(
            lambda w: w @ self.cov @ w, np.full(self.n, 1 / self.n), jac=lambda w: 2 * self.cov @ w,
            bounds=self.bounds, constraints=cons, method="SLSQP", options={"ftol": 1e-14, "maxiter": 1000},
        )
        if not res.success:
            raise RuntimeError(f"min-variance optimization failed (target={target_return}): {res.message}")
        return self._clean(res.x)

    def max_return(self) -> np.ndarray:
        """Highest-return feasible portfolio (a linear program)."""
        res = linprog(-self.mu, A_eq=np.ones((1, self.n)), b_eq=[1.0], bounds=self.bounds, method="highs")
        if not res.success:
            raise RuntimeError(res.message)
        return self._clean(res.x)

    def max_return_given_vol(self, sigma: float, start: np.ndarray) -> np.ndarray:
        """Efficient-frontier portfolio with volatility sigma: max w'mu s.t. w'Sigma w <= sigma^2."""
        cons = [
            {"type": "eq", "fun": lambda w: w.sum() - 1},
            {"type": "ineq", "fun": lambda w: sigma**2 - w @ self.cov @ w, "jac": lambda w: -2 * self.cov @ w},
        ]
        res = minimize(
            lambda w: -w @ self.mu, start, jac=lambda w: -self.mu,
            bounds=self.bounds, constraints=cons, method="SLSQP", options={"ftol": 1e-14, "maxiter": 1000},
        )
        if not res.success:
            raise RuntimeError(f"target-volatility optimization failed (sigma={sigma:.4f}): {res.message}")
        return self._clean(res.x)

    def frontier(self, points: int = 80) -> pd.DataFrame:
        w_min, w_max = self.min_variance(), self.max_return()
        rows = []
        for target in np.linspace(self.ret(w_min), self.ret(w_max), points):
            w = self.min_variance(target)
            rows.append({"Return": self.ret(w), "Volatility": self.vol(w), **{f"w_{a}": x for a, x in zip(self.assets, w)}})
        return pd.DataFrame(rows)

    def simulate(self, n: int, seed: int) -> pd.DataFrame:
        """Random feasible portfolios (opportunity set) - only used to draw the cloud and to verify the frontier."""
        rng = np.random.default_rng(seed)
        w = rng.dirichlet(np.ones(self.n), size=n * 4)
        w = w[(w <= self.cap).all(axis=1)][:n]
        vol = np.sqrt(np.einsum("ij,jk,ik->i", w, self.cov, w))
        return pd.DataFrame({"Return": w @ self.mu, "Volatility": vol})

    def metrics(self, w: np.ndarray) -> dict:
        """Return/risk summary of a weight vector, plus an in-sample daily-rebalanced back-test."""
        r, s = self.ret(w), self.vol(w)
        daily = self.returns.to_numpy() @ w
        wealth = np.cumprod(1 + daily)
        drawdown = wealth / np.maximum.accumulate(wealth) - 1
        rolling = pd.Series(daily).add(1).rolling(TRADING_DAYS).apply(np.prod, raw=True).dropna() - 1
        years = len(daily) / TRADING_DAYS
        return {
            "expected_return": r,
            "volatility": s,
            "sharpe": (r - self.rf) / s,
            "var95_1y": r - 1.645 * s,  # normal-approximation 5th-percentile 1-year return
            "hist_cagr": float(wealth[-1] ** (1 / years) - 1),
            "hist_max_drawdown": float(drawdown.min()),
            "hist_worst_1y": float(rolling.min()),
            "hist_best_1y": float(rolling.max()),
        }


def target_vol(score: float, sigma_min: float, sigma_max: float) -> float:
    """Linear map from the 0-100 risk score to a volatility between the MVP and the max-return portfolio."""
    return sigma_min + (score / 100.0) * (sigma_max - sigma_min)


def select_portfolios(uni: Universe, profiles: dict[str, rp.RiskProfile]) -> dict[str, dict]:
    w_min, w_max = uni.min_variance(), uni.max_return()
    s_min, s_max = uni.vol(w_min), uni.vol(w_max)
    out = {}
    for name, prof in profiles.items():
        sigma = target_vol(prof.score, s_min, s_max)
        # Start from the point of the min-variance path closest to the target: blend MVP and max-return weights.
        blend = (sigma - s_min) / (s_max - s_min) if s_max > s_min else 0.0
        w = uni.max_return_given_vol(sigma, (1 - blend) * w_min + blend * w_max)
        out[name] = {"weights": w, "target_vol": sigma, **uni.metrics(w)}
    return out


def verify_on_frontier(uni: Universe, selected: dict[str, dict]) -> dict[str, float]:
    """Cross-check: the selected portfolio's return must equal the min-variance portfolio's variance at that return."""
    gaps = {}
    for name, sel in selected.items():
        w_chk = uni.min_variance(sel["expected_return"] - 1e-9)
        gaps[name] = abs(uni.vol(w_chk) - sel["volatility"])
    return gaps


def cap_sensitivity(returns: pd.DataFrame, profiles: dict[str, rp.RiskProfile], caps: list[float], rf: float) -> pd.DataFrame:
    rows = []
    for cap in caps:
        uni = Universe(returns, cap, rf)
        for name, sel in select_portfolios(uni, profiles).items():
            rows.append({"max_weight": cap, "profile": name, "expected_return": sel["expected_return"],
                         "volatility": sel["volatility"], **{a: w for a, w in zip(uni.assets, sel["weights"])}})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------- charts
def _style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED)


def _color(name: str) -> str:
    return PROFILE_COLORS.get(name, FALLBACK_PROFILE_COLOR)


def plot_frontier(uni, cloud, frontier, selected, out: Path):
    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    ax.scatter(cloud["Volatility"] * 100, cloud["Return"] * 100, s=5, color="#9bb7d4", alpha=0.35, linewidths=0,
               rasterized=True, label="Random feasible portfolios")
    ax.plot(frontier["Volatility"] * 100, frontier["Return"] * 100, color=INK, linewidth=2.2, label="Efficient frontier")
    vols = np.sqrt(np.diag(uni.cov)) * 100
    ax.scatter(vols, uni.mu * 100, color=INK_MUTED, s=30, zorder=4, edgecolors=SURFACE, linewidths=1.2, label="Individual assets")
    for a, x, y in zip(uni.assets, vols, uni.mu * 100):
        ax.annotate(a, (x, y), xytext=(5, 4), textcoords="offset points", fontsize=8, color=INK_MUTED)
    label_offsets = {"Conservative": (-90, 52), "Moderate": (16, -34), "Aggressive": (-70, 34),
                     "Willing-but-Unable": (24, -62)}
    for i, (name, sel) in enumerate(selected.items()):
        ax.scatter([sel["volatility"] * 100], [sel["expected_return"] * 100], s=150, color=_color(name), zorder=6,
                   edgecolors="white", linewidths=1.5, label=name)
        ax.annotate(f"{name}\nσ {sel['volatility']:.1%}  E[R] {sel['expected_return']:.1%}",
                    (sel["volatility"] * 100, sel["expected_return"] * 100), xytext=label_offsets.get(name, (16, -34)),
                    textcoords="offset points", fontsize=8.5, color=INK, fontweight="bold",
                    bbox={"boxstyle": "round,pad=0.25", "fc": SURFACE, "ec": _color(name), "alpha": 0.95},
                    arrowprops={"arrowstyle": "-", "color": _color(name), "linewidth": 1.2})
    ax.set_xlabel("Portfolio risk: annualized volatility σ (%)", color=INK_MUTED)
    ax.set_ylabel("Expected annual return (%)", color=INK_MUTED)
    ax.set_title(f"Figure 1. Efficient frontier and investor-specific optimal portfolios (max {uni.cap:.0%} per asset)",
                 color=INK, fontsize=11, loc="left")
    ax.legend(loc="lower right", frameon=False, fontsize=8.5, labelcolor=INK_MUTED)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def plot_allocation(uni, selected, out: Path):
    names = list(selected)[::-1]
    fig, ax = plt.subplots(figsize=(10, 1.2 + 0.95 * len(names)), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    left = np.zeros(len(names))
    for j, asset in enumerate(uni.assets):
        vals = np.array([selected[n]["weights"][j] for n in names])
        ax.barh(names, vals * 100, left=left * 100, color=ASSET_COLORS[asset], edgecolor=SURFACE, linewidth=1.2, label=asset)
        for k, v in enumerate(vals):
            if v >= 0.05:
                dark = asset in ("2412", "1216", "00646", "0056")
                ax.text((left[k] + v / 2) * 100, k, f"{v:.0%}", ha="center", va="center", fontsize=8.5,
                        color=INK if dark else "white", fontweight="bold")
        left += vals
    ax.set_xlim(0, 100)
    ax.set_xlabel("Portfolio weight (%)", color=INK_MUTED)
    ax.set_title("Figure 2. Optimal asset allocation by investor profile", color=INK, fontsize=11, loc="left")
    ax.tick_params(colors=INK_MUTED)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.legend(ncol=8, loc="upper center", bbox_to_anchor=(0.5, -0.22), frameon=False, fontsize=8.5, labelcolor=INK_MUTED)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def plot_mapping(uni, selected, profiles, s_min, s_max, out: Path):
    fig, ax = plt.subplots(figsize=(7.5, 4.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    xs = np.linspace(0, 100, 101)
    ax.plot(xs, [target_vol(x, s_min, s_max) * 100 for x in xs], color=INK, linewidth=2)
    for name, prof in profiles.items():
        y = selected[name]["target_vol"] * 100
        ax.scatter([prof.score], [y], s=90, color=_color(name), zorder=5, edgecolors="white", linewidths=1.4)
        ax.annotate(name, (prof.score, y), xytext=(8, -12), textcoords="offset points", fontsize=8.5, color=INK)
    for edge in (35, 65):
        ax.axvline(edge, color=GRID, linestyle="--", linewidth=1)
    ax.set_xlabel("Overall risk score (0-100) = min(ability, willingness)", color=INK_MUTED)
    ax.set_ylabel("Target volatility (%)", color=INK_MUTED)
    ax.set_title("Figure 3. Risk score to target volatility", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def plot_scores(profiles, out: Path):
    names = list(profiles)
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(7.5, 4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    ax.bar(x - 0.2, [profiles[n].ability for n in names], 0.38, color="#0072B2", label="Ability (capacity)")
    ax.bar(x + 0.2, [profiles[n].willingness for n in names], 0.38, color="#E69F00", label="Willingness (tolerance)")
    for i, n in enumerate(names):
        ax.plot([i - 0.4, i + 0.4], [profiles[n].score] * 2, color=INK, linewidth=2)
        ax.text(i, profiles[n].score + 2, f"score {profiles[n].score:.0f}", ha="center", fontsize=8.5, color=INK, fontweight="bold")
    ax.set_xticks(x, names)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Factor score (0-100)", color=INK_MUTED)
    ax.set_title("Figure 4. Questionnaire scores (black line = overall score = lower factor)", color=INK, fontsize=10.5, loc="left")
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK_MUTED, loc="upper right")
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


# --------------------------------------------------------------------------- main
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--returns", type=Path, help="wide daily-return CSV (Date + one column per asset)")
    src.add_argument("--prices", type=Path, nargs="+", help="TEJ .xlsx / CSV price files (adjusted close)")
    p.add_argument("--price-col", default=None, help="price column name for long-format --prices files")
    p.add_argument("--source", default=None, help="data source text recorded in the outputs")
    p.add_argument("--start", default="2019-01-01", help="start date for the yfinance fallback")
    p.add_argument("--max-weight", type=float, default=0.40, help="per-asset weight cap (default 0.40); 1.0 = uncapped")
    p.add_argument("--rf", type=float, default=0.015, help="annual risk-free rate for Sharpe ratios (default 1.5%%)")
    p.add_argument("--n-random", type=int, default=10_000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--interactive", action="store_true", help="answer the questionnaire in the terminal as an extra investor")
    p.add_argument("--out", type=Path, default=HERE / "output")
    args = p.parse_args()

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    returns, source = load_returns(args)
    uni = Universe(returns, args.max_weight, args.rf)
    print(f"Data: {source}\nPeriod: {returns.index.min().date()} to {returns.index.max().date()} ({len(returns)} daily returns)")

    # --- investors
    profiles: dict[str, rp.RiskProfile] = {}
    answers: dict[str, dict[str, int]] = {}
    for name, ex in rp.EXAMPLE_INVESTORS.items():
        answers[name] = ex["answers"]
        profiles[name] = rp.assess(ex["answers"])
    if args.interactive:
        answers["You"] = rp.ask_interactively()
        profiles["You"] = rp.assess(answers["You"])

    # --- optimization
    frontier = uni.frontier()
    cloud = uni.simulate(args.n_random, args.seed)
    selected = select_portfolios(uni, profiles)
    gaps = verify_on_frontier(uni, selected)
    w_min, w_max = uni.min_variance(), uni.max_return()
    s_min, s_max = uni.vol(w_min), uni.vol(w_max)

    # Sanity checks that the numbers are a genuine efficient frontier.
    dominated = int(((cloud["Return"].to_numpy()[:, None] > frontier["Return"].to_numpy()[None, :] + 1e-9)
                     & (cloud["Volatility"].to_numpy()[:, None] < frontier["Volatility"].to_numpy()[None, :] - 1e-9)).any(axis=1).sum())
    for name, gap in gaps.items():
        assert gap < 5e-4, f"{name}: selected portfolio is off the frontier by {gap:.2e}"
    assert dominated == 0, f"{dominated} random portfolios beat the optimized frontier"

    # --- outputs
    summary_rows = []
    for name, prof in profiles.items():
        sel = selected[name]
        summary_rows.append({
            "investor": name, "ability": prof.ability, "willingness": prof.willingness, "score": prof.score,
            "type": prof.type_en, "binding_factor": prof.binding_factor, "target_vol": sel["target_vol"],
            **{k: sel[k] for k in ("expected_return", "volatility", "sharpe", "var95_1y", "hist_cagr", "hist_max_drawdown", "hist_worst_1y", "hist_best_1y")},
            **{a: w for a, w in zip(uni.assets, sel["weights"])},
        })
    pd.DataFrame(summary_rows).to_csv(out / "investor_portfolios.csv", index=False)
    frontier.to_csv(out / "efficient_frontier.csv", index=False)
    caps = sorted({args.max_weight, 1.0, 0.30, 0.50})
    sens = cap_sensitivity(returns, profiles, caps, args.rf)
    sens.to_csv(out / "cap_sensitivity.csv", index=False)

    stats = pd.DataFrame({"annual_return": uni.mu, "annual_volatility": np.sqrt(np.diag(uni.cov))}, index=uni.assets)
    stats.to_csv(out / "asset_stats.csv")
    pd.DataFrame(uni.cov, index=uni.assets, columns=uni.assets).to_csv(out / "covariance_annualized.csv")
    returns.corr().to_csv(out / "correlation_matrix.csv")

    plot_frontier(uni, cloud, frontier, selected, out / "fig1_efficient_frontier.png")
    plot_allocation(uni, selected, out / "fig2_allocation_comparison.png")
    plot_mapping(uni, selected, profiles, s_min, s_max, out / "fig3_score_mapping.png")
    plot_scores(profiles, out / "fig4_questionnaire_scores.png")

    results = {
        "data": {"source": source, "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
                 "n_returns": len(returns), "assets": uni.assets},
        "settings": {"max_weight": args.max_weight, "rf": args.rf, "trading_days": TRADING_DAYS,
                     "n_random": args.n_random, "seed": args.seed, "bands": [(u, en) for u, en, _ in rp.BANDS]},
        "frontier_range": {"mvp_vol": s_min, "mvp_return": uni.ret(w_min), "max_vol": s_max, "max_return": uni.ret(w_max),
                           "mvp_weights": dict(zip(uni.assets, map(float, w_min))), "max_return_weights": dict(zip(uni.assets, map(float, w_max)))},
        "verification": {"frontier_gap": gaps, "random_portfolios_dominating_frontier": dominated},
        "investors": {
            name: {"persona": rp.EXAMPLE_INVESTORS.get(name, {}).get("persona", "Interactive respondent"), "answers": answers[name],
                   "ability": prof.ability, "willingness": prof.willingness, "score": prof.score, "type": prof.type_en,
                   "type_zh": prof.type_zh, "binding_factor": prof.binding_factor,
                   **{k: (float(v) if not isinstance(v, np.ndarray) else None) for k, v in selected[name].items() if k != "weights"},
                   "weights": dict(zip(uni.assets, map(float, selected[name]["weights"])))}
            for name, prof in profiles.items()
        },
        "assets": {a: {**ASSETS[a], "annual_return": float(r), "annual_volatility": float(v)}
                   for a, r, v in zip(uni.assets, uni.mu, np.sqrt(np.diag(uni.cov)))},
    }
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))

    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    pd.set_option("display.width", 160)
    print("\n=== Investors ===")
    print(pd.DataFrame(summary_rows)[["investor", "ability", "willingness", "score", "type", "binding_factor"]].to_string(index=False))
    print("\n=== Optimal portfolios (weights from the optimizer) ===")
    print(pd.DataFrame({n: dict(zip(uni.assets, s["weights"])) for n, s in selected.items()}).T.to_string())
    print("\n=== Risk / return ===")
    print(pd.DataFrame(summary_rows)[["investor", "target_vol", "volatility", "expected_return", "sharpe", "hist_max_drawdown"]].to_string(index=False))
    print(f"\nChecks passed: each portfolio lies on the frontier; 0 of {len(cloud):,} random portfolios dominate it.")
    print(f"Results written to {out}/")


if __name__ == "__main__":
    main()
