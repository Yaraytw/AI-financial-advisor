"""Spec section 5: psychological alerts.

Pure function over a BehavioralProfile. Does NOT affect allocation — only
adds disclosure/education messages for the UI layer to surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.scoring.models import BehavioralProfile

HIGH_OPTIMISM_THRESHOLD = 5
LOW_SELF_CONTROL_THRESHOLD = 2
LOW_FINANCIAL_KNOWLEDGE_THRESHOLD = 2


class AlertSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"


@dataclass(frozen=True)
class PsychologicalAlert:
    code: str
    severity: AlertSeverity
    message: str


def generate_alerts(profile: BehavioralProfile) -> tuple[PsychologicalAlert, ...]:
    alerts: list[PsychologicalAlert] = []

    if profile.optimism >= HIGH_OPTIMISM_THRESHOLD:
        alerts.append(
            PsychologicalAlert(
                code="high_optimism_cost_insensitivity",
                severity=AlertSeverity.WARNING,
                message=(
                    "過度樂觀的投資人通常對投資成本不敏感。在確認投資組合前，"
                    "請明確揭露手續費、經理費等成本，以及這些成本長期下來對"
                    "複利報酬的侵蝕效果。"
                ),
            )
        )

    if profile.self_control <= LOW_SELF_CONTROL_THRESHOLD:
        low_knowledge = profile.financial_knowledge <= LOW_FINANCIAL_KNOWLEDGE_THRESHOLD
        message = (
            "偵測到自我控制能力偏低。建議採用「自動扣款」或「限制提領」等機制，"
            "以機械化的方式強制執行投資計畫。"
        )
        if low_knowledge:
            message += (
                "結合財務知識偏低的情況，計畫失控、中途放棄的風險會進一步提高。"
            )
        alerts.append(
            PsychologicalAlert(
                code="low_self_control_forced_savings",
                severity=AlertSeverity.WARNING if low_knowledge else AlertSeverity.INFO,
                message=message,
            )
        )

    return tuple(alerts)
