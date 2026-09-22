"""Module 1: Risk Need — how much growth-asset exposure a goal requires."""

from __future__ import annotations

from dataclasses import dataclass

from app.scoring.models import (
    DEFAULT_CME,
    CapitalMarketExpectations,
    ConsequenceOfFailure,
    FinancialGoal,
    RiskLevel,
)

_BISECTION_ITERATIONS = 200
_RATE_LOWER_BOUND = -0.99
_RATE_UPPER_BOUND = 5.0
_NEAR_ZERO_RATE = 1e-9


def future_value(
    rate: float,
    years: float,
    present_value: float,
    annual_contribution: float,
) -> float:
    """Future value of a lump sum plus an ordinary (end-of-period) annuity."""

    if abs(rate) < _NEAR_ZERO_RATE:
        return present_value + annual_contribution * years
    growth_factor = (1 + rate) ** years
    return present_value * growth_factor + annual_contribution * (growth_factor - 1) / rate


def required_rate_of_return(
    goal: FinancialGoal, cme: CapitalMarketExpectations = DEFAULT_CME
) -> float:
    """Bisect for the annual rate of return that hits the goal's nominal target."""

    target = goal.nominal_target(cme.inflation)
    lo, hi = _RATE_LOWER_BOUND, _RATE_UPPER_BOUND

    fv_lo = future_value(lo, goal.years, goal.current_assets, goal.annual_contribution)
    fv_hi = future_value(hi, goal.years, goal.current_assets, goal.annual_contribution)

    if fv_lo >= target:
        # Already funded even at the bracket floor.
        return lo
    if fv_hi < target:
        # Unreachable even at the bracket ceiling; caller detects infeasibility
        # separately via the growth-weight check, not via this sentinel.
        return hi

    for _ in range(_BISECTION_ITERATIONS):
        mid = (lo + hi) / 2
        fv_mid = future_value(mid, goal.years, goal.current_assets, goal.annual_contribution)
        if fv_mid < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def required_growth_weight(
    rate_of_return: float, cme: CapitalMarketExpectations = DEFAULT_CME
) -> float:
    """Growth-asset weight implied by a required rate of return.

    Deliberately NOT clamped: negative or >1.0 values are the infeasibility /
    over-funded signal for callers to interpret.
    """

    return (rate_of_return - cme.defensive_return) / (cme.growth_return - cme.defensive_return)


def classify_risk_need(growth_weight: float) -> RiskLevel:
    clamped = min(max(growth_weight, 0.0), 1.0)
    if clamped < 0.30:
        return RiskLevel.LOW
    if clamped <= 0.70:
        return RiskLevel.MODERATE
    return RiskLevel.HIGH


@dataclass(frozen=True)
class RiskNeedAssessment:
    level: RiskLevel
    required_rate_of_return: float
    required_real_return: float
    required_growth_weight: float
    target_growth_weight: float
    nominal_target: float
    feasible: bool
    consequence_of_failure: ConsequenceOfFailure
    warnings: tuple[str, ...]


def assess_risk_need(
    goal: FinancialGoal, cme: CapitalMarketExpectations = DEFAULT_CME
) -> RiskNeedAssessment:
    nominal_target = goal.nominal_target(cme.inflation)
    ror = required_rate_of_return(goal, cme)
    real_return = (1 + ror) / (1 + cme.inflation) - 1
    raw_growth_weight = required_growth_weight(ror, cme)
    target_growth_weight = min(max(raw_growth_weight, 0.0), 1.0)
    level = classify_risk_need(raw_growth_weight)

    warnings: list[str] = []
    feasible = True

    if raw_growth_weight > 1.0:
        feasible = False
        max_deliverable_return = cme.growth_return
        warnings.append(
            f"此目標在任何資產配置下都無法達成：所需報酬率 {ror:.2%} "
            f"超過 100% 成長型資產所能提供的最高預期報酬率 "
            f"{max_deliverable_return:.2%}。"
        )
    elif raw_growth_weight > 0.90:
        warnings.append(
            f"所需成長型資產配置（{raw_growth_weight:.1%}）已逼近 100% 上限，"
            "緩衝空間很小。"
        )

    if raw_growth_weight < 0.0:
        warnings.append(
            f"此目標僅靠防禦型資產即可達成（所需成長型資產配置為 "
            f"{raw_growth_weight:.1%}）。"
        )

    if real_return < 0:
        warnings.append(
            f"所需實質報酬率（{real_return:.2%}）為負數：即使達成名目目標金額，"
            "購買力仍會流失。"
        )

    return RiskNeedAssessment(
        level=level,
        required_rate_of_return=ror,
        required_real_return=real_return,
        required_growth_weight=raw_growth_weight,
        target_growth_weight=target_growth_weight,
        nominal_target=nominal_target,
        feasible=feasible,
        consequence_of_failure=goal.consequence_of_failure,
        warnings=tuple(warnings),
    )


@dataclass(frozen=True)
class GoalRemediation:
    achievable_rate_of_return: float
    required_annual_contribution: float
    required_years: float | None
    achievable_target: float


def _annuity_factor(rate: float, years: float) -> float:
    if abs(rate) < _NEAR_ZERO_RATE:
        return years
    return ((1 + rate) ** years - 1) / rate


def compute_remediation(
    goal: FinancialGoal,
    max_growth_weight: float,
    cme: CapitalMarketExpectations = DEFAULT_CME,
    max_years: float = 60.0,
) -> GoalRemediation:
    """"What would it take" helper for a red-light UI message."""

    achievable_rate = cme.blended_return(max_growth_weight)
    target = goal.nominal_target(cme.inflation)

    # Contribution needed to hit the goal at the achievable rate, holding
    # current_assets and years fixed.
    growth_factor = (1 + achievable_rate) ** goal.years
    remaining = target - goal.current_assets * growth_factor
    annuity_factor = _annuity_factor(achievable_rate, goal.years)
    if annuity_factor <= 0:
        # Degenerate (e.g. years effectively 0); avoid division by zero.
        required_annual_contribution = max(remaining, 0.0)
    else:
        required_annual_contribution = remaining / annuity_factor
    required_annual_contribution = max(required_annual_contribution, 0.0)

    # Years-to-goal at current contribution and achievable rate, via bisection.
    def fv_at_years(years: float) -> float:
        return future_value(achievable_rate, years, goal.current_assets, goal.annual_contribution)

    required_years: float | None
    if fv_at_years(max_years) < target:
        required_years = None
    elif fv_at_years(0.0) >= target:
        required_years = 0.0
    else:
        lo, hi = 0.0, max_years
        for _ in range(_BISECTION_ITERATIONS):
            mid = (lo + hi) / 2
            if fv_at_years(mid) < target:
                lo = mid
            else:
                hi = mid
        required_years = (lo + hi) / 2

    stated_years = required_years if required_years is not None else goal.years
    achievable_target = future_value(
        achievable_rate, stated_years, goal.current_assets, goal.annual_contribution
    )

    return GoalRemediation(
        achievable_rate_of_return=achievable_rate,
        required_annual_contribution=required_annual_contribution,
        required_years=required_years,
        achievable_target=achievable_target,
    )
