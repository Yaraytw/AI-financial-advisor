"""
Robo-Advisor Assignment 2 — Part I & II
Modern Portfolio Theory: data collection, return/risk analysis.

Part I:
  1. Download >= 5 years of daily Adjusted Close prices for the chosen assets.
  2. Align dates across assets and handle missing values.
  3. Compute daily returns and assemble the return matrix.

Part II:
  For each asset: average return, annualized return, standard deviation,
  annualized volatility. Also builds the correlation matrix and the
  covariance matrix across all assets.

Usage:
  python mpt_analysis.py                 # pulls data from Yahoo Finance via yfinance
  python mpt_analysis.py --csv prices.csv  # use a local CSV instead (Date index, one column per ticker, Adj Close)

Output CSVs are written to the output/ directory next to this script.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252

# Eight diversified assets: Taiwan + US equity, emerging-market equity,
# US bond, Taiwan-listed long-duration US treasury bond, gold, and REIT.
ASSETS = {
    "SPY": "US Large-Cap Equity ETF (S&P 500)",
    "VWO": "Emerging Markets Equity ETF",
    "0050.TW": "Taiwan Top 50 Equity ETF (Yuanta/P-shares)",
    "AGG": "US Aggregate Bond ETF",
    "00679B.TWO": "Taiwan-listed 20+ Year US Treasury Bond ETF",
    "GLD": "Gold ETF",
    "VNQ": "US REIT ETF",
    "DBC": "Broad Commodity ETF",
}

START_DATE = "2019-01-01"  # >= 5 years of history through today
END_DATE = None  # None = through latest available


def download_prices(tickers: list[str], start: str, end: str | None) -> pd.DataFrame:
    """Download daily Adjusted Close prices for each ticker via yfinance."""
    import yfinance as yf

    frames = {}
    failed = []
    for ticker in tickers:
        data = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)
        if data.empty:
            failed.append(ticker)
            continue
        adj = data["Adj Close"]
        frames[ticker] = adj.iloc[:, 0] if isinstance(adj, pd.DataFrame) else adj
    if failed:
        print(f"WARNING: no data for {failed}; continuing without them.", file=sys.stderr)
    if len(frames) < 5:
        raise RuntimeError(f"Only {len(frames)} assets downloaded; the assignment needs at least 5.")
    prices = pd.DataFrame(frames)
    prices.index.name = "Date"
    return prices


def _read_csv_text(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str)
    # Taiwan data exports are often Big5 (cp950) instead of UTF-8.
    for enc in ("utf-8-sig", "cp950"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {path}; save it as UTF-8 CSV.")


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.str.replace(",", "", regex=False).str.strip(), errors="coerce")


def load_prices_from_csv(path: Path, price_col: str | None = None) -> pd.DataFrame:
    """Load prices from a wide CSV (Date + one column per ticker) or a TEJ-style long CSV.

    Long format has one row per (security, date): a date column, a security-code
    column, and a price column (pass --price-col, or it picks a column whose name
    contains 調整 / adj / 收盤價). .xlsx files work too.
    """
    df = _read_csv_text(path)
    df.columns = [str(c).strip() for c in df.columns]
    date_col = next((c for c in df.columns if c.lower() in ("date", "mdate") or c in ("年月日", "日期")), None)
    id_col = next(
        (c for c in df.columns if c.lower() in ("coid", "ticker", "symbol") or c in ("證券代碼", "證券碼", "代號", "公司")),
        None,
    )
    if date_col and id_col:
        price_col = price_col or next(
            (c for c in df.columns if "調整" in c or "adj" in c.lower() or "收盤價" in c), None
        )
        if price_col is None or price_col not in df.columns:
            raise ValueError(f"Pass --price-col with one of: {list(df.columns)}")
        long = pd.DataFrame(
            {
                "Date": pd.to_datetime(df[date_col].str.strip()),
                "id": df[id_col].str.strip(),
                "price": _to_number(df[price_col]),
            }
        )
        prices = long.pivot_table(index="Date", columns="id", values="price", aggfunc="last")
    else:
        prices = df.set_index(df.columns[0])
        prices.index = pd.to_datetime(prices.index.str.strip())
        prices = prices.apply(_to_number)
    prices.index.name = "Date"
    prices.columns.name = None
    return prices


def clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Align trading dates and handle missing values.

    - Drop dates where every asset is missing (e.g. exchange holidays unique
      to one market already show up as NaN only for that asset).
    - Forward-fill isolated gaps (an asset not trading on a date the other
      market was open); leading NaNs are never back-filled.
    - Drop the rows at the start where an asset hasn't listed yet, so every
      asset shares the same common period.
    """
    prices = prices.sort_index()
    prices = prices.dropna(how="all")
    prices = prices.ffill()
    # Trim to the common period where every asset actually has data.
    prices = prices.dropna(axis=0, how="any")
    return prices


