import pytest

from app.scoring.behavioral import (
    MAX_BEHAVIORAL_SCORE,
    MIN_BEHAVIORAL_SCORE,
    assess_behavioral_tolerance,
    behavioral_score,
    classify_behavioral_tolerance,
)
from app.scoring.models import GROWTH_WEIGHT_CEILINGS, BehavioralProfile, RiskLevel


def make_profile(rt, rp, fk, ie, rper, rc, sc=3, op=3):
    return BehavioralProfile(
        risk_tolerance=rt,
        risk_preference=rp,
        financial_knowledge=fk,
        investing_experience=ie,
        risk_perception=rper,
        risk_composure=rc,
        self_control=sc,
        optimism=op,
    )


class TestBehavioralScore:
    def test_sums_only_cfa_attributes(self):
        p = make_profile(1, 1, 1, 1, 1, 1, sc=5, op=5)
        assert behavioral_score(p) == 6

    def test_max_score(self):
        p = make_profile(5, 5, 5, 5, 5, 5, sc=1, op=1)
        assert behavioral_score(p) == 30


class TestClassifyBehavioralTolerance:
    def test_min_is_low(self):
        assert classify_behavioral_tolerance(MIN_BEHAVIORAL_SCORE) == RiskLevel.LOW

    def test_13_is_low_boundary(self):
        assert classify_behavioral_tolerance(13) == RiskLevel.LOW

    def test_14_is_moderate_boundary(self):
        assert classify_behavioral_tolerance(14) == RiskLevel.MODERATE

    def test_22_is_moderate_boundary(self):
        assert classify_behavioral_tolerance(22) == RiskLevel.MODERATE

    def test_23_is_high_boundary(self):
        assert classify_behavioral_tolerance(23) == RiskLevel.HIGH

    def test_max_is_high(self):
        assert classify_behavioral_tolerance(MAX_BEHAVIORAL_SCORE) == RiskLevel.HIGH

    def test_rejects_below_min(self):
        with pytest.raises(ValueError):
            classify_behavioral_tolerance(MIN_BEHAVIORAL_SCORE - 1)

    def test_rejects_above_max(self):
        with pytest.raises(ValueError):
            classify_behavioral_tolerance(MAX_BEHAVIORAL_SCORE + 1)


class TestAssessBehavioralTolerance:
    def test_basic_assessment(self):
        p = make_profile(3, 3, 3, 3, 3, 3)
        a = assess_behavioral_tolerance(p)
        assert a.score == 18
        assert a.level == RiskLevel.MODERATE
        assert a.growth_weight_ceiling == GROWTH_WEIGHT_CEILINGS[RiskLevel.MODERATE]
        assert a.profile is p
        assert any("18" in r and "Moderate" in r for r in a.reasons)

    def test_risk_composure_low_adds_reason(self):
        p = make_profile(3, 3, 3, 3, 3, 2)
        a = assess_behavioral_tolerance(p)
        assert any("曾經賣出" in r for r in a.reasons)

    def test_risk_composure_at_boundary_3_no_reason(self):
        p = make_profile(3, 3, 3, 3, 3, 3)
        a = assess_behavioral_tolerance(p)
        assert not any("曾經賣出" in r for r in a.reasons)

    def test_experience_knowledge_mismatch_adds_reason(self):
        p = make_profile(3, 3, 4, 2, 3, 3)
        a = assess_behavioral_tolerance(p)
        assert any("財務知識程度高於" in r for r in a.reasons)

    def test_experience_knowledge_mismatch_requires_both_conditions(self):
        # Low experience but knowledge below threshold: no mismatch reason.
        p = make_profile(3, 3, 3, 2, 3, 3)
        a = assess_behavioral_tolerance(p)
        assert not any("財務知識程度高於" in r for r in a.reasons)
        # High knowledge but experience above threshold: no mismatch reason.
        p2 = make_profile(3, 3, 4, 3, 3, 3)
        a2 = assess_behavioral_tolerance(p2)
        assert not any("財務知識程度高於" in r for r in a2.reasons)

    def test_both_extra_reasons_can_fire_together(self):
        p = make_profile(3, 3, 4, 2, 3, 1)
        a = assess_behavioral_tolerance(p)
        assert any("曾經賣出" in r for r in a.reasons)
        assert any("財務知識程度高於" in r for r in a.reasons)
        assert len(a.reasons) == 3
