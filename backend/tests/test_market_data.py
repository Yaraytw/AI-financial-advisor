import sys
import types
from datetime import date, datetime

import pytest

from app.market_data import fetch_adjusted_closes


class _Series:
    def __init__(self, rows):
        self._rows = rows

    def dropna(self):
        return self

    def items(self):
        return iter(self._rows)


class _Frame:
    def __init__(self, rows):
        self.empty = not rows
        self._rows = rows

    def __getitem__(self, column):
        assert column == "Close"
        return _Series(self._rows)


def _install_fake_yfinance(monkeypatch, rows):
    calls = {}

    class Ticker:
        def __init__(self, symbol):
            calls["symbol"] = symbol

        def history(self, **kwargs):
            calls["kwargs"] = kwargs
            return _Frame(rows)

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Ticker))
    return calls


def test_returns_date_keyed_adjusted_closes(monkeypatch):
    rows = [(datetime(2024, 1, 2), 100.0), (datetime(2024, 1, 3), 101.5)]
    calls = _install_fake_yfinance(monkeypatch, rows)

    result = fetch_adjusted_closes("0050.TW", date(2024, 1, 1))

    assert result == {date(2024, 1, 2): 100.0, date(2024, 1, 3): 101.5}
    assert calls["symbol"] == "0050.TW"
    assert calls["kwargs"]["auto_adjust"] is True


def test_empty_result_raises(monkeypatch):
    _install_fake_yfinance(monkeypatch, [])
    with pytest.raises(ValueError):
        fetch_adjusted_closes("BAD", date(2024, 1, 1))
