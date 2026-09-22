export type ConsequenceOfFailure = "acceptable" | "unacceptable" | "unknown";

export interface GoalInput {
  target_amount: number;
  years: number;
  current_assets: number;
  annual_contribution: number;
  consequence_of_failure: ConsequenceOfFailure;
  target_in_todays_money: boolean;
}

export interface AbilityInput {
  time_horizon_years: number;
  annual_liquidity_need_pct: number;
  has_external_resources: boolean;
}

export interface BehavioralProfileInput {
  risk_tolerance: number;
  risk_preference: number;
  financial_knowledge: number;
  investing_experience: number;
  risk_perception: number;
  risk_composure: number;
  self_control: number;
  optimism: number;
}

export interface AssessmentRequest {
  goal: GoalInput;
  ability: AbilityInput;
  behavioral: BehavioralProfileInput;
}

export type RiskLevelLabel = "Low" | "Moderate" | "High";
export type TrafficLightValue = "red" | "yellow" | "green";
export type AlertSeverity = "info" | "warning";

export interface RiskNeedOut {
  level: RiskLevelLabel;
  required_rate_of_return: number;
  required_real_return: number;
  target_growth_weight: number;
  nominal_target: number;
  feasible: boolean;
  warnings: string[];
}

export interface RiskAbilityOut {
  level: RiskLevelLabel;
  growth_weight_ceiling: number;
  has_liquidity_constraint: boolean;
  reasons: string[];
}

export interface BehavioralOut {
  level: RiskLevelLabel;
  score: number;
  growth_weight_ceiling: number;
  reasons: string[];
}

export interface AlertOut {
  code: string;
  severity: AlertSeverity;
  message: string;
}

export interface CalibrationOut {
  light: TrafficLightValue;
  recommended_growth_weight: number;
  reasons: string[];
  nudge_toward_higher_risk: boolean;
}

export interface AssessmentResponse {
  id: number | null;
  need: RiskNeedOut;
  ability: RiskAbilityOut;
  behavioral: BehavioralOut;
  calibration: CalibrationOut;
  alerts: AlertOut[];
}
