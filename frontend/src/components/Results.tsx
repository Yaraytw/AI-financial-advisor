import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";
import type { AssessmentResponse, RiskLevelLabel, TrafficLightValue } from "../types";
import { formatTWD, formatPercent } from "../format";

const LEVEL_TO_SCORE: Record<RiskLevelLabel, number> = {
  Low: 1,
  Moderate: 2,
  High: 3,
};

const LIGHT_CONFIG: Record<
  TrafficLightValue,
  { label: string; bg: string; border: string; text: string }
> = {
  red: { label: "紅燈：需要調整目標", bg: "#fdecec", border: "#e0453c", text: "#8a1f18" },
  yellow: { label: "黃燈：需要留意", bg: "#fff8e1", border: "#e0a90c", text: "#7a5c00" },
  green: { label: "綠燈：可以進行", bg: "#eaf7ee", border: "#2fa84f", text: "#1a5c2e" },
};

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        border: "1px solid #ddd",
        borderRadius: 8,
        padding: 16,
        background: "#fff",
      }}
    >
      <h3 style={{ marginTop: 0, marginBottom: 12 }}>{title}</h3>
      {children}
    </div>
  );
}

function ReasonList({ items }: { items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

export function Results({ result }: { result: AssessmentResponse }) {
  const { need, ability, behavioral, calibration, alerts } = result;
  const lightConfig = LIGHT_CONFIG[calibration.light];
  const defensiveWeight = 1 - calibration.recommended_growth_weight;

  const radarData = [
    {
      factor: "風險需求",
      level: need.level,
      axis: `風險需求 (${need.level})`,
      score: LEVEL_TO_SCORE[need.level],
    },
    {
      factor: "風險承受能力",
      level: ability.level,
      axis: `風險承受能力 (${ability.level})`,
      score: LEVEL_TO_SCORE[ability.level],
    },
    {
      factor: "行為容忍度",
      level: behavioral.level,
      axis: `行為容忍度 (${behavioral.level})`,
      score: LEVEL_TO_SCORE[behavioral.level],
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 900 }}>
      {/* 1. Traffic-light banner */}
      <div
        style={{
          border: `3px solid ${lightConfig.border}`,
          borderRadius: 10,
          background: lightConfig.bg,
          color: lightConfig.text,
          padding: 20,
        }}
      >
        <div style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>
          {lightConfig.label}
        </div>
        <div style={{ fontSize: 16, marginBottom: 4 }}>
          建議成長型資產配置：
          <strong>{formatPercent(calibration.recommended_growth_weight)}</strong>
          {"　"}
          防禦型資產配置：
          <strong>{formatPercent(defensiveWeight)}</strong>
        </div>
        <ReasonList items={calibration.reasons} />
        {calibration.nudge_toward_higher_risk && (
          <div
            style={{
              marginTop: 12,
              padding: 10,
              borderRadius: 6,
              background: "rgba(255,255,255,0.6)",
              fontSize: 13,
            }}
          >
            提醒：由於您將「無法達成目標」標記為不可接受，系統建議採用高於您原始風險偏好的成長型資產配置。
          </div>
        )}
      </div>

      {/* 2. Three-factor radar chart */}
      <SectionCard title="三構面風險輪廓">
        <ResponsiveContainer width="100%" height={320}>
          <RadarChart data={radarData} outerRadius="75%">
            <PolarGrid />
            <PolarAngleAxis dataKey="axis" />
            <PolarRadiusAxis angle={30} domain={[0, 3]} tickCount={4} />
            <Radar
              name="風險輪廓"
              dataKey="score"
              stroke="#2f6fed"
              fill="#2f6fed"
              fillOpacity={0.4}
            />
          </RadarChart>
        </ResponsiveContainer>
      </SectionCard>

      {/* 3. Three factor detail cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: 16,
        }}
      >
        <SectionCard title="風險需求">
          <div>等級：<strong>{need.level}</strong></div>
          <div>所需報酬率：{formatPercent(need.required_rate_of_return)}</div>
          <div>目標金額(名目)：{formatTWD(need.nominal_target)}</div>
          {!need.feasible && (
            <div
              style={{
                marginTop: 8,
                padding: 8,
                borderRadius: 6,
                background: "#fdecec",
                border: "1px solid #e0453c",
                color: "#8a1f18",
                fontWeight: 600,
              }}
            >
              目標可能無法達成
            </div>
          )}
          <ReasonList items={need.warnings} />
        </SectionCard>

        <SectionCard title="風險承受能力">
          <div>等級：<strong>{ability.level}</strong></div>
          <div>
            流動性限制：
            {ability.has_liquidity_constraint ? "是" : "否"}
          </div>
          <ReasonList items={ability.reasons} />
        </SectionCard>

        <SectionCard title="行為容忍度">
          <div>等級：<strong>{behavioral.level}</strong></div>
          <div>分數：{behavioral.score} / 30</div>
          <ReasonList items={behavioral.reasons} />
        </SectionCard>
      </div>

      {/* 4. Psychological alerts */}
      {alerts.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {alerts.map((alert, i) => {
            const isWarning = alert.severity === "warning";
            return (
              <div
                key={`${alert.code}-${i}`}
                style={{
                  padding: 12,
                  borderRadius: 6,
                  background: isWarning ? "#fff8e1" : "#e8f1fd",
                  border: `1px solid ${isWarning ? "#e0a90c" : "#3a7bd5"}`,
                  color: isWarning ? "#7a5c00" : "#1a3f7a",
                }}
              >
                {alert.message}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
