"""
Build the Assignment 3 PDF report (Traditional Chinese, ~7 pages) from the files robo_advisor.py wrote.

Every number in the report is read from output/ (results.json, cap_sensitivity.csv, ...), so re-running
robo_advisor.py on new data and then this script gives a consistent report.

Usage:
  python make_report.py                          # reads output/, writes output/HW3_report.pdf
  python make_report.py --student "姓名 學號"     # name shown on the cover block
  python make_report.py --font /path/to/CJK.ttf  # if no CJK font is auto-detected
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import risk_profile as rp

HERE = Path(__file__).resolve().parent
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/msjh.ttc",
]
GROUPS = ["Equity ETFs", "Defensive stocks", "Bonds", "Gold"]
GROUP_ZH = {"Equity ETFs": "股票型 ETF", "Defensive stocks": "防禦型個股", "Bonds": "債券 ETF", "Gold": "黃金 ETF"}
TYPE_ZH = {"Conservative": "保守型", "Moderate": "穩健型", "Aggressive": "積極型"}
INK, MUTED, RULE, HEAD_BG = colors.HexColor("#111111"), colors.HexColor("#555555"), colors.HexColor("#cfcdc6"), colors.HexColor("#eef2f7")


def register_font(path: str | None) -> str:
    for cand in ([path] if path else []) + FONT_CANDIDATES:
        if cand and Path(cand).exists():
            pdfmetrics.registerFont(TTFont("CJK", cand, subfontIndex=0) if cand.lower().endswith(".ttc") else TTFont("CJK", cand))
            return "CJK"
    raise SystemExit("No CJK font found; pass --font /path/to/font.ttf (or .ttc)")


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def build(out_dir: Path, student: str, font_path: str | None, pdf_path: Path) -> None:
    font = register_font(font_path)
    res = json.loads((out_dir / "results.json").read_text())
    sens = pd.read_csv(out_dir / "cap_sensitivity.csv")
    corr = pd.read_csv(out_dir / "correlation_matrix.csv", index_col=0)
    data, cfg, fr = res["data"], res["settings"], res["frontier_range"]
    inv = res["investors"]
    assets = res["assets"]
    names = list(inv)
    cap = cfg["max_weight"]

    st = {
        "title": ParagraphStyle("title", fontName=font, wordWrap="CJK", fontSize=19, leading=26, textColor=INK, spaceAfter=4),
        "sub": ParagraphStyle("sub", fontName=font, wordWrap="CJK", fontSize=10, leading=15, textColor=MUTED, spaceAfter=10),
        "h1": ParagraphStyle("h1", fontName=font, wordWrap="CJK", fontSize=13.5, leading=19, textColor=colors.HexColor("#0b4f8a"), spaceBefore=10, spaceAfter=5),
        "h2": ParagraphStyle("h2", fontName=font, wordWrap="CJK", fontSize=11, leading=16, textColor=INK, spaceBefore=6, spaceAfter=3),
        "p": ParagraphStyle("p", fontName=font, wordWrap="CJK", fontSize=9.6, leading=15.2, textColor=INK, alignment=TA_LEFT, spaceAfter=4),
        "cell": ParagraphStyle("cell", fontName=font, wordWrap="CJK", fontSize=8.2, leading=11.6, textColor=INK),
        "cellb": ParagraphStyle("cellb", fontName=font, wordWrap="CJK", fontSize=8.2, leading=11.6, textColor=INK),
        "cap": ParagraphStyle("cap", fontName=font, wordWrap="CJK", fontSize=8.2, leading=12, textColor=MUTED, spaceAfter=6),
        "code": ParagraphStyle("code", fontName=font, wordWrap="CJK", fontSize=8.6, leading=13, textColor=INK, backColor=HEAD_BG, borderPadding=4, spaceAfter=6),
    }
    P = lambda t, s="p": Paragraph(t, st[s])  # noqa: E731
    C = lambda t: Paragraph(str(t).replace("&", "&amp;") if "<" not in str(t) else str(t), st["cell"])  # noqa: E731

    def table(rows, widths, header=True, zebra=False):
        t = Table([[c if not isinstance(c, str) else C(c) for c in r] for r in rows], colWidths=widths, repeatRows=1 if header else 0)
        style = [("GRID", (0, 0), (-1, -1), 0.4, RULE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
        if header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
        if zebra:
            style += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fafaf8")) for i in range(2, len(rows), 2)]
        t.setStyle(TableStyle(style))
        return t

    def img(name, width):
        path = out_dir / name
        from PIL import Image as PILImage
        w, h = PILImage.open(path).size
        return Image(str(path), width=width, height=width * h / w)

    def group_weights(w: dict) -> dict:
        g = {k: 0.0 for k in GROUPS}
        for a, x in w.items():
            g[assets[a]["group"]] += x
        return g

    story = []
    # ------------------------------------------------------------------ cover / summary
    story += [P("理財機器人 Assignment 3", "title"),
              P("投資人風險屬性評估與最適投資組合選擇（Investor Profiling × Modern Portfolio Theory × Automated Asset Allocation）", "sub")]
    if student:
        story.append(P(student, "sub"))
    best = inv["Aggressive"] if "Aggressive" in inv else inv[names[-1]]
    cons = inv["Conservative"] if "Conservative" in inv else inv[names[0]]
    story += [
        P("摘要", "h1"),
        P(f"本作業以 Python 實作一個初步的自動化投資建議流程：先用 10 題數位問卷衡量投資人的「風險承受能力」與「風險承受意願」，"
          f"取兩者較低者作為風險分數（0–100）並分成保守、穩健、積極三型；再以 {data['start']} 至 {data['end']} 共 {data['n_returns']:,} 筆台灣上市 8 檔資產的日報酬，"
          f"估計預期報酬與共變異數矩陣，用最佳化求出長期不得放空、單一資產上限 {pct(cap, 0)} 的效率前緣；最後依風險分數決定目標波動度，"
          f"由最佳化程序在前緣上求出各投資人的資產配置。所有權重皆由程式產生，沒有預先寫死。"),
        P(f"結果顯示：保守型（分數 {cons['score']:.0f}）目標波動度 {pct(cons['volatility'])}、預期年報酬 {pct(cons['expected_return'])}；"
          f"積極型（分數 {best['score']:.0f}）目標波動度 {pct(best['volatility'])}、預期年報酬 {pct(best['expected_return'])}。"
          f"另設一位「態度積極但財務能力不足」的投資人，示範取較低者的規則如何避免給出過度冒險的建議。"
          f"注意：預期報酬為歷史樣本平均，只用於課程示範，不代表未來績效。"),
    ]

    # ------------------------------------------------------------------ 1 data
    story += [P("一、資料來源與前處理", "h1"),
              P(f"<b>資料來源</b>：{data['source']}。期間 {data['start']} 至 {data['end']}，{data['n_returns']:,} 筆日報酬（約 {data['n_returns'] / 252:.1f} 年）。"
                "價格為除權息調整後收盤價，因此報酬已含股利再投入的效果。資料檔隨作業附上（data/return_matrix_TEJ.csv，說明見 data/DATA_SOURCE.md）。"),
              P("<b>前處理</b>：依日期排序，只在資產上市後向前填補單日缺口、不做向後填補，並取 8 檔資產共同有資料的期間；日報酬使用簡單報酬率 "
                "R<sub>t</sub> = P<sub>t</sub>/P<sub>t-1</sub> - 1。年化以 252 個交易日計算：預期報酬 μ = 日平均報酬 × 252，"
                "共變異數 Σ = 日共變異數 × 252。這樣組合報酬 E(R<sub>p</sub>) = Σ w<sub>i</sub>μ<sub>i</sub> 對權重是線性的，與作業二一致。")]
    rows = [["代號", "資產", "類別", "年化報酬 μ", "年化波動度 σ"]]
    for a, m in assets.items():
        rows.append([a, m["name"], GROUP_ZH[m["group"]], pct(m["annual_return"]), pct(m["annual_volatility"])])
    story += [table(rows, [1.6 * cm, 6.6 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm], zebra=True),
              P("表 1　資產池與樣本統計（年化）", "cap")]
    story.append(P(f"相關係數方面，0050 與 0056 高度相關（{corr.loc['0050', '0056']:.2f}），兩檔債券 ETF 也高度相關（{corr.loc['00679B', '00720B']:.2f}）；"
                   f"但長天期美債 00679B 與股票相關為負或接近零（與 0050 為 {corr.loc['00679B', '0050']:.2f}），"
                   f"防禦股 2412 與其他資產相關很低（與 0050 為 {corr.loc['2412', '0050']:.2f}），黃金 00635U 與股票相關約 {corr.loc['00635U', '0050']:.2f}。"
                   "這些低相關資產就是分散風險、讓效率前緣向左上彎曲的來源。"))

    # ------------------------------------------------------------------ 2 questionnaire
    story += [P("二、問卷設計", "h1"),
              P("問卷延續本專案主系統採用的 CFA／Hubble-Grable 三因子概念：風險承受<b>能力</b>（客觀財務條件）、風險承受<b>意願</b>（心理承受度）與風險<b>需求</b>（達成目標需要的報酬）。"
                "實務上最終風險水準不應超過能力與意願中較低者，所以本作業的問卷涵蓋能力與意願兩個因子各 5 題；風險需求（目標報酬率）需要財務目標與金額資訊，"
                "留待後續擴充（見討論）。每題為 5 選 1，依選項給 1–5 分，分數越高代表可承擔越多風險。")]
    rows = [["題號", "因子", "題目", "選項（1 分 → 5 分）"]]
    for q in rp.QUESTIONS:
        rows.append([q.qid, "能力" if q.factor == rp.ABILITY else "意願", q.text, " → ".join([q.options[0], q.options[-1]])])
    story += [table(rows, [1.1 * cm, 1.2 * cm, 8.6 * cm, 5.7 * cm], zebra=True),
              P("表 2　問卷題目（完整五個選項見 risk_profile.py；此處僅列最保守與最積極選項）", "cap")]

    # ------------------------------------------------------------------ 3 classification
    story += [P("三、風險分數與投資人分類", "h1"),
              P("<b>計分</b>：能力分數 S<sub>A</sub> = (A1–A5 平均分 - 1)/4 × 100；意願分數 S<sub>W</sub> = (W1–W5 平均分 - 1)/4 × 100，兩者皆介於 0–100。"),
              P("<b>整合規則</b>：總風險分數 S = min(S<sub>A</sub>, S<sub>W</sub>)。理由是：有能力但不願意承擔風險的人，勉強持有高波動資產容易在下跌時恐慌賣出；"
                "有意願但沒有能力的人，一次虧損就可能影響生活（例如兩年內要買房）。取較低者較保守，也符合適合性原則（suitability）。"),
              P("<b>分類</b>：S &lt; 35 為保守型；35 ≤ S &lt; 65 為穩健型；S ≥ 65 為積極型。這三型對應作業圖 1 的 Conservative／Moderate／Aggressive。"),
              P("<b>四位示範投資人</b>（問卷答案寫在 risk_profile.py 的 EXAMPLE_INVESTORS，屬於輸入資料而非投資組合權重）：")]
    rows = [["投資人", "背景", "能力", "意願", "總分", "類型", "決定分數的因子"]]
    for n, v in inv.items():
        rows.append([n, v["persona"], f"{v['ability']:.0f}", f"{v['willingness']:.0f}", f"{v['score']:.0f}", TYPE_ZH.get(v["type"], v["type"]),
                     {"ability": "能力", "willingness": "意願", "both": "兩者相同"}[v["binding_factor"]]])
    story += [table(rows, [3.2 * cm, 6.0 * cm, 1.1 * cm, 1.1 * cm, 1.1 * cm, 1.4 * cm, 2.1 * cm], zebra=True),
              P("表 3　示範投資人的問卷結果", "cap"),
              img("fig4_questionnaire_scores.png", 10 * cm),
              P("圖 4　各投資人的能力、意願與總分。Willing-but-Unable 的意願高達 95，但能力只有 25，因此總分取 25，被歸為保守型。", "cap")]

    # ------------------------------------------------------------------ 4 MPT
    story += [P("四、MPT 模型與最佳化", "h1"),
              P("<b>投資組合報酬與風險</b>：E(R<sub>p</sub>) = w′μ；σ<sub>p</sub> = √(w′Σw)。"),
              P(f"<b>限制條件</b>：Σw<sub>i</sub> = 1（全額投資）、0 ≤ w<sub>i</sub> ≤ {cap:.2f}（不放空，單一資產不超過 {pct(cap, 0)}）。"
                "上限避免最佳化結果集中在單一歷史上表現最好的資產（見第七節敏感度分析）。"),
              P("<b>效率前緣</b>：對每個目標報酬 r，以 scipy 的 SLSQP 解 min w′Σw（s.t. w′μ = r 及上述限制）。前緣起點是最小變異數投資組合（MVP），"
                "終點是以線性規劃（linprog）求得的最高報酬可行組合。"),
              P(f"在本資料與限制下：MVP 的波動度為 {pct(fr['mvp_vol'])}、預期報酬 {pct(fr['mvp_return'])}；最高報酬組合的波動度為 {pct(fr['max_vol'])}、預期報酬 {pct(fr['max_return'])}。"),
              P("<b>風險分數對應到組合</b>：把分數線性對應到前緣的風險範圍，"),
              P("σ*(S) = σ<sub>MVP</sub> + (S/100) × (σ<sub>MAX</sub> - σ<sub>MVP</sub>)", "code"),
              P("然後解 max w′μ　s.t. w′Σw ≤ σ*²，Σw = 1，0 ≤ w ≤ 上限。得到的就是在該投資人可接受風險下預期報酬最高的組合，一定落在效率前緣上。"
                "S = 0 對應 MVP，S = 100 對應最高報酬組合。"),
              img("fig3_score_mapping.png", 9.5 * cm),
              P("圖 3　風險分數對應到目標波動度（虛線為 35、65 分的分類界線）。", "cap"),
              P(f"<b>驗證</b>：程式內建兩項檢查並於執行時以 assert 驗證：(1) 每位投資人的組合，其波動度與「同報酬下最小變異數組合」的波動度差距 &lt; 0.05 個百分點"
                f"（實際最大差距 {max(res['verification']['frontier_gap'].values()):.1e}）；(2) {cfg['n_random']:,} 個隨機可行組合（種子 {cfg['seed']}，結果可重現）中，沒有任何一個同時報酬更高、風險更低於前緣"
                f"（實際 {res['verification']['random_portfolios_dominating_frontier']} 個）。")]

    # ------------------------------------------------------------------ 5 results
    story += [PageBreak(), P("五、結果", "h1"),
              img("fig1_efficient_frontier.png", 15.2 * cm),
              P("圖 1　效率前緣與各投資人的最適組合。淺藍色點為隨機可行組合，全部位於前緣的右下方；各組合點位置由最佳化決定。", "cap"),
              img("fig2_allocation_comparison.png", 15.2 * cm),
              P("圖 2　各投資人的最適資產配置比較（權重 ≥ 5% 者標示數字）。", "cap")]

    rows = [["資產"] + names]
    for a in res["data"]["assets"]:
        rows.append([a] + [pct(inv[n]["weights"][a]) for n in names])
    rows.append(["類別小計"] + ["" for _ in names])
    for g in GROUPS:
        rows.append([GROUP_ZH[g]] + [pct(group_weights(inv[n]["weights"])[g]) for n in names])
    story.append(KeepTogether([table(rows, [3.2 * cm] + [3.2 * cm] * len(names), zebra=False), P("表 4　最佳化產生的權重（含類別小計）", "cap")]))

    rows = [["指標"] + names]
    metric_rows = [("目標風險 σ*", "target_vol", True), ("預期年報酬 E(R)", "expected_return", True), ("年化波動度 σ", "volatility", True),
                   (f"夏普值（rf = {pct(cfg['rf'])}）", "sharpe", False), ("1 年 95% 風險值：E(R) - 1.645σ", "var95_1y", True),
                   ("歷史回測年化報酬", "hist_cagr", True), ("歷史最大回撤", "hist_max_drawdown", True),
                   ("歷史最差連續 1 年報酬", "hist_worst_1y", True)]
    for label, key, is_pct in metric_rows:
        rows.append([label] + [pct(inv[n][key]) if is_pct else f"{inv[n][key]:.2f}" for n in names])
    story += [table(rows, [5.2 * cm] + [2.7 * cm] * len(names), zebra=True),
              P("表 5　各組合的風險與報酬。歷史回測為樣本內、每日再平衡的結果，僅供說明；1 年 95% 風險值以常態分配近似。", "cap")]

    # ------------------------------------------------------------------ 6 advice
    story.append(P("六、給一般投資人的白話建議", "h1"))
    for n in names:
        v = inv[n]
        g = group_weights(v["weights"])
        top = sorted(((a, w) for a, w in v["weights"].items() if w >= 0.05), key=lambda t: -t[1])[:3]
        top_txt = "、".join(f"{a}（{pct(w, 0)}）" for a, w in top)
        label = TYPE_ZH.get(v["type"], v["type"])
        extra = ""
        if v["binding_factor"] == "ability" and v["willingness"] - v["ability"] >= 30:
            extra = (f"雖然您的投資意願很高（{v['willingness']:.0f} 分），但目前財務條件（{v['ability']:.0f} 分）還無法承受大幅虧損，"
                     "所以系統以能力為準給出較保守的配置；若備用金增加、短期大額支出完成後再重新評估，建議可以調整。")
        elif v["binding_factor"] == "willingness" and v["ability"] - v["willingness"] >= 15:
            extra = "您的財務條件其實可以承擔更多風險，但系統尊重您的心理感受，避免市場大跌時因恐慌而賣在低點。"
        story.append(P(
            f"<b>{n}（{label}，風險分數 {v['score']:.0f}）</b>　建議把資金配置為：股票型 ETF {pct(g['Equity ETFs'], 0)}、防禦型個股 {pct(g['Defensive stocks'], 0)}、"
            f"債券 ETF {pct(g['Bonds'], 0)}、黃金 {pct(g['Gold'], 0)}；比重較大的前幾名為 {top_txt}。"
            f"以歷史資料估計，這個組合每年預期報酬約 {pct(v['expected_return'])}，一般年度的上下波動約 ±{pct(v['volatility'])}；"
            f"過去這段期間最深的一次下跌（最大回撤）約 {pct(abs(v['hist_max_drawdown']))}，最差的連續一年約虧損 {pct(abs(v['hist_worst_1y']))}。"
            f"{extra}"))

    # ------------------------------------------------------------------ 7 discussion
    story.append(P("七、討論與限制", "h1"))
    cs = sens.pivot(index="max_weight", columns="profile", values="expected_return")
    cv = sens.pivot(index="max_weight", columns="profile", values="volatility")
    top50 = sens[sens["max_weight"] == 1.0].set_index("profile")
    rows = [["單一資產上限"] + [f"{n}（E(R) / σ）" for n in names]]
    for c in cs.index:
        rows.append([("無上限" if c >= 1 else pct(c, 0))] + [f"{pct(cs.loc[c, n])} / {pct(cv.loc[c, n])}" for n in names])
    story.append(KeepTogether([P("<b>1. 單一資產上限的影響。</b>下表比較不同上限下，每位投資人最適組合的預期報酬與波動度。"),
                               table(rows, [3.0 * cm] + [3.4 * cm] * len(names)), P("表 6　權重上限敏感度（完整權重見 cap_sensitivity.csv）", "cap")]))
    agg_uncapped = top50.loc[best_name := ("Aggressive" if "Aggressive" in top50.index else top50.index[-1])]
    story.append(P(f"無上限時，{best_name} 組合會把 {pct(agg_uncapped['0050'], 0)} 押在 0050（歷史報酬最高的單一資產），這是最佳化對估計誤差高度敏感的典型現象，"
                   f"因此本作業預設上限 {pct(cap, 0)}，換得較分散、較合理的建議。"))
    bond_cons = cons["weights"]["00679B"] + cons["weights"]["00720B"]
    story += [
        P(f"<b>2. 保守型為什麼債券比重很低？</b>保守型的債券比重只有 {pct(bond_cons, 0)}，多數低風險部位由防禦股 2412 與黃金承擔。原因在資料：樣本期間債券 ETF 表現疲弱（多半與期間的利率環境有關），"
          f"00679B 年化報酬 {pct(assets['00679B']['annual_return'])}、00720B 僅 {pct(assets['00720B']['annual_return'])}，而 2412 報酬 {pct(assets['2412']['annual_return'])}、"
          f"波動度僅 {pct(assets['2412']['annual_volatility'])}，且與其他資產相關係數低，因此最佳化認為 2412 的風險報酬更好。這在歷史上成立，但不代表未來債券永遠不適合保守投資人。"),
        P("<b>3. 預期報酬估計的限制。</b>以歷史平均當預期報酬（樣本內）會高估未來，特別是 2019 年後台股與美股大多頭、長天期債走空的特殊期間；"
          "MVP 只用共變異數、相對穩定，但越積極的組合越依賴報酬估計。進一步可以改用均衡報酬（Black-Litterman）、對平均報酬做收縮（shrinkage）或加入情境分析。"
          "此外回測未計交易成本、稅負與再平衡頻率，夏普值與回撤只能作為相對比較。"),
        P("<b>4. 問卷的限制。</b>題目為自行設計，尚未以大樣本檢驗信度與效度；等權重加總與 35/65 分界屬於合理的設計假設，並非實證校準。"
          "此外沒有納入風險需求（達成財務目標需要的報酬率）；若加入，可把「所需報酬率」換算成所需波動度，再與 σ*(S) 取較小者，形成與主系統一致的三因子模型。"),
        P("<b>5. 資料版權。</b>TEJ 資料僅限校園授權，隨作業附上的資料檔供老師重現使用，請勿再散布；不提供資料時，程式也能以 --prices 讀取 TEJ 價格檔，"
          "或以 yfinance 取得 Yahoo 資料做程式測試（Yahoo 資料與 TEJ 調整價可能略有差異）。"),
    ]

    # ------------------------------------------------------------------ 8 reproduce
    story += [P("八、重現方式與繳交檔案", "h1"),
              P("python3 -m pip install -r requirements.txt<br/>"
                "python3 robo_advisor.py --returns data/return_matrix_TEJ.csv --source \"TEJ Pro 調整股價(日)\"<br/>"
                "python3 make_report.py --student \"姓名 學號\"", "code"),
              table([["檔案", "內容"],
                     ["risk_profile.py", "問卷題目、計分、分類、示範投資人"],
                     ["robo_advisor.py", "資料讀取、μ/Σ 估計、效率前緣、目標波動度最佳化、圖表與輸出（--interactive 可自行作答）"],
                     ["make_report.py", "依 output/ 結果產生本 PDF"],
                     ["data/return_matrix_TEJ.csv、DATA_SOURCE.md", "金融資料檔與來源／期間說明"],
                     ["output/*.png", "圖 1 效率前緣、圖 2 配置比較、圖 3 分數對應、圖 4 問卷分數"],
                     ["output/investor_portfolios.csv、efficient_frontier.csv、cap_sensitivity.csv、results.json", "最佳化權重、前緣、敏感度與完整數值"]],
                    [6.2 * cm, 10.8 * cm], zebra=True)]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(2 * cm, 1.2 * cm, "Robo-Advisor Assignment 3 — Investor Profiling and Optimal Portfolio Selection")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"{doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.9 * cm,
                            title="Assignment 3 — Investor Profiling and Optimal Portfolio Selection", author=student or "")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE / "output")
    ap.add_argument("--student", default="")
    ap.add_argument("--font", default=None)
    ap.add_argument("--pdf", type=Path, default=None)
    a = ap.parse_args()
    pdf = a.pdf or a.out / "HW3_report.pdf"
    build(a.out, a.student, a.font, pdf)
    print(f"Wrote {pdf}")
