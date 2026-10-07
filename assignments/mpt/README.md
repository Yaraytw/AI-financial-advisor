# Robo-Advisor Assignment 2 — Modern Portfolio Theory

Opportunity set and Minimum Variance Portfolio (MVP) from real market data.
Kept separate from `backend/`/`frontend/` since this is coursework, not a
product feature.

## Assets (8, Taiwan-listed, daily adjusted close from TEJ)

| Code   | Description                                  |
|--------|----------------------------------------------|
| 0050   | Yuanta Taiwan Top 50 ETF (Taiwan large-cap)  |
| 0056   | Yuanta Taiwan High Dividend ETF              |
| 00646  | Yuanta S&P 500 ETF                           |
| 00679B | Yuanta 20+ Year US Treasury Bond ETF         |
| 00720B | Yuanta Investment-Grade Corporate Bond ETF   |
| 00635U | Yuanta S&P GSCI Gold ETF                     |
| 1216   | Uni-President (defensive consumer stock)     |
| 2412   | Chunghwa Telecom (defensive telecom stock)   |

Period: 2019-01-02 to 2026-10-05 (1,883 trading days). Price field: the
`收盤價(元)` column of TEJ's 調整股價(日)-除權息調整 table (adjusted for
dividends and splits).

TEJ data is licensed for campus use, so the raw exports in `data/` and the
working folder `output/` are gitignored. The raw prices are not committed; the
derived results needed for grading are in `results/` (see below).

## Setup

```
cd assignments/mpt
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Part I and II — `mpt_analysis.py`

Put one TEJ `.xlsx` export per security in `data/` (TEJ data explorer ->
個股查詢 -> pick the security, date range 2019/01/01 to latest), then:

```
python mpt_analysis.py --csv data/*.xlsx
```

Reads wide CSVs (a `Date` column plus one column per ticker), TEJ long-format
CSV/xlsx files (one row per security and date), or, with no `--csv`, downloads
the Yahoo Finance tickers listed in the script. Steps: align dates, forward-fill
isolated gaps (leading gaps are trimmed, never back-filled), compute daily
returns and the return matrix, then per-asset average daily return, annualized
return, cumulative return, CAGR, standard deviation, annualized volatility, plus
the correlation matrix, daily and annualized covariance matrices, and a ranked
list of correlation pairs.

Annualized return is reported two ways: the mean daily return compounded over
252 days, and the course formula `(1 + R)^(1/y) - 1` from cumulative return
(`Annualized Return (CAGR)`). State which one the write-up uses.

## Part III — `mpt_portfolio.py`

```
python mpt_portfolio.py            # 10,000 random portfolios, seed 42
python mpt_portfolio.py --n 20000 --seed 7
```

Reads `output/return_matrix.csv` from the previous step. Expected return is
mean daily return x 252 (so portfolio return is linear in the weights), risk is
`sqrt(w' Sigma w)` with the annualized covariance matrix.

1. Simulates random long-only portfolios (weights >= 0, sum to 1).
2. MVP two ways: closed form `w = Sigma^-1 1 / (1' Sigma^-1 1)` (negative
   weights mean shorting) and the long-only numerical solution (SLSQP).
3. Long-only efficient frontier (minimum variance for each target return from
   the MVP up to the best single asset).

Outputs in `output/`: `opportunity_set.png`, `mvp_weights.csv`,
`mvp_summary.csv`, `efficient_frontier.csv`, `portfolios_simulated.csv`.

## Results and answers

- [`ANSWERS.md`](ANSWERS.md): per-asset return and risk table, Q1 to Q3 answers,
  MVP weights and the opportunity set discussion (in Chinese).
- [`results/`](results/): the output files the answers are based on
  (`summary_stats.csv`, `return_matrix.csv`, `correlation_matrix.csv`,
  `correlation_pairs_ranked.csv`, `covariance_matrix.csv`,
  `covariance_matrix_annualized.csv`, `mvp_weights.csv`, `mvp_summary.csv`,
  `efficient_frontier.csv`, `opportunity_set.png`). They are a copy of what the
  scripts write to `output/`.
