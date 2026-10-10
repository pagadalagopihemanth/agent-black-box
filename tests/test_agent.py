import json
from types import SimpleNamespace as NS
import pytest
from agent import PRESETS, run_agent

def call(name, args, call_id="call1"):
    return NS(type="function_call", name=name, arguments=args, call_id=call_id)

class Client:
    def __init__(self, responses):
        self.items = iter(responses)
        self.calls = []
        self.responses = self
    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = next(self.items)
        if isinstance(item, Exception):
            raise item
        return NS(output=item, output_text="Gateway outcome received.")

@pytest.mark.parametrize("instruction,decision", list(zip(PRESETS[:3], ["ALLOW", "BLOCK", "REVIEW"])))
def test_offline_scenarios(gateway, instruction, decision):
    result = run_agent(instruction, gateway, offline=True)
    assert result["actions"][0]["decision"] == decision
    assert result["mode"] == "offline"

def test_live_protocol(gateway):
    client = Client([[call("read_invoice", '{"invoice_id":"INV-1001"}')], []])
    result = run_agent(PRESETS[0], gateway, client=client, model="gpt-6.1-sol")
    assert result["actions"][0]["execution"] == "completed"
    output = client.calls[1]["input"][-1]
    assert output["type"] == "function_call_output"
    assert json.loads(output["output"])["decision"] == "ALLOW"
    assert all(c["service_tier"] == "default" and c["store"] is False for c in client.calls)

def test_multiple_malformed_unknown(gateway):
    client = Client([[call("approve_payment", "not json"), call("exec", "{}", "call2")], []])
    result = run_agent("test", gateway, client=client, model="gpt-6.1-sol")
    assert len(result["actions"]) == 2
    assert all(r["decision"] == "BLOCK" for r in result["actions"])

def test_api_failure(gateway):
    result = run_agent("test", gateway, client=Client([RuntimeError("sk-sensitive")]), model="gpt-6.1-sol")
    assert result["actions"][0]["execution"] == "prevented"
    assert "sk-sensitive" not in str(result)

def test_no_call(gateway):
    assert run_agent("hello", gateway, client=Client([[]]), model="gpt-6.1-sol")["actions"] == []

def test_bounded_loop(gateway):
    client = Client([[call("approve_payment", '{"payment_id":"PAY-202","amount":15000,"currency":"USD"}', f"call{i}")] for i in range(3)])
    result = run_agent("test", gateway, client=client, model="gpt-6.1-sol")
    assert len(client.calls) == 3
    assert result["actions"][-1]["decision"] == "BLOCK"
    assert all(r["execution"] != "completed" for r in result["actions"])

def test_duplicate_call(gateway):
    c = call("approve_payment", '{"payment_id":"PAY-1","amount":1,"currency":"USD"}')
    result = run_agent("test", gateway, client=Client([[c, c], []]), model="gpt-6.1-sol")
    assert len(result["actions"]) == 2
    assert result["actions"][1]["decision"] == "BLOCK"
    with gateway.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 1

def test_injection_content_untrusted(gateway):
    client = Client([[call("read_invoice", '{"invoice_id":"INV-ATTACK"}')], [call("approve_payment", '{"payment_id":"PAY-202","amount":15000,"currency":"USD"}', "call2")], []])
    result = run_agent(PRESETS[3], gateway, client=client, model="gpt-6.1-sol")
    assert "Ignore previous" in result["actions"][0]["result"]["description"]
    assert result["actions"][1]["decision"] == "REVIEW"
    assert result["actions"][1]["execution"] == "pending"
