import itertools

import pytest

from app.scoring.behavioral import BehavioralAssessment
from app.scoring.decision import calibrate
from app.scoring.models import (
    GROWTH_WEIGHT_CEILINGS,
    BehavioralProfile,
    ConsequenceOfFailure,
    RiskLevel,
    TrafficLight,
)
from app.scoring.risk_ability import RiskAbilityAssessment
from app.scoring.risk_need import RiskNeedAssessment


def make_need(
    level=RiskLevel.MODERATE,
    growth_weight=0.5,
    feasible=True,
    consequence=ConsequenceOfFailure.UNKNOWN,
    ror=0.04,
):
    target_gw = min(max(growth_weight, 0.0), 1.0)
    return RiskNeedAssessment(
        level=level,
        required_rate_of_return=ror,
        required_real_return=0.02,
        required_growth_weight=growth_weight,
        target_growth_weight=target_gw,
        nominal_target=100_000.0,
        feasible=feasible,
        consequence_of_failure=consequence,
        warnings=(),
    )


def make_ability(level=RiskLevel.MODERATE):
    return RiskAbilityAssessment(
        level=level,
        growth_weight_ceiling=GROWTH_WEIGHT_CEILINGS[level],
        has_liquidity_constraint=False,
        reasons=("stub ability reason",),
    )


_STUB_PROFILE = BehavioralProfile(
    risk_tolerance=3,
    risk_preference=3,
    financial_knowledge=3,
    investing_experience=3,
    risk_perception=3,
    risk_composure=3,
    self_control=3,
    optimism=3,
)


def make_behavioral(level=RiskLevel.MODERATE):
    return BehavioralAssessment(
        level=level,
        score=18,
        growth_weight_ceiling=GROWTH_WEIGHT_CEILINGS[level],
        profile=_STUB_PROFILE,
        reasons=("stub behavioral reason",),
    )


class TestRedInfeasible:
    def test_infeasible_goal_is_red_regardless_of_levels(self):
        need = make_need(level=RiskLevel.HIGH, growth_weight=1.5, feasible=False)
        ability = make_ability(RiskLevel.HIGH)
        behavioral = make_behavioral(RiskLevel.HIGH)
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.RED
        assert result.recommended_growth_weight == ability.growth_weight_ceiling
        assert result.nudge_toward_higher_risk is False

    def test_infeasible_takes_priority_over_need_exceeds_ability(self):
        need = make_need(level=RiskLevel.HIGH, growth_weight=1.5, feasible=False)
        ability = make_ability(RiskLevel.LOW)
        behavioral = make_behavioral(RiskLevel.LOW)
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.RED
        assert result.recommended_growth_weight == ability.growth_weight_ceiling


class TestRedNeedExceedsAbility:
    def test_need_high_ability_moderate(self):
        need = make_need(level=RiskLevel.HIGH, growth_weight=0.8, feasible=True)
        ability = make_ability(RiskLevel.MODERATE)
        behavioral = make_behavioral(RiskLevel.HIGH)
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.RED
        assert result.recommended_growth_weight == ability.growth_weight_ceiling

    def test_need_moderate_ability_low(self):
        need = make_need(level=RiskLevel.MODERATE, growth_weight=0.5, feasible=True)
        ability = make_ability(RiskLevel.LOW)
        behavioral = make_behavioral(RiskLevel.MODERATE)
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.RED
        assert result.recommended_growth_weight == ability.growth_weight_ceiling

    def test_need_equal_ability_does_not_trigger_red(self):
        need = make_need(level=RiskLevel.MODERATE, growth_weight=0.5, feasible=True)
        ability = make_ability(RiskLevel.MODERATE)
        behavioral = make_behavioral(RiskLevel.MODERATE)
        result = calibrate(need, ability, behavioral)
        assert result.light != TrafficLight.RED


