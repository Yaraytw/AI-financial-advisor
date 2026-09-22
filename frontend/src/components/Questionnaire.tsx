import { useState } from "react";
import type {
  AssessmentRequest,
  AssessmentResponse,
  ConsequenceOfFailure,
} from "../types";
import { api, ApiError } from "../api/client";

type BehavioralKey =
  | "risk_tolerance"
  | "risk_preference"
  | "financial_knowledge"
  | "investing_experience"
  | "risk_perception"
  | "risk_composure"
  | "self_control"
  | "optimism";

interface BehavioralQuestion {
  key: BehavioralKey;
  label: string;
  lowLabel: string;
  midLabel?: string;
  highLabel: string;
}

const BEHAVIORAL_QUESTIONS: BehavioralQuestion[] = [
  {
    key: "risk_tolerance",
    label: "你能接受的財務不確定性上限？",
    lowLabel: "1 = 完全不能接受",
    highLabel: "5 = 完全可以接受",
  },
  {
    key: "risk_preference",
    label: "在安全與報酬之間，你偏好？",
    lowLabel: "1 = 絕對安全優先",
    highLabel: "5 = 絕對報酬優先",
  },
  {
    key: "financial_knowledge",
    label: "你對投資與風險報酬的理解程度？",
    lowLabel: "1 = 完全不懂",
    highLabel: "5 = 非常熟悉",
  },
  {
    key: "investing_experience",
    label: "你實際經歷過市場大幅下跌的經驗？",
    lowLabel: "1 = 完全沒有",
    highLabel: "5 = 經歷過多次",
  },
  {
    key: "risk_perception",
    label: "你認為目前市場風險高不高？",
    lowLabel: "1 = 非常危險",
    highLabel: "5 = 非常安全",
  },
  {
    key: "risk_composure",
    label: "過去投資虧損時，你的實際反應？",
    lowLabel: "1 = 恐慌賣出",
    midLabel: "3 = 什麼都沒做",
    highLabel: "5 = 逢低加碼",
  },
  {
    key: "self_control",
    label: "你能延遲享樂、堅持長期計畫的程度？",
    lowLabel: "1 = 容易衝動消費",
    highLabel: "5 = 非常能延遲享樂",
  },
  {
    key: "optimism",
    label: "你對未來投資報酬的樂觀程度？",
    lowLabel: "1 = 悲觀",
    midLabel: "3 = 適度謹慎",
    highLabel: "5 = 非常樂觀／對成本不敏感",
  },
];

interface FormState {
  targetAmount: string;
  years: string;
  currentAssets: string;
  annualContribution: string;
  consequenceOfFailure: ConsequenceOfFailure;
  targetInTodaysMoney: boolean;
  timeHorizonYears: string;
  annualLiquidityNeedPct: string;
  hasExternalResources: boolean;
  behavioral: Record<BehavioralKey, number>;
}

const initialState: FormState = {
  targetAmount: "",
  years: "",
  currentAssets: "0",
  annualContribution: "0",
  consequenceOfFailure: "unknown",
  targetInTodaysMoney: true,
  timeHorizonYears: "",
  annualLiquidityNeedPct: "0",
  hasExternalResources: false,
  behavioral: {
    risk_tolerance: 3,
    risk_preference: 3,
    financial_knowledge: 3,
    investing_experience: 3,
    risk_perception: 3,
    risk_composure: 3,
    self_control: 3,
    optimism: 3,
  },
};

const STEP_TITLES = ["財務目標", "財務狀況", "心理特徵評估"];

function parseNum(value: string): number | null {
  if (value.trim() === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

const fieldStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.25rem",
  marginBottom: "1rem",
};

const labelStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: "0.95rem",
};

const inputStyle: React.CSSProperties = {
  padding: "0.5rem",
  fontSize: "1rem",
  border: "1px solid #ccc",
  borderRadius: 4,
  maxWidth: 260,
};

const errorStyle: React.CSSProperties = {
  color: "#b00020",
  fontSize: "0.85rem",
};

const fieldsetStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 8,
  padding: "1.25rem",
  marginBottom: "1.5rem",
};

const legendStyle: React.CSSProperties = {
  fontWeight: 700,
  fontSize: "1.1rem",
  padding: "0 0.5rem",
};

const radioRowStyle: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "1rem",
};

const radioOptionStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.35rem",
  fontSize: "0.9rem",
};

const buttonRowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  marginTop: "1.5rem",
};

const buttonStyle: React.CSSProperties = {
  padding: "0.6rem 1.4rem",
  fontSize: "1rem",
  borderRadius: 6,
  border: "1px solid #333",
  background: "#fff",
  cursor: "pointer",
};

const primaryButtonStyle: React.CSSProperties = {
  ...buttonStyle,
  background: "#1a3c6e",
  color: "#fff",
  border: "1px solid #1a3c6e",
};

