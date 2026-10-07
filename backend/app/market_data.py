"""Optional historical price loader backed by yfinance (Yahoo Finance).

Nothing in the scoring or API path imports this module; it exists so metrics
such as Sharpe ratio, annualized volatility and max drawdown can be computed
from real prices later. yfinance is imported lazily so the API starts (and the
tests run) without touching the network or loading pandas.

Yahoo tickers for Taiwan-listed securities carry a suffix, e.g. "0050.TW".
"""

from __future__ import annotations

from datetime import date


def fetch_adjusted_closes(
    ticker: str, start: date, end: date | None = None
) -> dict[date, float]:
    """Return {trading day: dividend/split-adjusted close} for `ticker`.

    Raises ValueError when Yahoo returns no rows (unknown ticker or no data).
    """
    import yfinance as yf

    frame = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
    if frame.empty:
        raise ValueError(f"No price data returned for {ticker!r}")
    return {ts.date(): float(close) for ts, close in frame["Close"].dropna().items()}
