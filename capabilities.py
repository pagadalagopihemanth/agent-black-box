"""Bounded availability checks; import never makes network requests."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import httpx
from live_validation import safe_error

def check_access():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
    headers = {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}
    report = {"verified_at": datetime.now(timezone.utc).isoformat()}
    with httpx.Client(base_url="https://api.openai.com/v1", headers=headers, timeout=20) as client:
        for name, method, path, payload in [
            ("Agents API", "GET", "/agents/sessions?limit=1", None),
        ]:
            try:
                response = client.request(method, path, json=payload, headers={"OpenAI-Beta": "agents=v1"} if name == "Agents API" else None)
                # Never persist raw server messages or session data; status is sufficient for access checks.
                report[name] = {"http_status": response.status_code, "status": "Accessible; not enabled" if response.is_success else "Not enabled",
                    "reason": "SDK adapter missing" if response.is_success else "Access probe rejected for this project/configured model"}
            except Exception as error:
                report[name] = {"status": "Not enabled", "error": safe_error(error)}
    # October 2026 documentation supports only Luna for Decisions. Do not repeat
    # an unsupported Sol inference probe or silently change the configured model.
    report["Decisions API"] = {"status": "Not enabled", "reason": "Decisions supports only gpt-6-luna; configured gpt-6.1-sol is unsupported. No request made.",
        "documentation": "https://developers.openai.com/api/docs/guides/decisions"}
    report["Computer use"] = {"status": "Skipped", "reason": "No isolated computer-use environment configured; no desktop actions enabled"}
    report["MCP Events"] = {"status": "Not enabled", "reason": "Experimental trigger/event extension not integrated; synthetic event simulator used"}
    Path("data/capabilities.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

def access_report():
    path = Path("data/capabilities.json")
    report = json.loads(path.read_text()) if path.exists() else {"verified_at": "Not probed"}
    live_path = Path("data/live-showcase.json")
    live = json.loads(live_path.read_text()) if live_path.exists() else {}
    if live.get("Hosted Agents API", {}).get("passed"):
        report["Agents API"] = {**report.get("Agents API", {}), "status": "Enabled via optional REST adapter", "reason": "Live invoice session and gateway tool-result exchange passed; environment none"}
    decisions_path = Path("data/live-decisions.json")
    if decisions_path.exists():
        decisions = json.loads(decisions_path.read_text())
        report["Decisions API"] = {"status": "Available · optional advisory adapter" if decisions.get("success") else "Not enabled",
            "model": "gpt-6-luna", "http_status": decisions.get("http_status"), "reason": "Saved real Decisions classification check passed" if decisions.get("success") else "Saved Decisions check failed", "error": decisions.get("error")}
    return report

if __name__ == "__main__":
    print(json.dumps(check_access(), indent=2))
