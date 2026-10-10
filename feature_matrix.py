"""Feature claims derived from saved real integration results, never presumed access."""
import json
from pathlib import Path
from capabilities import access_report

ANNOUNCEMENT = "https://openai.com/index/devday-2026-recap/"

def matrix():
    path = Path("data/live-showcase.json")
    verification = json.loads(path.read_text()) if path.exists() else {}
    decisions_path = Path("data/live-decisions.json")
    if decisions_path.exists():
        decisions = json.loads(decisions_path.read_text())
        verification["Decisions API"] = {"passed": decisions.get("success", False), **({"error": decisions["error"]} if decisions.get("error") else {})}
    access = access_report()
    definitions = [
        ("Streaming", "Streaming + synthetic event", "Responses SSE with redacted public trace", "Live API", True, "streaming-responses"),
        ("Multi-agent workflow", "Policy Advisor", "Application-managed Planner, Policy Advisor, Audit Analyst Responses calls", "Live API", True, "agents"),
        ("Tool registry", None, "Local Tool Registry Search with permission-scoped schemas", "Local implementation", False, "tools-tool-search"),
        ("Native tool search", "Native tool search", "Responses tool_search + local scoped resolver; discovery only", "Live API", True, "tools-tool-search"),
        ("Context summary", None, "Application-level context summarizer; exact approval state retained", "Local implementation", False, "compaction"),
        ("Native compaction", "Native compaction", "responses.compact + exact authoritative local audit projection", "Live API", True, "compaction"),
        ("MCP tools", None, "Official MCP SDK 2.3, stdio subprocess, gateway-backed synthetic tools", "Local implementation", False, "tools-remote-mcp"),
        ("Event-driven workflow", "Streaming + synthetic event", "Synthetic Event Simulator with durable SQLite deduplication", "Simulated", False, "agents"),
        ("MCP Events", None, "Experimental extension not integrated", "Unavailable", True, "agents"),
        ("Hosted Agents API", "Hosted Agents API", "Official REST sessions and required-action/tool-result events; environment none", "Live API", True, "agents-api/overview"),
        ("Computer use", None, "Skipped; no isolated synthetic computer environment configured", "Unavailable", True, "tools-computer-use"),
        ("Decisions API", "Decisions API", "Official POST /v1/decisions REST · gpt-6-luna · advisory choice classification", "Live API", True, "decisions"),
    ]
    rows = []
    for name, key, method, status, required, guide in definitions:
        result = verification.get(key, {}) if key else {}
        if key and not result.get("passed"):
            status = "Unavailable" if "error" in result else "Not yet live-tested"
        test = "Live check passed" if result.get("passed") else "Live check failed" if result.get("error") else "Automated local tests" if status in ("Local implementation", "Simulated") else "Skipped / not enabled"
        rows.append({"Feature": name, "Implementation": method, "Status": status, "Last verified test": test,
                     "Verified at": verification.get("verified_at", access.get("verified_at", "Not verified")), "Account access required": required,
                     "Announcement": ANNOUNCEMENT, "Documentation": "https://developers.openai.com/api/docs/guides/" + guide})
    return rows
