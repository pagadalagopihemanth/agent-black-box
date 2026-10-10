import json
import httpx
import pytest
from decisions_adapter import MODEL, SCENARIOS, assess_actions, parse_response

def response(risks, names=None):
    return {"model": MODEL, "answers": [{"name": (names or [f"action_{i}" for i in range(len(risks))])[i], "type": "choice", "choice": risk, "confidence": .9} for i, risk in enumerate(risks)], "usage": {"total_tokens": 12}}

@pytest.mark.parametrize("scenario,risk,policy", [("Read invoice", "LOW RISK", "ALLOW"), ("Change supplier bank details", "HIGH RISK", "BLOCK"), ("Approve USD 15,000 payment", "HIGH RISK", "REVIEW")])
def test_risk_scenarios(monkeypatch, scenario, risk, policy):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    def handler(req):
        payload=json.loads(req.content)
        assert payload["model"] == MODEL and req.url.path == "/v1/decisions"
        assert "bank_account\": \"123" not in payload["input"]
        return httpx.Response(200, json=response([risk]))
    r=assess_actions([SCENARIOS[scenario]], httpx.MockTransport(handler))
    assert r["success"] and r["actions"][0]["risk"] == risk and r["actions"][0]["policy"] == policy
    import os
    assert os.environ["OPENAI_MODEL"] == "gpt-6.1-sol"
    assert "synthetic-secret" not in json.dumps(r)

def test_ai_low_risk_never_overrides_gateway(monkeypatch, gateway):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    for label in ("Change supplier bank details", "Approve USD 15,000 payment"):
        tool,args=SCENARIOS[label]
        r=assess_actions([(tool,args)], httpx.MockTransport(lambda req: httpx.Response(200,json=response(["LOW RISK"]))))
        assert r["actions"][0]["policy"] in ("BLOCK", "REVIEW")
    assert gateway.history() == []

@pytest.mark.parametrize("status,code,category", [(404,"model_not_found","model/access"),(403,"permission_denied","entitlement"),(429,"insufficient_quota","billing"),(401,"invalid_api_key","authentication")])
def test_access_errors_safe_no_retry(monkeypatch,status,code,category):
    monkeypatch.setenv("OPENAI_API_KEY","synthetic-secret")
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(status,json={"error":{"code":code,"message":"synthetic-secret sk-private 123456789012"}})
    r=assess_actions([SCENARIOS["Read invoice"]],httpx.MockTransport(handler))
    assert not r["success"] and r["error"]["category"] == category and len(calls)==1
    assert "synthetic-secret" not in json.dumps(r) and "123456789012" not in json.dumps(r)

@pytest.mark.parametrize("body", [response(["ALLOW"]), response(["LOW RISK"],["wrong"]), {"model":"gpt-6.1-sol","answers":[]}, {"model":MODEL,"answers":[{"name":"action_0","type":"choice","choice":"LOW RISK","confidence":10**400}]}])
def test_untrusted_response_rejected(body):
    with pytest.raises(ValueError):parse_response(body,["action_0"])

def test_refusal_has_no_fabricated_risk():
    answers,_=parse_response({"model":MODEL,"answers":[{"name":"action_0","type":"refusal"}]},["action_0"])
    assert answers[0]["risk"] is None

def test_untrusted_error_structure_is_safe(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    r=assess_actions([SCENARIOS["Read invoice"]],httpx.MockTransport(lambda req: httpx.Response(403,json={"error": "unexpected"})))
    assert not r["success"] and r["error"]["category"] == "entitlement"
