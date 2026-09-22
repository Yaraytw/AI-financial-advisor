import pytest

from app.scoring.models import ConsequenceOfFailure, FinancialGoal, RiskLevel
from app.scoring.risk_need import (
    assess_risk_need,
    classify_risk_need,
    compute_remediation,
    future_value,
    required_growth_weight,
    required_rate_of_return,
)


class TestFutureValue:
    def test_lump_sum_only(self):
        assert future_value(0.05, 10, 1000, 0) == pytest.approx(1000 * 1.05**10)

    def test_annuity_only(self):
        # Ordinary annuity of 100/yr for 5 years at 5%.
        fv = future_value(0.05, 5, 0, 100)
        expected = 100 * ((1.05**5 - 1) / 0.05)
        assert fv == pytest.approx(expected)

    def test_zero_rate_is_linear(self):
        assert future_value(0.0, 10, 1000, 50) == pytest.approx(1000 + 50 * 10)

    def test_near_zero_rate_matches_zero_rate(self):
        # Should not blow up near the rate == 0 division.
        fv_zero = future_value(0.0, 10, 1000, 50)
        fv_tiny = future_value(1e-12, 10, 1000, 50)
        assert fv_tiny == pytest.approx(fv_zero, rel=1e-6)

    def test_combined(self):
        fv = future_value(0.04, 8, 5000, 200)
        expected = 5000 * 1.04**8 + 200 * ((1.04**8 - 1) / 0.04)
        assert fv == pytest.approx(expected)


class TestRequiredRateOfReturn:
    def test_already_funded_returns_bracket_floor(self):
        # Target is negligible next to current_assets: even future_value at
        # the bracket floor (-99%/yr) still clears it.
        goal = FinancialGoal(target_amount=1e-10, years=5, current_assets=1_000_000)
        rate = required_rate_of_return(goal)
        assert rate == -0.99

    def test_unreachable_returns_bracket_ceiling(self):
        goal = FinancialGoal(target_amount=1e12, years=1, current_assets=1)
        rate = required_rate_of_return(goal)
        assert rate == 5.0

    def test_solves_known_rate(self):
        # current_assets compounds at 5% for 10 years with no inflation drift
        # cancellation trick: use target_in_todays_money=False to isolate the
        # rate-solving math from inflation.
        current = 100_000.0
        rate_true = 0.05
        target = current * (1 + rate_true) ** 10
        goal = FinancialGoal(
            target_amount=target,
            years=10,
            current_assets=current,
            target_in_todays_money=False,
        )
        solved = required_rate_of_return(goal)
        assert solved == pytest.approx(rate_true, abs=1e-6)


class TestRequiredGrowthWeight:
    def test_at_defensive_return_is_zero(self):
        assert required_growth_weight(0.02) == pytest.approx(0.0)

    def test_at_growth_return_is_one(self):
        assert required_growth_weight(0.06) == pytest.approx(1.0)

    def test_midpoint(self):
        assert required_growth_weight(0.04) == pytest.approx(0.5)

    def test_not_clamped_negative(self):
        assert required_growth_weight(0.0) < 0

    def test_not_clamped_above_one(self):
        assert required_growth_weight(0.10) > 1.0


class TestClassifyRiskNeed:
    def test_low_below_030(self):
        assert classify_risk_need(0.0) == RiskLevel.LOW
        assert classify_risk_need(0.299) == RiskLevel.LOW

    def test_moderate_boundary_030_inclusive_low_side(self):
        # 0.30 itself is the moderate lower edge (not < 0.30).
        assert classify_risk_need(0.30) == RiskLevel.MODERATE

    def test_moderate_upper_boundary_070_inclusive(self):
        assert classify_risk_need(0.70) == RiskLevel.MODERATE

    def test_high_above_070(self):
        assert classify_risk_need(0.7001) == RiskLevel.HIGH
        assert classify_risk_need(1.0) == RiskLevel.HIGH

    def test_clamps_out_of_range_inputs(self):
        assert classify_risk_need(-0.5) == RiskLevel.LOW
        assert classify_risk_need(1.5) == RiskLevel.HIGH


