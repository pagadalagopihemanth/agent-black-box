from types import SimpleNamespace as NS
import pytest
from streaming import RunTrace, StreamingClient, TracedGateway, Cancelled

class Stream:
    def __init__(self, events):
        self.events, self.closed = events, False
    def __iter__(self):
        return iter(self.events)
    def close(self):
        self.closed = True

def test_sse_only_public_completed_data():
    trace = RunTrace()
    final = NS(usage=NS(total_tokens=10))
    stream = Stream([NS(type="response.reasoning_text.delta", delta="private reasoning"),
        NS(type="response.function_call_arguments.delta", delta="123456789"),
        NS(type="response.output_text.done", text="Account 123456789 blocked."),
        NS(type="response.completed", response=final)])
    client = NS(responses=NS(create=lambda **kwargs: stream))
    assert StreamingClient(client, trace).create(model="gpt-6.1-sol") is final
    assert stream.closed
    assert "123456789" not in str(trace.snapshot())
    assert "private reasoning" not in str(trace.snapshot())

def test_cancel_prevents_gateway(gateway):
    trace = RunTrace()
    trace.cancel.set()
    with pytest.raises(Cancelled):
        TracedGateway(gateway, trace).propose("read", "read_invoice", {"invoice_id": "INV-1001"})
    assert gateway.history() == []

def test_incomplete_stream_closes():
    stream = Stream([])
    client = NS(responses=NS(create=lambda **kwargs: stream))
    with pytest.raises(RuntimeError):
        StreamingClient(client, RunTrace()).create()
    assert stream.closed

def test_trace_uses_gateway(gateway):
    trace = RunTrace()
    row = TracedGateway(gateway, trace).propose("Approve PAY-202 for 15000 USD", "approve_payment", {"payment_id": "PAY-202", "amount": 15000, "currency": "USD"})
    assert row["execution"] == "pending"
    assert any(e["event"] == "approval_pending" for e in trace.snapshot())
