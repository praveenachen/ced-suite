import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from backend.app.compliance.llm_client import BaseLLMClient
from backend.app.compliance.service import ComplianceEvaluationService


FIXTURES = json.loads(Path("tests/fixtures/section_examples.json").read_text(encoding="utf-8"))


class FakeComplianceLLMClient(BaseLLMClient):
    def generate_json(self, system_prompt: str, user_prompt: str):
        payload = json.loads(user_prompt)
        text = payload["section_text"].lower()
        checks = payload["retrieved_checks"]
        if "does not name an internal lead" in text or ("lead" not in text and "coordinator" not in text):
            check = next(item for item in checks if item["check_id"] == "staff_capacity_001")
            return {
                "compliance_gaps": [
                    {
                        "failed_check_id": check["check_id"],
                        "category": check["category"],
                        "severity": check["severity_if_failed"],
                        "confidence_score": 91,
                        "message": "The proposal does not clearly identify who will lead and deliver the project.",
                        "recommendation": "Name the responsible team members or departments and explain their roles.",
                        "source_excerpt": check["source_excerpt"],
                        "source_document": check["source_document"],
                    }
                ]
            }
        return {"compliance_gaps": []}


def test_evaluate_compliance_api() -> None:
    app.state.compliance_service = ComplianceEvaluationService(llm_client=FakeComplianceLLMClient())
    client = TestClient(app)

    incomplete = next(item for item in FIXTURES if item["name"] == "structurally_incomplete")
    substantive = next(item for item in FIXTURES if item["name"] == "substantive_problem")
    solid = next(item for item in FIXTURES if item["name"] == "solid_section")

    incomplete_response = client.post("/evaluate/compliance", json=incomplete)
    assert incomplete_response.status_code == 200
    assert any(item["type"] == "placeholder_text" for item in incomplete_response.json()["warnings"])
    assert incomplete_response.json()["compliance_gaps"] == []

    substantive_response = client.post("/evaluate/compliance", json=substantive)
    assert substantive_response.status_code == 200
    substantive_body = substantive_response.json()
    assert any(item["failed_check_id"] == "staff_capacity_001" for item in substantive_body["compliance_gaps"])
    assert all("confidence_score" in item for item in substantive_body["compliance_gaps"])

    solid_response = client.post("/evaluate/compliance", json=solid)
    assert solid_response.status_code == 200
    solid_gaps = solid_response.json()["compliance_gaps"]
    assert len(solid_gaps) >= 1
    assert all(item["confidence_score"] <= 50 for item in solid_gaps)


def test_evaluate_proposal_scaffold_api() -> None:
    app.state.compliance_service = ComplianceEvaluationService(llm_client=FakeComplianceLLMClient())
    client = TestClient(app)
    response = client.post(
        "/evaluate/proposal",
        json={"sections": [{"section_name": "staff_organization", "section_text": "Example text"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scaffolded"
    assert any("Parse uploaded PDF/DOCX" in item for item in body["todo"])