class TestAssessRiskNeed:
    def test_low_need(self):
        # Confirmed via scratch script: gw ~ 0.194, Low, feasible.
        goal = FinancialGoal(target_amount=110_000, years=10, current_assets=100_000)
        a = assess_risk_need(goal)
        assert a.level == RiskLevel.LOW
        assert a.feasible is True
        assert 0.0 <= a.required_growth_weight < 0.30

    def test_moderate_need(self):
        # Confirmed: gw ~ 0.418, Moderate, feasible.
        goal = FinancialGoal(target_amount=120_000, years=10, current_assets=100_000)
        a = assess_risk_need(goal)
        assert a.level == RiskLevel.MODERATE
        assert a.feasible is True
        assert 0.30 <= a.required_growth_weight <= 0.70

    def test_high_need_feasible(self):
        # Confirmed: gw ~ 0.783, High, feasible, no thin-margin warning.
        goal = FinancialGoal(target_amount=138_000, years=10, current_assets=100_000)
        a = assess_risk_need(goal)
        assert a.level == RiskLevel.HIGH
        assert a.feasible is True
        assert 0.70 < a.required_growth_weight <= 0.90
        assert not any("緩衝空間" in w for w in a.warnings)

    def test_high_need_thin_margin_warning(self):
        # Confirmed: gw ~ 0.950, High, feasible, thin-margin warning fires.
        goal = FinancialGoal(target_amount=147_030, years=10, current_assets=100_000)
        a = assess_risk_need(goal)
        assert a.level == RiskLevel.HIGH
        assert a.feasible is True
        assert a.required_growth_weight > 0.90
        assert any("緩衝空間" in w for w in a.warnings)

    def test_infeasible_goal(self):
        # Confirmed: gw ~ 1.78, infeasible.
        goal = FinancialGoal(target_amount=200_000, years=10, current_assets=100_000)
        a = assess_risk_need(goal)
        assert a.feasible is False
        assert a.required_growth_weight > 1.0
        assert any("無法達成" in w for w in a.warnings)

    def test_negative_growth_weight_warning_only(self):
        # Confirmed: gw ~ -0.025, Low, feasible, no negative-real-return warning.
        goal = FinancialGoal(target_amount=101_000, years=10, current_assets=100_000)
        a = assess_risk_need(goal)
        assert a.required_growth_weight < 0.0
        assert a.target_growth_weight == 0.0
        assert any("僅靠防禦型資產" in w for w in a.warnings)
        assert not any("為負數" in w for w in a.warnings)

    def test_negative_growth_weight_and_negative_real_return(self):
        # Confirmed: gw ~ -0.18, real return ~ -0.51%, both warnings fire.
        goal = FinancialGoal(target_amount=95_000, years=10, current_assets=100_000)
        a = assess_risk_need(goal)
        assert a.required_growth_weight < 0.0
        assert a.required_real_return < 0.0
        assert any("僅靠防禦型資產" in w for w in a.warnings)
        assert any("為負數" in w for w in a.warnings)

    def test_target_growth_weight_is_clamped(self):
        goal = FinancialGoal(target_amount=200_000, years=10, current_assets=100_000)
        a = assess_risk_need(goal)
        assert a.required_growth_weight > 1.0
        assert a.target_growth_weight == 1.0

    def test_consequence_of_failure_passthrough(self):
        goal = FinancialGoal(
            target_amount=110_000,
            years=10,
            current_assets=100_000,
            consequence_of_failure=ConsequenceOfFailure.UNACCEPTABLE,
        )
        a = assess_risk_need(goal)
        assert a.consequence_of_failure == ConsequenceOfFailure.UNACCEPTABLE

    def test_nominal_target_reflects_inflation(self):
        goal = FinancialGoal(target_amount=100_000, years=10, current_assets=0)
        a = assess_risk_need(goal)
        assert a.nominal_target == pytest.approx(100_000 * 1.018**10)


class TestComputeRemediation:
    def test_basic_remediation_hits_target(self):
        goal = FinancialGoal(target_amount=200_000, years=10, current_assets=100_000)
        rem = compute_remediation(goal, max_growth_weight=1.0)
        assert rem.achievable_rate_of_return == pytest.approx(0.06)
        # Contribution required at the achievable rate should exactly close
        # the gap to the nominal target over the goal's stated years.
        fv = future_value(
            rem.achievable_rate_of_return,
            goal.years,
            goal.current_assets,
            rem.required_annual_contribution,
        )
        assert fv == pytest.approx(goal.nominal_target(0.018), rel=1e-6)

    def test_required_years_none_when_unreachable(self):
        goal = FinancialGoal(
            target_amount=10_000_000,
            years=10,
            current_assets=1_000,
            annual_contribution=100,
        )
        rem = compute_remediation(goal, max_growth_weight=1.0, max_years=60.0)
        assert rem.required_years is None

    def test_required_years_found_when_reachable(self):
        goal = FinancialGoal(target_amount=200_000, years=10, current_assets=100_000)
        rem = compute_remediation(goal, max_growth_weight=1.0, max_years=60.0)
        assert rem.required_years is not None
        assert 0 < rem.required_years <= 60.0
