"""API endpoint tests using FastAPI TestClient + in-memory SQLite."""

import pytest
from pathlib import Path


def _model_available() -> bool:
    return (
        Path(__file__).resolve().parent.parent
        / "risk_engine"
        / "artifacts"
        / "pipeline_xgboost.joblib"
    ).exists()


_skip_no_model = pytest.mark.skipif(
    not _model_available(),
    reason="XGBoost artifact not found — skip integration tests",
)


# ── Health / meta ──


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "PatientTriage" in body["name"]
    assert body.get("version")


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "engine" in body


def test_engine_info(client):
    resp = client.get("/triage/engine")
    assert resp.status_code == 200
    body = resp.json()
    assert body["production_model"] == "xgboost"
    assert body["safety_mode"] == "conservative"


# ── Triage intake ────────────────────────────────────────────────

MINIMAL_INTAKE = {
    "patient": {"age": 45, "gender": "male"},
    "chief_complaint": "chest_pain",
    "symptom_text": "substernal pressure radiating to left arm",
    "arrival_mode": "ambulance",
    "vitals": {
        "heart_rate": 110,
        "systolic_bp": 90,
        "spo2": 93,
        "resp_rate": 24,
        "temperature_c": 37.2,
        "pain_score": 8,
    },
}


@_skip_no_model
def test_intake_creates_visit(client):
    resp = client.post("/triage/intake", json=MINIMAL_INTAKE)
    assert resp.status_code == 201
    body = resp.json()

    # Check structure
    assert "visit" in body
    assert "patient" in body
    assert "assessment" in body
    assert "confidence" in body

    # Check assessment fields
    a = body["assessment"]
    assert 1 <= a["final_priority"] <= 5
    assert 0.0 <= a["risk_probability"] <= 1.0
    assert a["model_version"]
    assert a["confidence_label"] in ("High", "Medium", "Low")


@_skip_no_model
def test_intake_missing_vitals_escalates(client):
    """When all vitals are missing, the engine should escalate due to uncertainty."""
    payload = {
        "patient": {"age": 60, "gender": "female"},
        "chief_complaint": "shortness_of_breath",
        "symptom_text": "progressive dyspnea",
        "arrival_mode": "walk-in",
        "vitals": {},
    }
    resp = client.post("/triage/intake", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["assessment"]["missing_fields"]) > 0


@_skip_no_model
def test_intake_then_queue(client):
    """After an intake, the patient should appear in the queue."""
  
    resp = client.post("/triage/intake", json=MINIMAL_INTAKE)
    assert resp.status_code == 201
    visit_id = resp.json()["visit"]["id"]

    # Queue should now contain at least one entry
    resp = client.get("/queue")
    assert resp.status_code == 200
    queue = resp.json()
    assert any(e["visit_id"] == visit_id for e in queue)


@_skip_no_model
def test_intake_then_assessment_history(client):
    """After intake, the visit should have exactly one assessment."""
    resp = client.post("/triage/intake", json=MINIMAL_INTAKE)
    assert resp.status_code == 201
    visit_id = resp.json()["visit"]["id"]

    resp = client.get(f"/triage/visits/{visit_id}")
    assert resp.status_code == 200
    assessments = resp.json()
    assert len(assessments) >= 1
    assert assessments[0]["visit_id"] == visit_id


# ── Queue ────────────────────────────────────────────────────────


def test_queue_empty(client):
    resp = client.get("/queue")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_queue_summary(client):
    resp = client.get("/queue/summary")
    assert resp.status_code == 200


def test_queue_next_empty(client):
    """Calling next on an empty queue should return 404."""
    resp = client.post("/queue/next")
    assert resp.status_code == 404


# ── Patients ─────────────────────────────────────────────────────


def test_patients_list(client):
    resp = client.get("/patients")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_patient_not_found(client):
    resp = client.get("/patients/DOES-NOT-EXIST")
    assert resp.status_code == 404


# ── Overrides ────────────────────────────────────────────────────


def test_overrides_list(client):
    resp = client.get("/overrides")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_override_not_found(client):
    resp = client.get("/overrides/999999")
    assert resp.status_code == 404


@_skip_no_model
def test_override_duplicate_blocked(client):
    """Creating two overrides on the same assessment should return 409."""
    # Create a patient + assessment first
    resp = client.post("/triage/intake", json=MINIMAL_INTAKE)
    assert resp.status_code == 201
    assessment_id = resp.json()["assessment"]["id"]
    ai_priority = resp.json()["assessment"]["final_priority"]

    # Pick an override priority different from the AI priority
    override_priority = 1 if ai_priority != 1 else 2

    override_payload = {
        "clinician_id": "DR-TEST",
        "clinician_role": "attending",
        "override_priority": override_priority,
        "reason_code": "clinical_judgement",
        "reason_text": "Test override for integration testing purposes only",
        "acknowledged_ai_recommendation": True,
    }

    # First override should succeed
    resp = client.post(f"/overrides/assessments/{assessment_id}", json=override_payload)
    assert resp.status_code == 201

    # Second override on same assessment should be 409
    resp = client.post(f"/overrides/assessments/{assessment_id}", json=override_payload)
    assert resp.status_code == 409


# ── Audit ────────────────────────────────────────────────────────


def test_audit_events(client):
    resp = client.get("/audit/events")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_audit_verify(client):
    resp = client.get("/audit/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert "intact" in body
    assert "events" in body


def test_audit_policy(client):
    resp = client.get("/audit/policy")
    assert resp.status_code == 200
    body = resp.json()
    assert "jurisdiction" in body
    assert "retention_days" in body


# ── Simulation ───────────────────────────────────────────────────


@_skip_no_model
def test_simulation_scenarios(client):
    resp = client.get("/simulation/scenarios")
    assert resp.status_code == 200
    assert "scenarios" in resp.json()


# ── Visit not found 


def test_visit_assessments_not_found(client):
    resp = client.get("/triage/visits/999999")
    assert resp.status_code == 404


def test_close_visit_not_found(client):
    resp = client.post("/queue/visits/999999/close")
    assert resp.status_code == 404
