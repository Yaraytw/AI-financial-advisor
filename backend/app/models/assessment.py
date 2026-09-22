"""SQLAlchemy ORM model for a persisted assessment."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    goal_input: Mapped[dict] = mapped_column(JSON, nullable=False)
    ability_input: Mapped[dict] = mapped_column(JSON, nullable=False)
    behavioral_input: Mapped[dict] = mapped_column(JSON, nullable=False)

    need_level: Mapped[str] = mapped_column(String, nullable=False)
    ability_level: Mapped[str] = mapped_column(String, nullable=False)
    behavioral_level: Mapped[str] = mapped_column(String, nullable=False)
    behavioral_score: Mapped[int] = mapped_column(Integer, nullable=False)

    traffic_light: Mapped[str] = mapped_column(String, nullable=False)
    recommended_growth_weight: Mapped[float] = mapped_column(Float, nullable=False)

    # Full serialized AssessmentResponse (minus id) so a later GET returns
    # exactly what was computed at create time instead of an approximation
    # reconstructed from the summary columns above.
    result_output: Mapped[dict] = mapped_column(JSON, nullable=False)