export function Questionnaire({
  onComplete,
}: {
  onComplete: (result: AssessmentResponse) => void;
}) {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>(initialState);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateBehavioral(key: BehavioralKey, value: number) {
    setForm((prev) => ({
      ...prev,
      behavioral: { ...prev.behavioral, [key]: value },
    }));
  }

  function validateStep0(): Record<string, string> {
    const e: Record<string, string> = {};
    const targetAmount = parseNum(form.targetAmount);
    if (targetAmount === null || targetAmount <= 0) {
      e.targetAmount = "請輸入大於 0 的目標金額";
    }
    const years = parseNum(form.years);
    if (years === null || years <= 0 || years > 80) {
      e.years = "請輸入 1 至 80 之間的年期";
    }
    const currentAssets = parseNum(form.currentAssets);
    if (currentAssets === null || currentAssets < 0) {
      e.currentAssets = "目前資產不可為負數";
    }
    const annualContribution = parseNum(form.annualContribution);
    if (annualContribution === null || annualContribution < 0) {
      e.annualContribution = "每年可投入金額不可為負數";
    }
    return e;
  }

  function validateStep1(): Record<string, string> {
    const e: Record<string, string> = {};
    const timeHorizonYears = parseNum(form.timeHorizonYears);
    if (timeHorizonYears === null || timeHorizonYears <= 0 || timeHorizonYears > 80) {
      e.timeHorizonYears = "請輸入 1 至 80 之間的投資期限";
    }
    const pct = parseNum(form.annualLiquidityNeedPct);
    if (pct === null || pct < 0 || pct > 100) {
      e.annualLiquidityNeedPct = "請輸入 0 至 100 之間的比例";
    }
    return e;
  }

  function goNext() {
    const stepErrors = step === 0 ? validateStep0() : validateStep1();
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors);
      return;
    }
    setErrors({});
    setStep((s) => Math.min(s + 1, STEP_TITLES.length - 1));
  }

  function goBack() {
    setErrors({});
    setSubmitError(null);
    setStep((s) => Math.max(s - 1, 0));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const step0Errors = validateStep0();
    const step1Errors = validateStep1();
    const combined = { ...step0Errors, ...step1Errors };
    if (Object.keys(combined).length > 0) {
      setErrors(combined);
      setStep(Object.keys(step0Errors).length > 0 ? 0 : 1);
      return;
    }

    const request: AssessmentRequest = {
      goal: {
        target_amount: Number(form.targetAmount),
        years: Number(form.years),
        current_assets: Number(form.currentAssets || "0"),
        annual_contribution: Number(form.annualContribution || "0"),
        consequence_of_failure: form.consequenceOfFailure,
        target_in_todays_money: form.targetInTodaysMoney,
      },
      ability: {
        time_horizon_years: Number(form.timeHorizonYears),
        annual_liquidity_need_pct: Number(form.annualLiquidityNeedPct || "0") / 100,
        has_external_resources: form.hasExternalResources,
      },
      behavioral: { ...form.behavioral },
    };

    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await api.post<AssessmentResponse>("/assessments", request);
      onComplete(response);
    } catch (error) {
      if (error instanceof ApiError) {
        if (Array.isArray(error.detail)) {
          const messages = (error.detail as Array<{ loc?: unknown; msg?: unknown }>)
            .map((d) => (typeof d?.msg === "string" ? d.msg : null))
            .filter((msg): msg is string => Boolean(msg));
          setSubmitError(messages.length > 0 ? messages.join("；") : error.message);
        } else {
          setSubmitError(error.message);
        }
      } else if (error instanceof TypeError) {
        setSubmitError("無法連線至伺服器，請確認網路連線或聯絡管理員確認服務是否已部署");
      } else {
        setSubmitError("發生錯誤，請稍後再試");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 640 }}>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        {STEP_TITLES.map((title, i) => (
          <div
            key={title}
            style={{
              flex: 1,
              textAlign: "center",
              padding: "0.4rem",
              borderRadius: 4,
              fontSize: "0.85rem",
              fontWeight: i === step ? 700 : 400,
              background: i === step ? "#1a3c6e" : "#eee",
              color: i === step ? "#fff" : "#555",
            }}
          >
            {i + 1}. {title}
          </div>
        ))}
      </div>

      {step === 0 && (
        <fieldset style={fieldsetStyle}>
          <legend style={legendStyle}>財務目標</legend>

          <div style={fieldStyle}>
            <label style={labelStyle} htmlFor="targetAmount">
              目標金額（NT$）
            </label>
            <input
              id="targetAmount"
              style={inputStyle}
              type="number"
              min={0}
              value={form.targetAmount}
              onChange={(e) => update("targetAmount", e.target.value)}
              required
            />
            {errors.targetAmount && <span style={errorStyle}>{errors.targetAmount}</span>}
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle} htmlFor="years">
              年期
            </label>
            <input
              id="years"
              style={inputStyle}
              type="number"
              min={1}
              max={80}
              value={form.years}
              onChange={(e) => update("years", e.target.value)}
              required
            />
            {errors.years && <span style={errorStyle}>{errors.years}</span>}
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle} htmlFor="currentAssets">
              目前資產（NT$）
            </label>
            <input
              id="currentAssets"
              style={inputStyle}
              type="number"
              min={0}
              value={form.currentAssets}
              onChange={(e) => update("currentAssets", e.target.value)}
            />
            {errors.currentAssets && <span style={errorStyle}>{errors.currentAssets}</span>}
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle} htmlFor="annualContribution">
              每年可投入金額（NT$）
            </label>
            <input
              id="annualContribution"
              style={inputStyle}
              type="number"
              min={0}
              value={form.annualContribution}
              onChange={(e) => update("annualContribution", e.target.value)}
            />
            {errors.annualContribution && (
              <span style={errorStyle}>{errors.annualContribution}</span>
            )}
          </div>

          <div style={fieldStyle}>
            <span style={labelStyle}>若無法達成目標，你可以接受嗎？</span>
            <div style={radioRowStyle}>
              {(
                [
                  { value: "acceptable", label: "可以接受" },
                  { value: "unacceptable", label: "不可以接受" },
                  { value: "unknown", label: "不確定" },
                ] as { value: ConsequenceOfFailure; label: string }[]
              ).map((opt) => (
                <label key={opt.value} style={radioOptionStyle}>
                  <input
                    type="radio"
                    name="consequenceOfFailure"
                    value={opt.value}
                    checked={form.consequenceOfFailure === opt.value}
                    onChange={() => update("consequenceOfFailure", opt.value)}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          <div style={fieldStyle}>
            <label style={radioOptionStyle}>
              <input
                type="checkbox"
                checked={form.targetInTodaysMoney}
                onChange={(e) => update("targetInTodaysMoney", e.target.checked)}
              />
              <span style={labelStyle}>目標金額是以今天的購買力計算的嗎？</span>
            </label>
          </div>
        </fieldset>
      )}

      {step === 1 && (
        <fieldset style={fieldsetStyle}>
          <legend style={legendStyle}>財務狀況</legend>

          <div style={fieldStyle}>
            <label style={labelStyle} htmlFor="timeHorizonYears">
              這筆資金的投資期限（年）
            </label>
            <input
              id="timeHorizonYears"
              style={inputStyle}
              type="number"
              min={1}
              max={80}
              value={form.timeHorizonYears}
              onChange={(e) => update("timeHorizonYears", e.target.value)}
              required
            />
            {errors.timeHorizonYears && (
              <span style={errorStyle}>{errors.timeHorizonYears}</span>
            )}
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle} htmlFor="annualLiquidityNeedPct">
              每年預期從這筆投資提領的比例（%）
            </label>
            <input
              id="annualLiquidityNeedPct"
              style={inputStyle}
              type="number"
              min={0}
              max={100}
              value={form.annualLiquidityNeedPct}
              onChange={(e) => update("annualLiquidityNeedPct", e.target.value)}
            />
            {errors.annualLiquidityNeedPct && (
              <span style={errorStyle}>{errors.annualLiquidityNeedPct}</span>
            )}
          </div>

          <div style={fieldStyle}>
            <label style={radioOptionStyle}>
              <input
                type="checkbox"
                checked={form.hasExternalResources}
                onChange={(e) => update("hasExternalResources", e.target.checked)}
              />
              <span style={labelStyle}>
                若遇到緊急狀況，你是否有足夠的外部收入、信貸額度、現金儲蓄或保險，不需要動用這筆投資？
              </span>
            </label>
          </div>
        </fieldset>
      )}

      {step === 2 && (
        <fieldset style={fieldsetStyle}>
          <legend style={legendStyle}>心理特徵評估</legend>
          {BEHAVIORAL_QUESTIONS.map((q) => (
            <div key={q.key} style={fieldStyle}>
              <span style={labelStyle}>{q.label}</span>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "#666", maxWidth: 420 }}>
                <span>{q.lowLabel}</span>
                {q.midLabel && <span>{q.midLabel}</span>}
                <span>{q.highLabel}</span>
              </div>
              <div style={radioRowStyle}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <label key={n} style={radioOptionStyle}>
                    <input
                      type="radio"
                      name={q.key}
                      value={n}
                      checked={form.behavioral[q.key] === n}
                      onChange={() => updateBehavioral(q.key, n)}
                    />
                    {n}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </fieldset>
      )}

      {submitError && (
        <div style={{ ...errorStyle, marginBottom: "1rem", whiteSpace: "pre-wrap" }}>
          {submitError}
        </div>
      )}

      <div style={buttonRowStyle}>
        <button
          type="button"
          style={buttonStyle}
          onClick={goBack}
          disabled={step === 0 || submitting}
        >
          上一步
        </button>
        {step < STEP_TITLES.length - 1 ? (
          <button key="next" type="button" style={primaryButtonStyle} onClick={goNext}>
            下一步
          </button>
        ) : (
          <button key="submit" type="submit" style={primaryButtonStyle} disabled={submitting}>
            {submitting ? "送出中…" : "送出"}
          </button>
        )}
      </div>
    </form>
  );
}
