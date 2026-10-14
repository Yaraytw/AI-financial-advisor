# Robo-Advisor Assignment 3 — Investor Profiling and Optimal Portfolio Selection

Questionnaire -> risk score -> target volatility -> optimizer picks the portfolio on the
efficient frontier. No weight is typed in anywhere; they all come from `scipy` optimizers.

| File | Role |
|---|---|
| `risk_profile.py` | 10-question questionnaire (5 on ability, 5 on willingness), scoring, 3-type classification, four example investors |
| `robo_advisor.py` | data loading, mu/Sigma, long-only efficient frontier (SLSQP + linprog), score -> target-volatility optimization, charts, CSV/JSON output |
| `make_report.py` | builds the Chinese PDF report (`output/HW3_report.pdf`) from the run's output files |

## Setup

```
cd assignments/hw3
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```
# TEJ price files (same .xlsx exports as Assignment 2; cleaned with the Assignment 2 code)
python robo_advisor.py --prices ../mpt/data/*.xlsx --source "TEJ Pro 調整股價(日)"

# or the daily return matrix Assignment 2 wrote (Date + one column per asset)
python robo_advisor.py --returns ../mpt/output/return_matrix.csv --source "TEJ Pro 調整股價(日)"

# test only: Yahoo Finance via yfinance (no --returns/--prices)
python robo_advisor.py

python robo_advisor.py --interactive ...   # also answer the questionnaire yourself
python robo_advisor.py --max-weight 1.0 ... # uncapped
python make_report.py --student "姓名 學號"
```

Assets (same as Assignment 2): 0050, 0056, 00646, 1216, 2412, 00679B, 00720B, 00635U.
Outputs go to `output/`: `fig1_efficient_frontier.png`, `fig2_allocation_comparison.png`,
`fig3_score_mapping.png`, `fig4_questionnaire_scores.png`, `investor_portfolios.csv`,
`efficient_frontier.csv`, `cap_sensitivity.csv`, `asset_stats.csv`, `results.json`, `HW3_report.pdf`.

`robo_advisor.py` asserts that every selected portfolio sits on the efficient frontier and that none of
the random feasible portfolios dominates the frontier.

## Method in one paragraph

Overall risk score `S = min(ability, willingness)` (0-100); `S < 35` Conservative, `35 <= S < 65`
Moderate, `S >= 65` Aggressive. Expected returns are mean daily return x 252, covariance is daily
covariance x 252, weights are long-only with a 40% cap per asset (`--max-weight`). The target volatility
is `sigma*(S) = sigma_MVP + S/100 (sigma_MAX - sigma_MVP)` and the portfolio solves
`max w'mu  s.t. w'Sigma w <= sigma*^2`.

TEJ data is licensed for campus use, so `data/` and `output/` are gitignored.