def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily simple returns, one column per asset (the "return matrix")."""
    returns = prices.pct_change().dropna(how="all")
    return returns


def summary_stats(returns: pd.DataFrame) -> pd.DataFrame:
    avg_daily = returns.mean()
    std_daily = returns.std()
    annualized_return = (1 + avg_daily) ** TRADING_DAYS_PER_YEAR - 1
    annualized_vol = std_daily * np.sqrt(TRADING_DAYS_PER_YEAR)

    stats = pd.DataFrame(
        {
            "Average Daily Return": avg_daily,
            "Annualized Return": annualized_return,
            "Daily Std Dev": std_daily,
            "Annualized Volatility": annualized_vol,
        }
    )
    return stats


def ranked_pairs(corr: pd.DataFrame) -> pd.Series:
    """Unique asset pairs sorted from highest to lowest correlation."""
    mask = np.triu(np.ones(corr.shape, dtype=bool), k=1)
    pairs = corr.where(mask).stack().dropna()
    pairs.index = [f"{a} - {b}" for a, b in pairs.index]
    return pairs.sort_values(ascending=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, nargs="+", default=None, help="Path to a local CSV of Adjusted Close prices instead of downloading")
    parser.add_argument("--price-col", default=None, help="Price column name when --csv is a long-format file (e.g. TEJ export)")
    parser.add_argument("--start", default=START_DATE)
    parser.add_argument("--end", default=END_DATE)
    args = parser.parse_args()

    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)

    if args.csv:
        prices = pd.concat([load_prices_from_csv(f, args.price_col) for f in args.csv], axis=1)
        prices = prices.loc[:, ~prices.columns.duplicated()]
    else:
        try:
            prices = download_prices(list(ASSETS.keys()), args.start, args.end)
        except Exception as exc:  # network/API failure
            print(f"Failed to download data via yfinance: {exc}", file=sys.stderr)
            print(
                "Supply prices locally instead: python mpt_analysis.py --csv <path_to_prices.csv>\n"
                "The CSV should have a 'Date' index column and one column per ticker of Adjusted Close prices.",
                file=sys.stderr,
            )
            sys.exit(1)

    prices = clean_prices(prices)
    prices.to_csv(out_dir / "prices_cleaned.csv")

    returns = compute_returns(prices)
    returns.to_csv(out_dir / "return_matrix.csv")

    stats = summary_stats(returns)
    stats.to_csv(out_dir / "summary_stats.csv")

    corr = returns.corr()
    corr.to_csv(out_dir / "correlation_matrix.csv")

    cov = returns.cov()
    cov.to_csv(out_dir / "covariance_matrix.csv")

    cov_annualized = cov * TRADING_DAYS_PER_YEAR
    cov_annualized.to_csv(out_dir / "covariance_matrix_annualized.csv")

    pd.set_option("display.float_format", lambda v: f"{v:.4f}")
    print(f"Data period: {prices.index.min().date()} to {prices.index.max().date()} ({len(prices)} trading days)")
    print("\n=== Return & Risk Summary ===")
    print(stats)
    print("\n=== Correlation Matrix ===")
    print(corr)
    pairs = ranked_pairs(corr)
    pairs.to_csv(out_dir / "correlation_pairs_ranked.csv", header=["correlation"])
    print("\n=== Highest correlations (Q1) ===")
    print(pairs.head(5))
    print("\n=== Lowest / negative correlations (Q2, Q3) ===")
    print(pairs.tail(5).sort_values())
    print("\n=== Covariance Matrix (daily) ===")
    print(cov)
    print(f"\nFull results written to {out_dir}/")


if __name__ == "__main__":
    main()
