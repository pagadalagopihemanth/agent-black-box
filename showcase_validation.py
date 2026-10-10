"""Small controlled real integrations; output never includes raw streamed payloads."""
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from openai import OpenAI
from database import Gateway
from streaming import RunTrace, execute_streaming
from demo import demo_event
from specialists import analyze
from native_features import native_search, native_compact
from hosted_agent import run_hosted_demo
from live_validation import safe_error

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hosted-only", action="store_true")
    parser.add_argument("--compact-roundtrip", action="store_true")
    options = parser.parse_args()
    load_dotenv(Path(__file__).parent / ".env", override=True)
    client = OpenAI(timeout=30, max_retries=0)
    gateway = Gateway("data/showcase-validation.sqlite3")
    if options.compact_roundtrip:
        path = Path("data/live-showcase.json")
        report = json.loads(path.read_text()) if path.exists() else {}
        try:
            compact = native_compact(gateway.history(), [], client)
            from agent import run_agent
            result = run_agent("Read invoice INV-1001 and show its details.", gateway, client=client, context=compact["context"])
            passed = len(result["actions"]) == 1 and result["actions"][0]["decision"] == "ALLOW" and result["actions"][0]["execution"] == "completed"
            report["Native compaction roundtrip"] = {"passed": passed, "method": compact["method"], "original_chars": compact["original_chars"], "compressed_chars": compact["compressed_chars"]}
        except Exception as error:
            report["Native compaction roundtrip"] = {"passed": False, "error": safe_error(error)}
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report["Native compaction roundtrip"], indent=2))
        return 0 if report["Native compaction roundtrip"]["passed"] else 1
    if options.hosted_only:
        path = Path("data/live-showcase.json")
        report = json.loads(path.read_text()) if path.exists() else {}
        try:
            result = run_hosted_demo(gateway)
            report["Hosted Agents API"] = {"passed": bool(result["actions"]), "method": result["method"], "status": result["status"]}
        except Exception as error:
            report["Hosted Agents API"] = {"passed": False, "error": safe_error(error)}
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report["Hosted Agents API"], indent=2))
        return 0 if report["Hosted Agents API"]["passed"] else 1
    report = {"verified_at": datetime.now(timezone.utc).isoformat()}
    trace = RunTrace()
    def runner(request, g):
        execute_streaming(request, g, trace, client=client)
        return trace
    # Unique event ID per validation run; no approval is granted by this script.
    from events import dispatch_event
    dispatch_event(gateway, trace.id, "payment-requested", {"payment_id": "PAY-202", "amount": 15000, "currency": "USD"}, runner)
    report["Streaming + synthetic event"] = {"passed": bool(trace.result and len(trace.result["actions"]) == 1 and trace.result["actions"][0]["decision"] == "REVIEW"),
        "trace": trace.snapshot(), "action_ids": [r["id"] for r in (trace.result or {}).get("actions", [])]}
    for role in ("Policy Advisor", "Audit Analyst"):
        result = analyze(role, gateway.history(), client=client)
        report[role] = {"passed": result["success"], "method": result["method"], "usage": result.get("usage")}
    for name, callback in [("Native tool search", lambda: native_search("invoice", {"read_invoice"}, client)),
        ("Native compaction", lambda: native_compact(gateway.history(), [trace.id], client)),
        ("Hosted Agents API", lambda: run_hosted_demo(gateway))]:
        try:
            result = callback()
            report[name] = {"passed": bool(result.get("actions")) if name == "Hosted Agents API" else True,
                "method": result["method"], "status": result.get("status", "Completed")}
        except Exception as error:
            report[name] = {"passed": False, "error": safe_error(error)}
        print(json.dumps({name: report[name]}, indent=2), flush=True)
    with gateway.connect() as c:
        report["No payment execution"] = c.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0
    Path("data/live-showcase.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["Streaming + synthetic event"]["passed"] and report["No payment execution"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
