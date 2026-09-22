import pytest

from app.scoring.models import GROWTH_WEIGHT_CEILINGS, RiskAbilityInputs, RiskLevel
from app.scoring.risk_ability import (
    LIQUIDITY_CONSTRAINT_THRESHOLD,
    LONG_HORIZON_YEARS,
    SHORT_HORIZON_YEARS,
    assess_risk_ability,
)


class TestAssessRiskAbility:
    def test_short_horizon_is_low(self):
        inp = RiskAbilityInputs(time_horizon_years=3)
        a = assess_risk_ability(inp)
        assert a.level == RiskLevel.LOW
        assert a.growth_weight_ceiling == GROWTH_WEIGHT_CEILINGS[RiskLevel.LOW]

    def test_horizon_exactly_at_short_threshold_is_low(self):
        inp = RiskAbilityInputs(time_horizon_years=SHORT_HORIZON_YEARS)
        a = assess_risk_ability(inp)
        assert a.level == RiskLevel.LOW

    def test_horizon_just_above_short_threshold_is_not_forced_low(self):
        inp = RiskAbilityInputs(time_horizon_years=SHORT_HORIZON_YEARS + 0.01)
        a = assess_risk_ability(inp)
        assert a.level != RiskLevel.LOW

    def test_binding_liquidity_need_without_external_resources_is_low(self):
        inp = RiskAbilityInputs(
            time_horizon_years=12,
            annual_liquidity_need_pct=LIQUIDITY_CONSTRAINT_THRESHOLD,
            has_external_resources=False,
        )
        a = assess_risk_ability(inp)
        assert a.level == RiskLevel.LOW
        assert a.has_liquidity_constraint is True

    def test_liquidity_need_covered_by_external_resources_not_forced_low(self):
        inp = RiskAbilityInputs(
            time_horizon_years=12,
            annual_liquidity_need_pct=0.10,
            has_external_resources=True,
        )
        a = assess_risk_ability(inp)
        assert a.level != RiskLevel.LOW
        assert a.has_liquidity_constraint is False

    def test_liquidity_need_below_threshold_not_binding(self):
        inp = RiskAbilityInputs(
            time_horizon_years=12,
            annual_liquidity_need_pct=LIQUIDITY_CONSTRAINT_THRESHOLD - 0.01,
            has_external_resources=False,
        )
        a = assess_risk_ability(inp)
        assert a.has_liquidity_constraint is False

    def test_high_ability_requires_all_three_conditions(self):
        inp = RiskAbilityInputs(
            time_horizon_years=LONG_HORIZON_YEARS,
            annual_liquidity_need_pct=0.0,
            has_external_resources=True,
        )
        a = assess_risk_ability(inp)
        assert a.level == RiskLevel.HIGH
        assert a.growth_weight_ceiling == GROWTH_WEIGHT_CEILINGS[RiskLevel.HIGH]

    def test_horizon_just_below_long_threshold_is_not_high(self):
        inp = RiskAbilityInputs(
            time_horizon_years=LONG_HORIZON_YEARS - 0.01,
            annual_liquidity_need_pct=0.0,
            has_external_resources=True,
        )
        a = assess_risk_ability(inp)
        assert a.level != RiskLevel.HIGH

    def test_high_conditions_but_missing_external_resources_is_moderate(self):
        inp = RiskAbilityInputs(
            time_horizon_years=12,
            annual_liquidity_need_pct=0.0,
            has_external_resources=False,
        )
        a = assess_risk_ability(inp)
        assert a.level == RiskLevel.MODERATE

    def test_middling_horizon_no_constraints_is_moderate(self):
        inp = RiskAbilityInputs(time_horizon_years=7)
        a = assess_risk_ability(inp)
        assert a.level == RiskLevel.MODERATE
        assert a.growth_weight_ceiling == GROWTH_WEIGHT_CEILINGS[RiskLevel.MODERATE]

    def test_low_triggers_take_priority_over_high_conditions(self):
        # Short horizon AND otherwise-high-qualifying liquidity/external
        # resources: LOW must win since it's evaluated first.
        inp = RiskAbilityInputs(
            time_horizon_years=3,
            annual_liquidity_need_pct=0.0,
            has_external_resources=True,
        )
        a = assess_risk_ability(inp)
        assert a.level == RiskLevel.LOW

    def test_reasons_populated(self):
        inp = RiskAbilityInputs(time_horizon_years=3)
        a = assess_risk_ability(inp)
        assert len(a.reasons) >= 1
        assert all(isinstance(r, str) and r for r in a.reasons)
