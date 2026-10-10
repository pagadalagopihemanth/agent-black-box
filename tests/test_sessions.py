from sessions import summarize_context, save_run, list_runs
from streaming import RunTrace

def test_context_preserves_approvals_and_ids(gateway):
    row = gateway.propose("pay", "approve_payment", {"payment_id": "PAY-202", "amount": 15000, "currency": "USD"})
    compact = summarize_context(gateway.history(), ["run-1"])
    assert compact["preserved"]["run_ids"] == ["run-1"]
    assert compact["preserved"]["unresolved_action_ids"] == [row["id"]]
    assert compact["preserved"]["actions"][0]["approval"] == "pending"
    assert gateway.get(row["id"])["execution"] == "pending"

def test_trace_persists_once(gateway):
    trace = RunTrace()
    save_run(gateway, trace)
    save_run(gateway, trace)
    assert len(list_runs(gateway)) == 1
