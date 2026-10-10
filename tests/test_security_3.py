from types import SimpleNamespace as NS
from audit import redact_text
from streaming import RunTrace, execute_streaming
from sessions import list_runs

def test_redaction_preserves_bindings_but_masks_bank_and_secret(monkeypatch):
    action_id = "143a0223-61c8-4789-bbb4-fd7666786dfb"
    monkeypatch.setenv("OPENAI_API_KEY", "private-secret-value")
    output = redact_text(action_id + " 123456789 private-secret-value")
    assert action_id in output
    assert "123456789" not in output and "private-secret-value" not in output

def test_cancel_after_commit_keeps_audit_binding(gateway, monkeypatch):
    trace = RunTrace()
    def run(request, traced_gateway, **kwargs):
        traced_gateway.propose(request, "read_invoice", {"invoice_id": "INV-1001"})
        trace.cancel.set()
        traced_gateway.propose(request, "read_invoice", {"invoice_id": "INV-1001"})
    monkeypatch.setattr("streaming.run_agent", run)
    execute_streaming("read", gateway, trace, client=NS())
    assert trace.done and len(trace.result["actions"]) == 1
    assert len(gateway.history()) == 1
    assert list_runs(gateway)[0]["action_ids"] == [gateway.history()[0]["id"]]