class TestYellowBehavioralBinding:
    def test_unacceptable_consequence_nudges_up(self):
        need = make_need(
            level=RiskLevel.HIGH,
            growth_weight=0.8,
            feasible=True,
            consequence=ConsequenceOfFailure.UNACCEPTABLE,
        )
        ability = make_ability(RiskLevel.HIGH)
        behavioral = make_behavioral(RiskLevel.LOW)
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.YELLOW
        assert result.nudge_toward_higher_risk is True
        assert result.recommended_growth_weight == pytest.approx(
            min(need.target_growth_weight, ability.growth_weight_ceiling)
        )

    def test_acceptable_consequence_falls_back(self):
        need = make_need(
            level=RiskLevel.HIGH,
            growth_weight=0.8,
            feasible=True,
            consequence=ConsequenceOfFailure.ACCEPTABLE,
        )
        ability = make_ability(RiskLevel.HIGH)
        behavioral = make_behavioral(RiskLevel.LOW)
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.YELLOW
        assert result.nudge_toward_higher_risk is False
        assert result.recommended_growth_weight == pytest.approx(
            min(GROWTH_WEIGHT_CEILINGS[RiskLevel.LOW], ability.growth_weight_ceiling)
        )

    def test_unknown_consequence_treated_as_acceptable_fallback(self):
        need = make_need(
            level=RiskLevel.HIGH,
            growth_weight=0.8,
            feasible=True,
            consequence=ConsequenceOfFailure.UNKNOWN,
        )
        ability = make_ability(RiskLevel.HIGH)
        behavioral = make_behavioral(RiskLevel.LOW)
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.YELLOW
        assert result.nudge_toward_higher_risk is False
        assert result.recommended_growth_weight == pytest.approx(
            min(GROWTH_WEIGHT_CEILINGS[RiskLevel.LOW], ability.growth_weight_ceiling)
        )

    def test_behavioral_below_ability_only_still_triggers_yellow(self):
        # need <= ability guaranteed past step 2; here behavioral < ability
        # even though behavioral == need.
        need = make_need(level=RiskLevel.LOW, growth_weight=0.1, feasible=True)
        ability = make_ability(RiskLevel.HIGH)
        behavioral = make_behavioral(RiskLevel.LOW)
        # behavioral.level (LOW) < ability.level (HIGH) -> yellow, even though
        # behavioral.level == need.level.
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.YELLOW


class TestGreen:
    def test_all_aligned(self):
        need = make_need(level=RiskLevel.MODERATE, growth_weight=0.5, feasible=True)
        ability = make_ability(RiskLevel.MODERATE)
        behavioral = make_behavioral(RiskLevel.MODERATE)
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.GREEN
        assert result.recommended_growth_weight == pytest.approx(0.5)
        assert not any("忽略" in r for r in result.reasons)

    def test_overconfidence_ignored(self):
        need = make_need(level=RiskLevel.LOW, growth_weight=0.1, feasible=True)
        ability = make_ability(RiskLevel.MODERATE)
        behavioral = make_behavioral(RiskLevel.HIGH)
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.GREEN
        assert result.recommended_growth_weight == pytest.approx(
            min(need.target_growth_weight, ability.growth_weight_ceiling)
        )
        assert any("忽略" in r for r in result.reasons)

    def test_green_recommendation_never_exceeds_ability_ceiling(self):
        need = make_need(level=RiskLevel.HIGH, growth_weight=0.95, feasible=True)
        ability = make_ability(RiskLevel.HIGH)
        behavioral = make_behavioral(RiskLevel.HIGH)
        result = calibrate(need, ability, behavioral)
        assert result.light == TrafficLight.GREEN
        assert result.recommended_growth_weight <= ability.growth_weight_ceiling


class TestInvariantNeverExceedsAbilityCeiling:
    @pytest.mark.parametrize(
        "need_level,ability_level,behavioral_level,feasible,consequence",
        list(
            itertools.product(
                [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH],
                [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH],
                [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH],
                [True, False],
                [
                    ConsequenceOfFailure.ACCEPTABLE,
                    ConsequenceOfFailure.UNACCEPTABLE,
                    ConsequenceOfFailure.UNKNOWN,
                ],
            )
        ),
    )
    def test_invariant_holds_across_all_combinations(
        self, need_level, ability_level, behavioral_level, feasible, consequence
    ):
        need = make_need(
            level=need_level,
            growth_weight=GROWTH_WEIGHT_CEILINGS[need_level],
            feasible=feasible,
            consequence=consequence,
        )
        ability = make_ability(ability_level)
        behavioral = make_behavioral(behavioral_level)
        result = calibrate(need, ability, behavioral)
        assert result.recommended_growth_weight <= ability.growth_weight_ceiling + 1e-9
