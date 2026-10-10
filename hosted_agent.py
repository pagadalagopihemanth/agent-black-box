"""Optional documented Agents API REST session adapter; environment=none."""
import json
import os
import re
import time
import httpx
from database import fingerprint
from agent import SYSTEM, TOOLS
from audit import redact_text

def handle_action(gateway, session_id, action):
    if not isinstance(action, dict) or action.get("type") != "function_call":
        raise ValueError("Not a pending function action")
    key = [session_id, action.get("turn_id"), action.get("call_id")]
    if not all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", v) for v in key):
        raise ValueError("Invalid hosted action binding")
    request_hash = fingerprint(action.get("name"), action.get("arguments"))
    with gateway.connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS hosted_calls (session_id TEXT, turn_id TEXT, call_id TEXT, action_id TEXT, PRIMARY KEY(session_id,turn_id,call_id))")
        if "request_hash" not in {r["name"] for r in c.execute("PRAGMA table_info(hosted_calls)")}:
            c.execute("ALTER TABLE hosted_calls ADD COLUMN request_hash TEXT")
        c.execute("BEGIN IMMEDIATE")
        existing = c.execute("SELECT action_id,request_hash FROM hosted_calls WHERE session_id=? AND turn_id=? AND call_id=?", key).fetchone()
        if existing:
            if existing["request_hash"] != request_hash:
                raise ValueError("Hosted call arguments changed; cached action cannot be reused")
            if not existing["action_id"]:
                raise ValueError("Hosted action claimed; execution outcome requires reconciliation")
            return gateway.get(existing["action_id"])
        c.execute("INSERT INTO hosted_calls(session_id,turn_id,call_id,action_id,request_hash) VALUES (?,?,?,NULL,?)", [*key, request_hash])
    args = action.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = None
    row = gateway.propose("Hosted Agents API synthetic invoice demonstration", action.get("name"), args, "hosted_agents")
    with gateway.connect() as c:
        c.execute("UPDATE hosted_calls SET action_id=? WHERE session_id=? AND turn_id=? AND call_id=?", [row["id"], *key])
    return row

def run_hosted_demo(gateway, transport=None):
    if os.getenv("OPENAI_MODEL") != "gpt-6.1-sol":
        raise ValueError("Hosted demonstration requires configured gpt-6.1-sol")
    headers = {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "OpenAI-Beta": "agents=v1"}
    records, session_id = [], None
    with httpx.Client(base_url="https://api.openai.com/v1", headers=headers, timeout=25, transport=transport) as client:
        # Only read-only invoice tool advertised. No hosted sandbox or computer tools.
        response_tool = next(t for t in TOOLS if t["name"] == "read_invoice")
        # Hosted Agents function schema documents these fields; Responses-only strict is not accepted.
        tool = {k: response_tool[k] for k in ("type", "name", "description", "parameters")}
        started = time.monotonic()
        with client.stream("POST", "/agents/sessions", json={"agent": {"model": "gpt-6.1-sol", "instructions": SYSTEM, "tools": [tool]},
             "environment": {"type": "none"}, "input": "Read synthetic invoice INV-1001 using read_invoice, then summarize the authorized result.", "stream": True}) as response:
            if response.is_error:
                response.read()
            response.raise_for_status()
            for count, line in enumerate(response.iter_lines()):
                if count > 1000 or time.monotonic() - started > 45:
                    raise RuntimeError("Hosted session event budget exceeded")
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except ValueError:
                    continue
                session = event.get("session", {})
                session_id = session.get("id", session_id)
                if event.get("type") == "agent.session.requires_action":
                    if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
                        raise ValueError("Invalid hosted session identifier")
                    actions = session.get("required_actions", [])
                    if len(actions) > 3:
                        raise RuntimeError("Hosted tool budget exceeded")
                    for action in actions:
                        row = handle_action(gateway, session_id, action)
                        records.append(row)
                        result = {"type": "agent.session.input.tool_result", "turn_id": action["turn_id"], "call_id": action["call_id"],
                                  "success": True, "output": json.dumps({k: row[k] for k in ("id", "decision", "execution", "result")})}
                        submitted = client.post(f"/agents/sessions/{session_id}/events", json={"events": [result]})
                        submitted.raise_for_status()
                    break
        return {"method": "Hosted Agents API · official REST sessions + tool-result events · environment none", "session_id": redact_text(session_id),
                "status": "Function result submitted" if records else "Session returned no pending tool action", "actions": records}
