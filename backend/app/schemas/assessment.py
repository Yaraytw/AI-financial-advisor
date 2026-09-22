"""Pydantic request/response schemas for the assessments API.

Field names and shapes match frontend/src/types.ts exactly.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ConsequenceOfFailureIn(str, Enum):
    ACCEPTABLE = "acceptable"
    UNACCEPTABLE = "unacceptable"
    UNKNOWN = "unknown"


class GoalIn(BaseModel):
    target_amount: float = Field(gt=0)
    years: float = Field(gt=0, le=80)
    current_assets: float = Field(ge=0, default=0.0)
    annual_contribution: float = Field(ge=0, default=0.0)
    consequence_of_failure: ConsequenceOfFailureIn = ConsequenceOfFailureIn.UNKNOWN
    target_in_todays_money: bool = True


class AbilityIn(BaseModel):
    time_horizon_years: float = Field(gt=0, le=80)
    annual_liquidity_need_pct: float = Field(ge=0, le=1, default=0.0)
    has_external_resources: bool = False


class BehavioralProfileIn(BaseModel):
    risk_tolerance: int = Field(ge=1, le=5)
    risk_preference: int = Field(ge=1, le=5)
    financial_knowledge: int = Field(ge=1, le=5)
    investing_experience: int = Field(ge=1, le=5)
    risk_perception: int = Field(ge=1, le=5)
    risk_composure: int = Field(ge=1, le=5)
    self_control: int = Field(ge=1, le=5)
    optimism: int = Field(ge=1, le=5)


class AssessmentRequest(BaseModel):
    goal: GoalIn
    ability: AbilityIn
    behavioral: BehavioralProfileIn

    @model_validator(mode="after")
    def _check_horizon_consistency(self) -> "AssessmentRequest":
        if abs(self.ability.time_horizon_years - self.goal.years) > 40:
            raise ValueError(
                "ability.time_horizon_years and goal.years differ by more than "
                "40 years; check for an input mistake."
            )
        return self


class RiskNeedOut(BaseModel):
    level: str
    required_rate_of_return: float
    required_real_return: float
    target_growth_weight: float
    nominal_target: float
    feasible: bool
    warnings: list[str]


class RiskAbilityOut(BaseModel):
    level: str
    growth_weight_ceiling: float
    has_liquidity_constraint: bool
    reasons: list[str]


class BehavioralOut(BaseModel):
    level: str
    score: int
    growth_weight_ceiling: float
    reasons: list[str]


class AlertOut(BaseModel):
    code: str
    severity: str
    message: str


class CalibrationOut(BaseModel):
    light: str
    recommended_growth_weight: float
    reasons: list[str]
    nudge_toward_higher_risk: bool


class AssessmentResponse(BaseModel):
    id: int | None = None
    need: RiskNeedOut
    ability: RiskAbilityOut
    behavioral: BehavioralOut
    calibration: CalibrationOut
    alerts: list[AlertOut]
