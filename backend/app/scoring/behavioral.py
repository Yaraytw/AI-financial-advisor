"""Module 3: Behavioral Loss Tolerance — the CFA six-attribute score."""

from __future__ import annotations

from dataclasses import dataclass

from app.scoring.models import (
    CFA_ATTRIBUTES,
    GROWTH_WEIGHT_CEILINGS,
    BehavioralProfile,
    RiskLevel,
)

MIN_BEHAVIORAL_SCORE = 6
MAX_BEHAVIORAL_SCORE = 30


def behavioral_score(profile: BehavioralProfile) -> int:
    return sum(getattr(profile, name) for name in CFA_ATTRIBUTES)


def classify_behavioral_tolerance(score: int) -> RiskLevel:
    if not (MIN_BEHAVIORAL_SCORE <= score <= MAX_BEHAVIORAL_SCORE):
        raise ValueError(
            f"score must be within [{MIN_BEHAVIORAL_SCORE}, {MAX_BEHAVIORAL_SCORE}] "
            f"(got {score!r})"
        )
    if score <= 13:
        return RiskLevel.LOW
    if score <= 22:
        return RiskLevel.MODERATE
    return RiskLevel.HIGH


@dataclass(frozen=True)
class BehavioralAssessment:
    level: RiskLevel
    score: int
    growth_weight_ceiling: float
    profile: BehavioralProfile
    reasons: tuple[str, ...]


def assess_behavioral_tolerance(profile: BehavioralProfile) -> BehavioralAssessment:
    score = behavioral_score(profile)
    level = classify_behavioral_tolerance(score)

    reasons: list[str] = [
        f"CFA 行為分數為 {score}（滿分 {MAX_BEHAVIORAL_SCORE}），落在"
        f"「{level.label}」區間。"
    ]

    if profile.risk_composure <= 2:
        reasons.append(
            "投資人過去在虧損時曾經賣出（risk_composure <= 2），這是最強的"
            "實際損失容忍度偏低證據。"
        )

    if profile.investing_experience <= 2 and profile.financial_knowledge >= 4:
        reasons.append(
            "自評財務知識程度高於實際投資經驗，尚未真正經歷過大幅虧損"
            "（investing_experience <= 2, financial_knowledge >= 4）。"
        )

    return BehavioralAssessment(
        level=level,
        score=score,
        growth_weight_ceiling=GROWTH_WEIGHT_CEILINGS[level],
        profile=profile,
        reasons=tuple(reasons),
    )
