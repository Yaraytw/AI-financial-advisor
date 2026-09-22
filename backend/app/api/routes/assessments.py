"""POST /assessments and GET /assessments/{id}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.assessment import Assessment
from app.schemas.assessment import (
    AlertOut,
    AssessmentRequest,
    AssessmentResponse,
    BehavioralOut,
    CalibrationOut,
    RiskAbilityOut,
    RiskNeedOut,
)
from app.scoring.behavioral import assess_behavioral_tolerance
from app.scoring.decision import calibrate
from app.scoring.alerts import generate_alerts
from app.scoring.models import (
    BehavioralProfile,
    ConsequenceOfFailure,
    FinancialGoal,
    RiskAbilityInputs,
)
from app.scoring.risk_ability import assess_risk_ability
from app.scoring.risk_need import assess_risk_need

router = APIRouter(prefix="/assessments", tags=["assessments"])

_CONSEQUENCE_MAP = {
    "acceptable": ConsequenceOfFailure.ACCEPTABLE,
    "unacceptable": ConsequenceOfFailure.UNACCEPTABLE,
    "unknown": ConsequenceOfFailure.UNKNOWN,
}


def _run_pipeline(payload: AssessmentRequest) -> AssessmentResponse:
    goal = FinancialGoal(
        target_amount=payload.goal.target_amount,
        years=payload.goal.years,
        current_assets=payload.goal.current_assets,
        annual_contribution=payload.goal.annual_contribution,
        consequence_of_failure=_CONSEQUENCE_MAP[payload.goal.consequence_of_failure.value],
        target_in_todays_money=payload.goal.target_in_todays_money,
    )
    ability_inputs = RiskAbilityInputs(
        time_horizon_years=payload.ability.time_horizon_years,
        annual_liquidity_need_pct=payload.ability.annual_liquidity_need_pct,
        has_external_resources=payload.ability.has_external_resources,
    )
    behavioral_profile = BehavioralProfile(
        risk_tolerance=payload.behavioral.risk_tolerance,
        risk_preference=payload.behavioral.risk_preference,
        financial_knowledge=payload.behavioral.financial_knowledge,
        investing_experience=payload.behavioral.investing_experience,
        risk_perception=payload.behavioral.risk_perception,
        risk_composure=payload.behavioral.risk_composure,
        self_control=payload.behavioral.self_control,
        optimism=payload.behavioral.optimism,
    )

    need = assess_risk_need(goal)
    ability = assess_risk_ability(ability_inputs)
    behavioral = assess_behavioral_tolerance(behavioral_profile)
    calibration = calibrate(need, ability, behavioral)
    alerts = generate_alerts(behavioral_profile)

    return AssessmentResponse(
        need=RiskNeedOut(
            level=need.level.label,
            required_rate_of_return=need.required_rate_of_return,
            required_real_return=need.required_real_return,
            target_growth_weight=need.target_growth_weight,
            nominal_target=need.nominal_target,
            feasible=need.feasible,
            warnings=list(need.warnings),
        ),
        ability=RiskAbilityOut(
            level=ability.level.label,
            growth_weight_ceiling=ability.growth_weight_ceiling,
            has_liquidity_constraint=ability.has_liquidity_constraint,
            reasons=list(ability.reasons),
        ),
        behavioral=BehavioralOut(
            level=behavioral.level.label,
            score=behavioral.score,
            growth_weight_ceiling=behavioral.growth_weight_ceiling,
            reasons=list(behavioral.reasons),
        ),
        calibration=CalibrationOut(
            light=calibration.light.value.lower(),
            recommended_growth_weight=calibration.recommended_growth_weight,
            reasons=list(calibration.reasons),
            nudge_toward_higher_risk=calibration.nudge_toward_higher_risk,
        ),
        alerts=[
            AlertOut(code=a.code, severity=a.severity.value.lower(), message=a.message)
            for a in alerts
        ],
    )


@router.post("", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: AssessmentRequest, db: Session = Depends(get_db)) -> AssessmentResponse:
    response = _run_pipeline(payload)

    record = Assessment(
        goal_input=payload.goal.model_dump(mode="json"),
        ability_input=payload.ability.model_dump(mode="json"),
        behavioral_input=payload.behavioral.model_dump(mode="json"),
        need_level=response.need.level,
        ability_level=response.ability.level,
        behavioral_level=response.behavioral.level,
        behavioral_score=response.behavioral.score,
        traffic_light=response.calibration.light,
        recommended_growth_weight=response.calibration.recommended_growth_weight,
        result_output=response.model_dump(mode="json", exclude={"id"}),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    response.id = record.id
    return response


@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(assessment_id: int, db: Session = Depends(get_db)) -> AssessmentResponse:
    record = db.get(Assessment, assessment_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    return AssessmentResponse(id=record.id, **record.result_output)
