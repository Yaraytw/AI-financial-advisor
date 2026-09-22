"""Step C: the traffic-light calibration matrix.

Combines Risk Need, Risk-Taking Ability, and Behavioral Tolerance into a
single recommended growth-asset weight plus a traffic-light signal.

Evaluated in strict order; each rule is a hard "return here if triggered"
and the first match wins.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.scoring.behavioral import BehavioralAssessment
from app.scoring.models import GROWTH_WEIGHT_CEILINGS, ConsequenceOfFailure, TrafficLight
from app.scoring.risk_ability import RiskAbilityAssessment
from app.scoring.risk_need import RiskNeedAssessment


@dataclass(frozen=True)
class CalibrationResult:
    light: TrafficLight
    recommended_growth_weight: float
    reasons: tuple[str, ...]
    nudge_toward_higher_risk: bool = False


def calibrate(
    need: RiskNeedAssessment,
    ability: RiskAbilityAssessment,
    behavioral: BehavioralAssessment,
) -> CalibrationResult:
    # 1. RED — infeasible goal: unreachable even at 100% growth assets.
    if not need.feasible:
        reasons = (
            "此目標在任何資產配置下都無法達成，即使 100% 配置成長型資產"
            f"（所需報酬率 {need.required_rate_of_return:.2%}）。",
            *need.warnings,
        )
        return CalibrationResult(
            light=TrafficLight.RED,
            recommended_growth_weight=ability.growth_weight_ceiling,
            reasons=reasons,
        )

    # 2. RED — need exceeds ability: the goal demands more risk than the
    # investor's objective capacity allows.
    if need.level > ability.level:
        reasons = (
            f"風險需求（{need.level.label}）超過風險承受能力"
            f"（{ability.level.label}）。",
            *ability.reasons,
        )
        return CalibrationResult(
            light=TrafficLight.RED,
            recommended_growth_weight=ability.growth_weight_ceiling,
            reasons=reasons,
        )

    # Past this point need.level <= ability.level is guaranteed, so
    # ability.growth_weight_ceiling is always a safe upper bound.

    # 3. YELLOW — behavioral tolerance is the binding constraint.
    if behavioral.level < need.level or behavioral.level < ability.level:
        if need.consequence_of_failure == ConsequenceOfFailure.UNACCEPTABLE:
            recommended = min(need.target_growth_weight, ability.growth_weight_ceiling)
            reasons = (
                f"行為損失容忍度（{behavioral.level.label}）低於目標所需，"
                "或低於投資人的承受能力，但無法達成此目標是不可接受的。"
                "因此仍建議採用所需的配置，並搭配加強的投資人教育，"
                "而非退回到投資人感到舒適的配置。",
                *behavioral.reasons,
            )
            return CalibrationResult(
                light=TrafficLight.YELLOW,
                recommended_growth_weight=recommended,
                reasons=reasons,
                nudge_toward_higher_risk=True,
            )

        # ACCEPTABLE or UNKNOWN: UNKNOWN treated as ACCEPTABLE (conservative
        # default when the investor's failure tolerance hasn't been
        # established) — ticket #5, approved.
        recommended = min(
            GROWTH_WEIGHT_CEILINGS[behavioral.level], ability.growth_weight_ceiling
        )
        reasons = (
            f"行為損失容忍度（{behavioral.level.label}）低於目標所需，"
            "或低於投資人的承受能力。為避免投資人在市場下跌時恐慌性賣出，"
            "退回到投資人感到舒適的配置。",
            *behavioral.reasons,
        )
        return CalibrationResult(
            light=TrafficLight.YELLOW,
            recommended_growth_weight=recommended,
            reasons=reasons,
            nudge_toward_higher_risk=False,
        )

    # 4. GREEN — all three aligned, or investor is more tolerant than
    # required (overconfidence, which is ignored rather than acted on).
    recommended = min(need.target_growth_weight, ability.growth_weight_ceiling)
    reasons_list: list[str] = []
    if behavioral.level > max(need.level, ability.level):
        reasons_list.append(
            f"行為損失容忍度（{behavioral.level.label}）同時超過風險需求與"
            "風險承受能力；多出來的容忍度會被忽略，不會用來提高風險配置。"
        )
    else:
        reasons_list.append(
            "風險需求、風險承受能力與行為損失容忍度三者一致。"
        )

    return CalibrationResult(
        light=TrafficLight.GREEN,
        recommended_growth_weight=recommended,
        reasons=tuple(reasons_list),
        nudge_toward_higher_risk=False,
    )
