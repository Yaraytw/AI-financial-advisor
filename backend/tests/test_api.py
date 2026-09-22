"""HTTP-layer tests for the FastAPI app on top of the scoring engine."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

VALID_PAYLOAD = {
    "goal": {
        "target_amount": 5_000_000,
        "years": 20,
        "current_assets": 500_000,
        "annual_contribution": 100_000,
        "consequence_of_failure": "unknown",
        "target_in_todays_money": True,
    },
    "ability": {
        "time_horizon_years": 20,
        "annual_liquidity_need_pct": 0.0,
        "has_external_resources": False,
    },
    "behavioral": {
        "risk_tolerance": 4,
        "risk_preference": 4,
        "financial_knowledge": 3,
        "investing_experience": 3,
        "risk_perception": 4,
        "risk_composure": 4,
        "self_control": 3,
        "optimism": 3,
    },
}


@pytest.fixture()
def client():
    # Plain "sqlite:///:memory:" gives each new connection its own distinct
    # empty in-memory database, so a session opened by one request wouldn't
    # see rows written by another. StaticPool forces every connection
    # through a single shared underlying connection, so the whole test run
    # shares one in-memory database instead.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_post_assessment_returns_201_with_sane_output(client: TestClient) -> None:
    resp = client.post("/assessments", json=VALID_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()

    assert body["id"] is not None
    assert body["calibration"]["light"] in {"red", "yellow", "green"}
    weight = body["calibration"]["recommended_growth_weight"]
    assert 0.0 <= weight <= 1.0

    assert body["need"]["level"] in {"Low", "Moderate", "High"}
    assert body["ability"]["level"] in {"Low", "Moderate", "High"}
    assert body["behavioral"]["level"] in {"Low", "Moderate", "High"}
    assert isinstance(body["alerts"], list)


def test_get_assessment_matches_post_response_byte_for_byte(client: TestClient) -> None:
    post_resp = client.post("/assessments", json=VALID_PAYLOAD)
    assert post_resp.status_code == 201
    post_body = post_resp.json()

    get_resp = client.get(f"/assessments/{post_body['id']}")
    assert get_resp.status_code == 200
    assert get_resp.text == post_resp.text
    assert get_resp.json() == post_body


def test_get_nonexistent_assessment_returns_404(client: TestClient) -> None:
    resp = client.get("/assessments/999999")
    assert resp.status_code == 404


def test_post_invalid_payload_returns_422(client: TestClient) -> None:
    bad_payload = {
        **VALID_PAYLOAD,
        "goal": {**VALID_PAYLOAD["goal"], "target_amount": -100},
    }
    resp = client.post("/assessments", json=bad_payload)
    assert resp.status_code == 422
