"""
Robo-Advisor Assignment 3 - investor risk questionnaire and scoring.

A 10-question digital questionnaire (1-5 points per answer) measured on the two
factors the CFA / Hubble-Grable framework treats as the *limits* on risk-taking:

  * Risk-taking ability   (capacity): can the investor afford a loss?   (A1-A5)
  * Risk-taking willingness (tolerance): does the investor accept losses? (W1-W5)

Each factor is scored 0-100. The overall risk score is the LOWER of the two
("the binding constraint"): an investor who is willing but cannot afford to lose
money is classified by what they can afford, and vice versa.

The score is only a number between 0 and 100; turning it into a portfolio is the
job of robo_advisor.py (optimizer), so no allocation is hard-coded here.
"""

from __future__ import annotations

from dataclasses import dataclass

ABILITY = "ability"
WILLINGNESS = "willingness"


@dataclass(frozen=True)
class Question:
    qid: str
    factor: str
    text: str
    options: tuple[str, str, str, str, str]  # option i is worth i+1 points


QUESTIONS: tuple[Question, ...] = (
    # ---- Risk-taking ability (capacity) -------------------------------------
    Question("A1", ABILITY, "您的年齡？",
             ("65 歲以上", "55–64 歲", "45–54 歲", "35–44 歲", "未滿 35 歲")),
    Question("A2", ABILITY, "這筆資金預計多久之後才會動用（投資期間）？",
             ("1 年內", "1–3 年", "3–5 年", "5–10 年", "10 年以上")),
    Question("A3", ABILITY, "您目前的收入來源與穩定度？",
             ("無工作收入，主要靠退休金或投資收益", "收入不穩定，且有主要扶養責任",
              "一般受薪收入", "穩定受薪或公職收入", "多元且穩定的收入，扣除支出後仍有大額結餘")),
    Question("A4", ABILITY, "不動用這筆投資，您的緊急預備金可支應幾個月的生活費？",
             ("不到 3 個月", "3–6 個月", "6–9 個月", "9–12 個月", "12 個月以上")),
    Question("A5", ABILITY, "這筆資金占您全部可投資資產的比例？",
             ("80% 以上", "60%–80%", "40%–60%", "20%–40%", "不到 20%")),
    # ---- Risk-taking willingness (tolerance) --------------------------------
    Question("W1", WILLINGNESS, "若投資組合在三個月內下跌 20%，您會怎麼做？",
             ("全部賣出，停止投資", "賣出一部分", "維持不動", "持續定期定額投入", "趁低檔加碼買進")),
    Question("W2", WILLINGNESS, "一年內您最多能接受的投資虧損幅度？",
             ("完全不能虧損", "最多 5%", "最多 10%", "最多 20%", "超過 20% 也可以")),
    Question("W3", WILLINGNESS, "您的投資經驗？",
             ("只有定存或儲蓄險", "買過基金或債券", "投資股票或 ETF 1–3 年",
              "投資股票或 ETF 3–10 年", "超過 10 年，經歷過多次空頭")),
    Question("W4", WILLINGNESS, "下列哪一種「一年後可能結果」您最想要？",
             ("確定賺 2%", "可能賺 7% 或虧 3%", "可能賺 17% 或虧 7%",
              "可能賺 30% 或虧 20%", "可能賺 50% 或虧 40%")),
    Question("W5", WILLINGNESS, "您最主要的投資目標？",
             ("保本，不要虧損", "穩定的配息收入", "兼顧收益與成長", "資產長期成長", "追求最大報酬，可忍受大幅波動")),
)

# Score bands -> investor type (labels follow the assignment's Figure 1).
BANDS: tuple[tuple[float, str, str], ...] = (
    (35.0, "Conservative", "保守型"),
    (65.0, "Moderate", "穩健型"),
    (100.0001, "Aggressive", "積極型"),
)


def factor_score(answers: dict[str, int], factor: str) -> float:
    """Mean answer of the factor's questions rescaled from 1-5 to 0-100."""
    qs = [q for q in QUESTIONS if q.factor == factor]
    missing = [q.qid for q in qs if q.qid not in answers]
    if missing:
        raise ValueError(f"missing answers: {missing}")
    for q in qs:
        if answers[q.qid] not in (1, 2, 3, 4, 5):
            raise ValueError(f"{q.qid}: answer must be 1-5, got {answers[q.qid]!r}")
    mean = sum(answers[q.qid] for q in qs) / len(qs)
    return (mean - 1) / 4 * 100


def classify(score: float) -> tuple[str, str]:
    for upper, en, zh in BANDS:
        if score < upper:
            return en, zh
    return BANDS[-1][1], BANDS[-1][2]


@dataclass(frozen=True)
class RiskProfile:
    ability: float
    willingness: float
    score: float
    type_en: str
    type_zh: str
    binding_factor: str  # which factor set the score ("ability", "willingness" or "both")

    @property
    def mismatch(self) -> float:
        return abs(self.ability - self.willingness)


def assess(answers: dict[str, int]) -> RiskProfile:
    ability = factor_score(answers, ABILITY)
    willingness = factor_score(answers, WILLINGNESS)
    score = min(ability, willingness)
    binding = "both" if ability == willingness else (ABILITY if ability < willingness else WILLINGNESS)
    en, zh = classify(score)
    return RiskProfile(ability, willingness, score, en, zh, binding)


# Example respondents used to demonstrate the pipeline. These are *questionnaire
# answers* (inputs), not portfolio weights; every allocation is produced by the
# optimizer from the resulting score.
EXAMPLE_INVESTORS: dict[str, dict] = {
    "Conservative": {
        "persona": "62 歲退休教師，退休金為主要收入，資金 3–5 年內可能動用，不願見到本金虧損。",
        "answers": {"A1": 2, "A2": 3, "A3": 1, "A4": 3, "A5": 2, "W1": 1, "W2": 2, "W3": 2, "W4": 2, "W5": 2},
    },
    "Moderate": {
        "persona": "40 歲工程師，薪資穩定，投資期間約 10 年，能接受一定波動但不想大起大落。",
        "answers": {"A1": 4, "A2": 4, "A3": 4, "A4": 3, "A5": 3, "W1": 3, "W2": 3, "W3": 3, "W4": 3, "W5": 3},
    },
    "Aggressive": {
        "persona": "27 歲軟體工程師，收入成長快、備用金充足，投資期間 10 年以上，以資產成長為目標。",
        "answers": {"A1": 5, "A2": 5, "A3": 4, "A4": 4, "A5": 4, "W1": 5, "W2": 5, "W3": 3, "W4": 4, "W5": 5},
    },
    "Willing-but-Unable": {
        "persona": "31 歲自由工作者，態度非常積極，但兩年內要買房、備用金不足、資金占全部資產大部分。",
        "answers": {"A1": 5, "A2": 1, "A3": 2, "A4": 1, "A5": 1, "W1": 5, "W2": 5, "W3": 4, "W4": 5, "W5": 5},
    },
}


def ask_interactively() -> dict[str, int]:
    """Terminal version of the questionnaire (python robo_advisor.py --interactive)."""
    answers: dict[str, int] = {}
    for q in QUESTIONS:
        print(f"\n[{q.qid}] {q.text}")
        for i, opt in enumerate(q.options, start=1):
            print(f"  {i}. {opt}")
        while True:
            raw = input("請輸入 1-5：").strip()
            if raw in {"1", "2", "3", "4", "5"}:
                answers[q.qid] = int(raw)
                break
            print("請輸入 1 到 5 的數字。")
    return answers
