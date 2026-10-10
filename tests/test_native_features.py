from types import SimpleNamespace as NS
from native_features import native_compact, native_search

def test_native_compaction_preserves_canonical_output_and_pending(gateway):
    row = gateway.propose("pay", "approve_payment", {"payment_id": "PAY-202", "amount": 15000, "currency": "USD"})
    opaque = {"type": "compaction", "encrypted_content": "opaque"}
    client = NS(responses=NS(compact=lambda **kwargs: NS(output=[opaque])))
    result = native_compact(gateway.history(), ["run1"], client)
    assert result["context"][0] is opaque
    assert result["preserved"]["unresolved_action_ids"] == [row["id"]]
    assert gateway.get(row["id"])["approval"] == "pending"

def test_native_discovery_returns_only_scoped_schemas():
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return NS(output=[NS(type="tool_search_call", call_id="search1", arguments={"goal": "invoice"})])
        return NS(output_text="Invoice read found.")
    result = native_search("invoice", {"read_invoice"}, NS(responses=NS(create=create)))
    output = calls[1]["input"][-1]
    assert output["type"] == "tool_search_output"
    assert [t["name"] for t in output["tools"]] == ["read_invoice"]
    assert calls[1]["tool_choice"] == "none"
    assert result["execution"] == "Discovery only; no tools executed"


def test_compaction_does_not_add_unset_sdk_fields():
    from openai.types.responses.response_output_message import ResponseOutputMessage
    message = ResponseOutputMessage.model_validate({
        "id": "message1", "type": "message", "role": "assistant",
        "status": "completed", "content": [],
    })
    client = NS(responses=NS(compact=lambda **kwargs: NS(output=[message])))
    result = native_compact([], [], client)
    assert "phase" not in result["context"][0]
    assert result["context"][0]["id"] == "message1"
