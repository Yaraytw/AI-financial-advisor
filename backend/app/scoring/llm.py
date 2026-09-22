"""LLM extraction contract for the future chat-based questionnaire path.

The v1 questionnaire is 1-5 direct input (ticket #1), so nothing else in
this package calls into this module yet. It documents and validates the
contract an LLM-chat extraction layer must satisfy.
"""

from __future__ import annotations

from app.scoring.models import BEHAVIORAL_ATTRIBUTES, BehavioralProfile

EXTRACTION_SYSTEM_PROMPT = """You are an expert behavioral finance analyst. Based on the user's responses to open-ended investment scenarios, extract the following 8 psychometric attributes. Rate the first 6 attributes on a strict integer scale from 1 to 5 based on the CFA Investment Risk Profiling framework.

1. risk_tolerance (1=Very Low, 5=Very High)
2. risk_preference (1=Maximize Safety, 5=Maximize Returns)
3. financial_knowledge (1=Not at all, 5=Very Knowledgeable)
4. investing_experience (1=None, 5=Extensive)
5. risk_perception (1=Very Risky market view, 5=Very Safe market view)
6. risk_composure (1=Sold out in panic, 3=Did nothing, 5=Purchased more)

Additionally, extract 2 psychological traits based on psychology literature:
7. self_control (1=Impulsive/Present-biased, 5=High delay of gratification)
8. optimism (1=Pessimistic, 3=Moderate/Prudent, 5=Overly Optimistic/Cost-insensitive)

Output strictly as a JSON object."""


class LLMExtractionError(ValueError):
    """Raised when an LLM extraction payload fails strict validation."""


_ATTRIBUTE_SET = set(BEHAVIORAL_ATTRIBUTES)


def parse_llm_extraction(payload: dict) -> BehavioralProfile:
    """Strictly validate and parse an LLM extraction payload.

    Rejects: non-dict payloads, missing keys, unexpected extra keys,
    non-int values (bools explicitly rejected), and out-of-range values.
    Never silently clamps or defaults.
    """

    if not isinstance(payload, dict):
        raise LLMExtractionError(f"payload must be a dict (got {type(payload).__name__})")

    payload_keys = set(payload.keys())

    missing = _ATTRIBUTE_SET - payload_keys
    if missing:
        raise LLMExtractionError(f"payload is missing required keys: {sorted(missing)}")

    extra = payload_keys - _ATTRIBUTE_SET
    if extra:
        raise LLMExtractionError(f"payload has unexpected extra keys: {sorted(extra)}")

    for name in BEHAVIORAL_ATTRIBUTES:
        value = payload[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise LLMExtractionError(
                f"{name} must be an int in range 1..5 (got {type(value).__name__})"
            )

    try:
        return BehavioralProfile(**{name: payload[name] for name in BEHAVIORAL_ATTRIBUTES})
    except (TypeError, ValueError) as exc:
        raise LLMExtractionError(str(exc)) from exc
