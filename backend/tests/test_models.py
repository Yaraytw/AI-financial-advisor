import pytest

from app.scoring.models import (
    BEHAVIORAL_ATTRIBUTES,
    CFA_ATTRIBUTES,
    DEFAULT_CME,
    GROWTH_WEIGHT_CEILINGS,
    PSYCHOLOGICAL_ATTRIBUTES,
    BehavioralProfile,
    CapitalMarketExpectations,
    ConsequenceOfFailure,
    FinancialGoal,
    RiskAbilityInputs,
    RiskLevel,
    TrafficLight,
)


def make_profile(**overrides):
    base = dict(
        risk_tolerance=3,
        risk_preference=3,
        financial_knowledge=3,
        investing_experience=3,
        risk_perception=3,
        risk_composure=3,
        self_control=3,
        optimism=3,
    )
    base.update(overrides)
    return BehavioralProfile(**base)


class TestRiskLevel:
    def test_ordering(self):
        assert RiskLevel.LOW < RiskLevel.MODERATE < RiskLevel.HIGH
        assert RiskLevel.HIGH > RiskLevel.LOW
        assert RiskLevel.MODERATE >= RiskLevel.MODERATE

    def test_labels(self):
        assert RiskLevel.LOW.label == "Low"
        assert RiskLevel.MODERATE.label == "Moderate"
        assert RiskLevel.HIGH.label == "High"


def test_traffic_light_members():
    assert {m.name for m in TrafficLight} == {"RED", "YELLOW", "GREEN"}


def test_consequence_of_failure_members():
    assert {m.name for m in ConsequenceOfFailure} == {
        "ACCEPTABLE",
        "UNACCEPTABLE",
        "UNKNOWN",
    }


def test_growth_weight_ceilings():
    assert GROWTH_WEIGHT_CEILINGS == {
        RiskLevel.LOW: 0.30,
        RiskLevel.MODERATE: 0.70,
        RiskLevel.HIGH: 1.00,
    }


class TestCapitalMarketExpectations:
    def test_defaults(self):
        cme = CapitalMarketExpectations()
        assert cme.growth_return == 0.06
        assert cme.defensive_return == 0.02
        assert cme.inflation == 0.018

    def test_default_instance_matches(self):
        assert DEFAULT_CME.growth_return == 0.06
        assert DEFAULT_CME.defensive_return == 0.02
        assert DEFAULT_CME.inflation == 0.018

    def test_rejects_growth_not_greater_than_defensive(self):
        with pytest.raises(ValueError):
            CapitalMarketExpectations(growth_return=0.02, defensive_return=0.02)
        with pytest.raises(ValueError):
            CapitalMarketExpectations(growth_return=0.01, defensive_return=0.02)

    def test_blended_return(self):
        cme = CapitalMarketExpectations(growth_return=0.08, defensive_return=0.02)
        assert cme.blended_return(1.0) == pytest.approx(0.08)
        assert cme.blended_return(0.0) == pytest.approx(0.02)
        assert cme.blended_return(0.5) == pytest.approx(0.05)

    def test_frozen(self):
        cme = CapitalMarketExpectations()
        with pytest.raises(Exception):
            cme.growth_return = 0.10  # type: ignore[misc]


class TestFinancialGoal:
    def test_valid(self):
        g = FinancialGoal(target_amount=100.0, years=5.0)
        assert g.current_assets == 0.0
        assert g.annual_contribution == 0.0
        assert g.consequence_of_failure == ConsequenceOfFailure.UNKNOWN
        assert g.target_in_todays_money is True

    @pytest.mark.parametrize(
        "kwargs",
        [
            dict(target_amount=0, years=5),
            dict(target_amount=-1, years=5),
            dict(target_amount=100, years=0),
            dict(target_amount=100, years=-1),
            dict(target_amount=100, years=5, current_assets=-1),
            dict(target_amount=100, years=5, annual_contribution=-1),
        ],
    )
    def test_invalid(self, kwargs):
        with pytest.raises(ValueError):
            FinancialGoal(**kwargs)

    def test_nominal_target_in_todays_money(self):
        g = FinancialGoal(target_amount=100.0, years=10.0, target_in_todays_money=True)
        assert g.nominal_target(0.02) == pytest.approx(100.0 * 1.02**10)

    def test_nominal_target_already_nominal(self):
        g = FinancialGoal(target_amount=100.0, years=10.0, target_in_todays_money=False)
        assert g.nominal_target(0.02) == 100.0


