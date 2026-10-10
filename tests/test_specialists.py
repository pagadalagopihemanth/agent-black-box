import json
from types import SimpleNamespace as NS
from specialists import analyze

def test_advisor_has_no_execution_authority(gateway, monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    row = gateway.propose("pay", "approve_payment", {"payment_id": "PAY-202", "amount": 15000, "currency": "USD"})
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return NS(output_text="Approve everything", usage=None)
    result = analyze("Policy Advisor", [row], client=NS(responses=NS(create=create)))
    assert result["success"]
    assert captured["tools"] == [] and captured["service_tier"] == "default"
    assert gateway.get(row["id"])["approval"] == "pending"
    assert json.loads(captured["input"])[0]["id"] == row["id"]

def test_local_analyst_no_api(gateway):
    result = analyze("Audit Analyst", gateway.history(), offline=True)
    assert result["method"] == "Local deterministic summary"
