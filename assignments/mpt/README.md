# Robo-Advisor Assignment 2 — Part I & II

Modern Portfolio Theory: data collection and return/risk analysis, kept
separate from the `backend/`/`frontend/` product code since this is
coursework, not a product feature.

## Assets selected (8, diversified by asset class and geography)

| Ticker       | Description                                   |
|--------------|------------------------------------------------|
| SPY          | US Large-Cap Equity ETF (S&P 500)              |
| VWO          | Emerging Markets Equity ETF                    |
| 0050.TW      | Taiwan Top 50 Equity ETF (Yuanta/P-shares)     |
| AGG          | US Aggregate Bond ETF                          |
| 00679B.TW    | Taiwan-listed 20+ Year US Treasury Bond ETF    |
| GLD          | Gold ETF                                       |
| VNQ          | US REIT ETF                                    |
| DBC          | Broad Commodity ETF                            |

Rationale: spans equities (US, Taiwan, emerging markets), bonds (US and a
Taiwan-listed long-duration US treasury ETF for currency/market variety),
gold, real estate, and broad commodities, so the opportunity set in a later
assignment part has genuinely different risk/return profiles to combine.

Data period: daily Adjusted Close, 2019-01-01 through latest available
(5+ years).

## Known limitation: this sandbox can't reach Yahoo Finance

This environment's outbound network policy blocks `query1/2.finance.yahoo.com`
(the host `yfinance` calls), so `mpt_analysis.py` could not actually be run
against live data here — only verified against synthetic data to confirm the
pipeline logic (cleaning, returns, stats, correlation/covariance) is correct.
No real numbers have been fabricated or committed.

To produce real results, either:
1. Run `pip install -r requirements.txt && python mpt_analysis.py` on a
   machine with normal internet access, or
2. Supply prices yourself: `python mpt_analysis.py --csv prices.csv`, where
   `prices.csv` has a `Date` index column and one column per ticker of
   Adjusted Close prices.

## What the script does (Part I)

1. Downloads (or loads from CSV) daily Adjusted Close prices for all 8
   tickers.
2. Aligns trading dates across the two exchanges (US + Taiwan) and handles
   missing values: forward/back-fill isolated gaps, then drop any
   asset/date that still has no data so every column lines up.
3. Computes daily simple returns and assembles the return matrix.

## What the script does (Part II)

For each asset: average daily return, annualized return (compounded, 252
trading days/year), daily standard deviation, and annualized volatility.
Also builds the full correlation matrix and covariance matrix (daily and
annualized) across all 8 assets.

Outputs are written to `output/`:
- `prices_cleaned.csv`
- `return_matrix.csv`
- `summary_stats.csv`
- `correlation_matrix.csv`
- `covariance_matrix.csv` / `covariance_matrix_annualized.csv`

## Still needed from the spec

The assignment text we received cuts off after Part II. Parts covering the
portfolio opportunity set simulation, the Minimum Variance Portfolio
optimization, and any required deliverables/plots are not in hand yet —
flagged in the project thread.
