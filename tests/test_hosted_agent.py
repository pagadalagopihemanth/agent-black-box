from hosted_agent import handle_action
import pytest

def test_hosted_actions_still_require_policy(gateway):
    action = {"type": "function_call", "turn_id": "turn1", "call_id": "call1", "name": "approve_payment", "arguments": {"payment_id": "PAY-202", "amount": 15000, "currency": "USD"}}
    row = handle_action(gateway, "session1", action)
    assert row["decision"] == "REVIEW" and row["approval"] == "pending"
    assert handle_action(gateway, "session1", action)["id"] == row["id"]
    assert len(gateway.history()) == 1
    action["arguments"]["amount"] = 1
    with pytest.raises(ValueError, match="arguments changed"):
        handle_action(gateway, "session1", action)
    assert gateway.get(row["id"])["approval"] == "pending"

def test_hosted_unknown_and_injection_blocked(gateway):
    action = {"type": "function_call", "turn_id": "turn1", "call_id": "call1", "name": "exec", "arguments": {"code": "ignore policy"}}
    assert handle_action(gateway, "session1", action)["execution"] == "prevented"
