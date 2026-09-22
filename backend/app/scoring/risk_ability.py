"""Module 2: Risk-Taking Ability — objective capacity to bear risk."""

from __future__ import annotations

from dataclasses import dataclass

from app.scoring.models import GROWTH_WEIGHT_CEILINGS, RiskAbilityInputs, RiskLevel

LIQUIDITY_CONSTRAINT_THRESHOLD = 0.05
SHORT_HORIZON_YEARS = 5.0
LONG_HORIZON_YEARS = 10.0


@dataclass(frozen=True)
class RiskAbilityAssessment:
    level: RiskLevel
    growth_weight_ceiling: float
    has_liquidity_constraint: bool
    reasons: tuple[str, ...]


def assess_risk_ability(inputs: RiskAbilityInputs) -> RiskAbilityAssessment:
    has_liquidity_constraint = (
        inputs.annual_liquidity_need_pct >= LIQUIDITY_CONSTRAINT_THRESHOLD
        and not inputs.has_external_resources
    )
    short_horizon = inputs.time_horizon_years <= SHORT_HORIZON_YEARS

    reasons: list[str] = []

    if short_horizon or has_liquidity_constraint:
        level = RiskLevel.LOW
        if short_horizon:
            reasons.append(
                f"投資期限 {inputs.time_horizon_years:g} 年，落在短期門檻 "
                f"{SHORT_HORIZON_YEARS:g} 年以下（或等於）。"
            )
        if has_liquidity_constraint:
            reasons.append(
                f"每年流動性需求（{inputs.annual_liquidity_need_pct:.1%}）達到"
                f"或超過 {LIQUIDITY_CONSTRAINT_THRESHOLD:.0%} 的硬性門檻，"
                "且沒有足夠的外部資源可以支應。"
            )
    elif (
        inputs.time_horizon_years >= LONG_HORIZON_YEARS
        and inputs.annual_liquidity_need_pct < LIQUIDITY_CONSTRAINT_THRESHOLD
        and inputs.has_external_resources
    ):
        level = RiskLevel.HIGH
        reasons.append(
            f"投資期限 {inputs.time_horizon_years:g} 年，達到長期門檻 "
            f"{LONG_HORIZON_YEARS:g} 年以上，流動性需求低於硬性門檻，"
            "且有足夠的外部資源支應。"
        )
    else:
        level = RiskLevel.MODERATE
        reasons.append(
            "既未觸發低能力條件（短期限，或流動性需求達門檻且無外部資源），"
            "也未同時滿足所有高能力條件（長期限、低流動性需求、有外部資源）。"
        )

    return RiskAbilityAssessment(
        level=level,
        growth_weight_ceiling=GROWTH_WEIGHT_CEILINGS[level],
        has_liquidity_constraint=has_liquidity_constraint,
        reasons=tuple(reasons),
    )