class TestRiskAbilityInputs:
    def test_valid(self):
        inp = RiskAbilityInputs(time_horizon_years=10)
        assert inp.annual_liquidity_need_pct == 0.0
        assert inp.has_external_resources is False

    @pytest.mark.parametrize(
        "kwargs",
        [
            dict(time_horizon_years=0),
            dict(time_horizon_years=-1),
            dict(time_horizon_years=5, annual_liquidity_need_pct=-0.01),
            dict(time_horizon_years=5, annual_liquidity_need_pct=1.01),
        ],
    )
    def test_invalid(self, kwargs):
        with pytest.raises(ValueError):
            RiskAbilityInputs(**kwargs)

    def test_boundary_liquidity_pct(self):
        RiskAbilityInputs(time_horizon_years=5, annual_liquidity_need_pct=0.0)
        RiskAbilityInputs(time_horizon_years=5, annual_liquidity_need_pct=1.0)


class TestAttributeTuples:
    def test_cfa_attributes_count(self):
        assert len(CFA_ATTRIBUTES) == 6

    def test_psychological_attributes_count(self):
        assert len(PSYCHOLOGICAL_ATTRIBUTES) == 2

    def test_behavioral_is_concatenation(self):
        assert BEHAVIORAL_ATTRIBUTES == CFA_ATTRIBUTES + PSYCHOLOGICAL_ATTRIBUTES
        assert len(BEHAVIORAL_ATTRIBUTES) == 8


class TestBehavioralProfile:
    def test_valid(self):
        p = make_profile()
        assert p.risk_tolerance == 3

    @pytest.mark.parametrize("name", BEHAVIORAL_ATTRIBUTES)
    def test_rejects_out_of_range_low(self, name):
        with pytest.raises(ValueError):
            make_profile(**{name: 0})

    @pytest.mark.parametrize("name", BEHAVIORAL_ATTRIBUTES)
    def test_rejects_out_of_range_high(self, name):
        with pytest.raises(ValueError):
            make_profile(**{name: 6})

    @pytest.mark.parametrize("name", BEHAVIORAL_ATTRIBUTES)
    def test_boundary_values_accepted(self, name):
        make_profile(**{name: 1})
        make_profile(**{name: 5})

    @pytest.mark.parametrize("name", BEHAVIORAL_ATTRIBUTES)
    def test_rejects_bool(self, name):
        with pytest.raises(TypeError):
            make_profile(**{name: True})

    @pytest.mark.parametrize("name", BEHAVIORAL_ATTRIBUTES)
    def test_rejects_non_int(self, name):
        with pytest.raises(TypeError):
            make_profile(**{name: 3.5})
        with pytest.raises(TypeError):
            make_profile(**{name: "3"})

    def test_cfa_scores(self):
        p = make_profile(
            risk_tolerance=1,
            risk_preference=2,
            financial_knowledge=3,
            investing_experience=4,
            risk_perception=5,
            risk_composure=1,
            self_control=5,
            optimism=5,
        )
        assert p.cfa_scores == {
            "risk_tolerance": 1,
            "risk_preference": 2,
            "financial_knowledge": 3,
            "investing_experience": 4,
            "risk_perception": 5,
            "risk_composure": 1,
        }
        assert "self_control" not in p.cfa_scores
        assert "optimism" not in p.cfa_scores

    def test_as_dict(self):
        p = make_profile()
        d = p.as_dict()
        assert set(d.keys()) == set(BEHAVIORAL_ATTRIBUTES)
        assert d["self_control"] == 3
        assert d["optimism"] == 3

    def test_frozen(self):
        p = make_profile()
        with pytest.raises(Exception):
            p.risk_tolerance = 5  # type: ignore[misc]
