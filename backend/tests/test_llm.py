import pytest

from app.scoring.models import BEHAVIORAL_ATTRIBUTES, BehavioralProfile
from app.scoring.llm import (
    EXTRACTION_SYSTEM_PROMPT,
    LLMExtractionError,
    parse_llm_extraction,
)


def valid_payload(**overrides):
    base = {name: 3 for name in BEHAVIORAL_ATTRIBUTES}
    base.update(overrides)
    return base


class TestExtractionSystemPrompt:
    def test_exact_text(self):
        expected = (
            "You are an expert behavioral finance analyst. Based on the user's "
            "responses to open-ended investment scenarios, extract the "
            "following 8 psychometric attributes. Rate the first 6 attributes "
            "on a strict integer scale from 1 to 5 based on the CFA Investment "
            "Risk Profiling framework.\n"
            "\n"
            "1. risk_tolerance (1=Very Low, 5=Very High)\n"
            "2. risk_preference (1=Maximize Safety, 5=Maximize Returns)\n"
            "3. financial_knowledge (1=Not at all, 5=Very Knowledgeable)\n"
            "4. investing_experience (1=None, 5=Extensive)\n"
            "5. risk_perception (1=Very Risky market view, 5=Very Safe market view)\n"
            "6. risk_composure (1=Sold out in panic, 3=Did nothing, 5=Purchased more)\n"
            "\n"
            "Additionally, extract 2 psychological traits based on psychology "
            "literature:\n"
            "7. self_control (1=Impulsive/Present-biased, 5=High delay of "
            "gratification)\n"
            "8. optimism (1=Pessimistic, 3=Moderate/Prudent, 5=Overly "
            "Optimistic/Cost-insensitive)\n"
            "\n"
            "Output strictly as a JSON object."
        )
        assert EXTRACTION_SYSTEM_PROMPT == expected

    def test_is_str(self):
        assert isinstance(EXTRACTION_SYSTEM_PROMPT, str)


class TestParseLLMExtraction:
    def test_valid_payload(self):
        payload = valid_payload(risk_composure=1, optimism=5)
        profile = parse_llm_extraction(payload)
        assert isinstance(profile, BehavioralProfile)
        assert profile.risk_composure == 1
        assert profile.optimism == 5

    def test_rejects_non_dict(self):
        for bad in [None, "not a dict", 42, ["a", "list"], (1, 2)]:
            with pytest.raises(LLMExtractionError):
                parse_llm_extraction(bad)

    def test_rejects_missing_key(self):
        payload = valid_payload()
        del payload["optimism"]
        with pytest.raises(LLMExtractionError):
            parse_llm_extraction(payload)

    def test_rejects_extra_key(self):
        payload = valid_payload()
        payload["unexpected_field"] = 3
        with pytest.raises(LLMExtractionError):
            parse_llm_extraction(payload)

    def test_rejects_out_of_range_value(self):
        payload = valid_payload(risk_tolerance=0)
        with pytest.raises(LLMExtractionError):
            parse_llm_extraction(payload)

        payload2 = valid_payload(optimism=6)
        with pytest.raises(LLMExtractionError):
            parse_llm_extraction(payload2)

    def test_rejects_bool_as_int(self):
        payload = valid_payload(self_control=True)
        with pytest.raises(LLMExtractionError):
            parse_llm_extraction(payload)

    def test_rejects_non_int_value(self):
        payload = valid_payload(risk_perception=3.5)
        with pytest.raises(LLMExtractionError):
            parse_llm_extraction(payload)

        payload2 = valid_payload(risk_perception="3")
        with pytest.raises(LLMExtractionError):
            parse_llm_extraction(payload2)

    def test_never_clamps_or_defaults(self):
        # An out-of-range value must raise, never silently clamp.
        payload = valid_payload(financial_knowledge=100)
        with pytest.raises(LLMExtractionError):
            parse_llm_extraction(payload)
