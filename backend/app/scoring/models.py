"""Shared value objects for the Digital Investor Profiling scoring engine.

Pure, stateless, stdlib-only (dataclasses + enum). No FastAPI, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class RiskLevel(IntEnum):
    """Ordered risk band. IntEnum so `>`/`<`/`<=`/`>=` compare meaningfully."""

    LOW = 1
    MODERATE = 2
    HIGH = 3

    @property
    def label(self) -> str:
        return {
            RiskLevel.LOW: "Low",
            RiskLevel.MODERATE: "Moderate",
            RiskLevel.HIGH: "High",
        }[self]


class TrafficLight(Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class ConsequenceOfFailure(Enum):
    ACCEPTABLE = "ACCEPTABLE"
    UNACCEPTABLE = "UNACCEPTABLE"
    UNKNOWN = "UNKNOWN"


# Spec's allocation mapping: growth-asset weight ceiling per risk level.
# LOW  -> <30% growth assets
# MODERATE -> 30-70% growth assets
# HIGH -> up to 100% growth assets
GROWTH_WEIGHT_CEILINGS: dict[RiskLevel, float] = {
    RiskLevel.LOW: 0.30,
    RiskLevel.MODERATE: 0.70,
    RiskLevel.HIGH: 1.00,
}


@dataclass(frozen=True)
class CapitalMarketExpectations:
    """Long-term capital market assumptions used to translate a required
    rate of return into a required growth-asset weight.

    Defaults (confirmed Taiwan-market values):
      - growth_return=0.06: Vanguard/JPMorgan 2026 long-term capital market
        assumptions for a globally-diversified growth allocation.
      - defensive_return=0.02: Taiwan 10-year government bond yield range.
      - inflation=0.018: Taiwan central bank's official 2025 CPI forecast
        (1.81%).
    """

    growth_return: float = 0.06
    defensive_return: float = 0.02
    inflation: float = 0.018
    growth_volatility: float = 0.15
    defensive_volatility: float = 0.05

    def __post_init__(self) -> None:
        if not self.growth_return > self.defensive_return:
            raise ValueError(
                "growth_return must be greater than defensive_return "
                f"(got growth_return={self.growth_return!r}, "
                f"defensive_return={self.defensive_return!r})"
            )

    def blended_return(self, growth_weight: float) -> float:
        return growth_weight * self.growth_return + (1 - growth_weight) * self.defensive_return


DEFAULT_CME = CapitalMarketExpectations()


@dataclass(frozen=True)
class FinancialGoal:
    target_amount: float
    years: float
    current_assets: float = 0.0
    annual_contribution: float = 0.0
    consequence_of_failure: ConsequenceOfFailure = ConsequenceOfFailure.UNKNOWN
    target_in_todays_money: bool = True

    def __post_init__(self) -> None:
        if not self.target_amount > 0:
            raise ValueError(f"target_amount must be > 0 (got {self.target_amount!r})")
        if not self.years > 0:
            raise ValueError(f"years must be > 0 (got {self.years!r})")
        if not self.current_assets >= 0:
            raise ValueError(f"current_assets must be >= 0 (got {self.current_assets!r})")
        if not self.annual_contribution >= 0:
            raise ValueError(
                f"annual_contribution must be >= 0 (got {self.annual_contribution!r})"
            )

    def nominal_target(self, inflation: float) -> float:
        if self.target_in_todays_money:
            return self.target_amount * (1 + inflation) ** self.years
        return self.target_amount


@dataclass(frozen=True)
class RiskAbilityInputs:
    time_horizon_years: float
    annual_liquidity_need_pct: float = 0.0
    has_external_resources: bool = False

    def __post_init__(self) -> None:
        if not self.time_horizon_years > 0:
            raise ValueError(
                f"time_horizon_years must be > 0 (got {self.time_horizon_years!r})"
            )
        if not (0 <= self.annual_liquidity_need_pct <= 1):
            raise ValueError(
                "annual_liquidity_need_pct must be within [0, 1] "
                f"(got {self.annual_liquidity_need_pct!r})"
            )


CFA_ATTRIBUTES = (
    "risk_tolerance",
    "risk_preference",
    "financial_knowledge",
    "investing_experience",
    "risk_perception",
    "risk_composure",
)

PSYCHOLOGICAL_ATTRIBUTES = ("self_control", "optimism")

BEHAVIORAL_ATTRIBUTES = CFA_ATTRIBUTES + PSYCHOLOGICAL_ATTRIBUTES


@dataclass(frozen=True)
class BehavioralProfile:
    risk_tolerance: int
    risk_preference: int
    financial_knowledge: int
    investing_experience: int
    risk_perception: int
    risk_composure: int
    self_control: int
    optimism: int

    def __post_init__(self) -> None:
        for name in BEHAVIORAL_ATTRIBUTES:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(
                    f"{name} must be an int in range 1..5 (got {type(value).__name__})"
                )
            if not (1 <= value <= 5):
                raise ValueError(f"{name} must be within 1..5 (got {value!r})")

    @property
    def cfa_scores(self) -> dict:
        return {name: getattr(self, name) for name in CFA_ATTRIBUTES}

    def as_dict(self) -> dict:
        return {name: getattr(self, name) for name in BEHAVIORAL_ATTRIBUTES}
