import pytest

from app.scoring.alerts import AlertSeverity, generate_alerts
from app.scoring.models import BehavioralProfile


def make_profile(self_control=3, optimism=3, financial_knowledge=3):
    return BehavioralProfile(
        risk_tolerance=3,
        risk_preference=3,
        financial_knowledge=financial_knowledge,
        investing_experience=3,
        risk_perception=3,
        risk_composure=3,
        self_control=self_control,
        optimism=optimism,
    )


class TestGenerateAlerts:
    def test_no_alerts_for_neutral_profile(self):
        p = make_profile(self_control=3, optimism=3, financial_knowledge=3)
        assert generate_alerts(p) == ()

    def test_high_optimism_alert(self):
        p = make_profile(optimism=5, self_control=3)
        alerts = generate_alerts(p)
        assert len(alerts) == 1
        assert alerts[0].code == "high_optimism_cost_insensitivity"
        assert alerts[0].severity == AlertSeverity.WARNING
        assert "成本" in alerts[0].message

    def test_optimism_below_threshold_no_alert(self):
        p = make_profile(optimism=4, self_control=3)
        assert generate_alerts(p) == ()

    def test_low_self_control_with_high_knowledge_is_info(self):
        p = make_profile(self_control=2, financial_knowledge=4, optimism=3)
        alerts = generate_alerts(p)
        assert len(alerts) == 1
        assert alerts[0].code == "low_self_control_forced_savings"
        assert alerts[0].severity == AlertSeverity.INFO
        assert "失控" not in alerts[0].message

    def test_low_self_control_with_low_knowledge_is_warning(self):
        p = make_profile(self_control=1, financial_knowledge=2, optimism=3)
        alerts = generate_alerts(p)
        assert len(alerts) == 1
        assert alerts[0].code == "low_self_control_forced_savings"
        assert alerts[0].severity == AlertSeverity.WARNING
        assert "失控" in alerts[0].message

    def test_self_control_above_threshold_no_alert(self):
        p = make_profile(self_control=3, financial_knowledge=1, optimism=3)
        assert generate_alerts(p) == ()

    def test_both_alerts_fire_together_in_order(self):
        p = make_profile(optimism=5, self_control=2, financial_knowledge=2)
        alerts = generate_alerts(p)
        assert len(alerts) == 2
        assert alerts[0].code == "high_optimism_cost_insensitivity"
        assert alerts[1].code == "low_self_control_forced_savings"
        assert alerts[1].severity == AlertSeverity.WARNING
