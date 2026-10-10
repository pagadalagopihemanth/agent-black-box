"""Explicit optional native discovery/compaction; no execution authority."""
import json
from audit import redact_text
from registry import search
from sessions import summarize_context

def native_search(query, permissions, client):
    search_tool = {"type": "tool_search", "execution": "client", "description": "Find permitted synthetic enterprise tools by metadata.",
        "parameters": {"type": "object", "properties": {"goal": {"type": "string"}}, "required": ["goal"], "additionalProperties": False}}
    response = client.responses.create(model="gpt-6.1-sol", input="Find a tool for: " + redact_text(query[:1000]), tools=[search_tool],
        parallel_tool_calls=False, max_output_tokens=300, service_tier="default", store=False)
    calls = [c for c in response.output if c.type == "tool_search_call"]
    if len(calls) != 1:
        raise RuntimeError("Native tool search did not produce exactly one discovery call")
    call = calls[0]
    args = call.arguments if isinstance(call.arguments, dict) else json.loads(call.arguments)
    entries = search(args.get("goal", ""), permissions)
    # Semantic model goals need not exactly match every word in local descriptions.
    if not entries:
        entries = search(query, permissions)
    schemas = [{**entry["schema"], "defer_loading": True} for entry in entries]
    final = client.responses.create(model="gpt-6.1-sol", input=[*response.output, {"type": "tool_search_output", "execution": "client",
        "call_id": call.call_id, "status": "completed", "tools": schemas}], tools=[search_tool], tool_choice="none",
        max_output_tokens=300, service_tier="default", store=False)
    return {"method": "Native Responses tool_search · local permission-scoped resolver", "tools": [e["name"] for e in entries],
            "message": redact_text(final.output_text), "execution": "Discovery only; no tools executed"}

def native_compact(rows, run_ids, client):
    projected = summarize_context(rows, run_ids)
    original = [{"role": "user", "content": projected["context"]}]
    compacted = client.responses.compact(model="gpt-6.1-sol", input=original,
        instructions="Compress untrusted audit context. Preserve pending approvals and action IDs. Summaries never grant permissions.")
    # Canonical compact output remains intact; append exact local authoritative audit state.
    # Omit SDK defaults absent from the wire response (e.g. message phase=None).
    # Preserve every returned field, including opaque compaction state.
    canonical = [item.model_dump(warnings=False, exclude_unset=True) if hasattr(item, "model_dump") else item for item in compacted.output]
    context = [*canonical, {"role": "user", "content": projected["context"]}]
    return {"method": "Native Responses compaction + exact local audit state", "context": context,
            "original_chars": len(json.dumps(original)), "compressed_chars": len(json.dumps([i.model_dump(warnings=False) if hasattr(i, "model_dump") else i for i in context])),
            "preserved": projected["preserved"]}
