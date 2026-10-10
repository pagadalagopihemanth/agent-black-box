"""Explicit, bounded real-API smoke test. Never prints credentials or raw arguments."""
import json
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from openai import OpenAI
from agent import PRESETS, run_agent
from database import Gateway
from audit import redact_text

def safe_error(error):
    message = str(error)
    secret = os.getenv("OPENAI_API_KEY", "")
    if secret:
        message = message.replace(secret, "[REDACTED SECRET]")
    response = getattr(error, "response", None)
    detail = None
    if response is not None:
        try:
            body = response.json().get("error", {})
            if isinstance(body, dict):
                detail = {k: redact_text(str(body[k]).replace(secret, "[REDACTED SECRET]") if secret else body[k]) for k in ("message", "type", "code", "param") if k in body}
        except Exception:
            pass
    return {"type": type(error).__name__, "status_code": getattr(error, "status_code", getattr(response, "status_code", None)), "message": redact_text(message), **({"api_error": detail} if detail else {})}

class ObservedClient:
    def __init__(self, client):
        self.client = client
        self.responses = self
        self.calls = []
        self.errors = []

    def create(self, **kwargs):
        try:
            response = self.client.responses.create(**kwargs)
        except Exception as error:
            self.errors.append(safe_error(error))
            raise
        self.calls.append({"model": response.model, "status": response.status,
            "usage": response.usage.model_dump() if response.usage else None,
            "proposed_tools": [c.name for c in response.output if c.type == "function_call"],
            "tool_results_sent": sum(isinstance(i, dict) and i.get("type") == "function_call_output" for i in kwargs.get("input", []))})
        return response

def main():
    parser = argparse.ArgumentParser(description="Run explicit live integration tests with secret-safe output.")
    parser.add_argument("--env-file", type=Path, default=Path(__file__).parent / ".env")
    options = parser.parse_args()
    load_dotenv(options.env_file, override=True)
    model = os.getenv("OPENAI_MODEL", "")
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "configured_model": model, "mode": "live", "scenarios": []}
    if model != "gpt-6.1-sol" or not os.getenv("OPENAI_API_KEY"):
        report["configuration_error"] = "Local .env must configure OPENAI_API_KEY and OPENAI_MODEL=gpt-6.1-sol. No fallback used."
        print(json.dumps(report, indent=2))
        return 1
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url="https://api.openai.com/v1", timeout=45, max_retries=0)
    try:
        response = client.responses.create(model=model, input="Reply with OK.", max_output_tokens=128,
            reasoning={"effort": "low"}, service_tier="default", store=False)
        report["connectivity"] = {"authentication": "succeeded", "model_access": "succeeded", "model": response.model,
            "status": response.status, "usage": response.usage.model_dump() if response.usage else None}
    except Exception as error:
        report["connectivity"] = {"authentication_and_access": "not_verified", "error": safe_error(error)}
        print(json.dumps({"connectivity": report["connectivity"]}, indent=2), flush=True)
    gateway = Gateway(Path(__file__).parent / "data/audit.sqlite3")
    expected = [("read_invoice", "ALLOW", "completed"), ("update_supplier_bank_account", "BLOCK", "prevented"), ("approve_payment", "REVIEW", "pending")]
    for request, (tool, decision, execution) in zip(PRESETS[:3], expected):
        observed = ObservedClient(client)
        result = run_agent(request, gateway, offline=False, client=observed, model=model)
        ids = [r["id"] for r in result["actions"]]
        records = [gateway.get(i) for i in ids]
        with gateway.connect() as c:
            payment_effects = c.execute("SELECT COUNT(*) FROM payments WHERE action_id IN (%s)" % (",".join("?" for _ in ids) or "NULL"), ids).fetchone()[0]
        tools = [t for call in observed.calls for t in call["proposed_tools"]]
        passed = (len(records) == 1 and tools == [tool] and records[0]["decision"] == decision and records[0]["execution"] == execution
            and records[0]["source"] == "live" and payment_effects == 0 and not observed.errors
            and any(call["tool_results_sent"] > 0 for call in observed.calls))
        item = {"expected_tool": tool, "passed": passed, "real_api_calls": observed.calls, "errors": observed.errors,
            "audit": [{k: row[k] for k in ("id", "tool", "decision", "approval", "execution", "source", "events")} for row in records],
            "payment_effects": payment_effects}
        report["scenarios"].append(item)
        print(json.dumps(item, indent=2), flush=True)
    report["passed"] = report.get("connectivity", {}).get("model_access") == "succeeded" and all(s["passed"] for s in report["scenarios"])
    Path("data/live-validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "connectivity": report["connectivity"], "report": "data/live-validation.json"}, indent=2))
    return 0 if report["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
