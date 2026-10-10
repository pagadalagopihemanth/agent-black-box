"""Synthetic Event Simulator with durable at-most-once claims, not MCP Events."""
import re
import sqlite3
from policy_engine import evaluate

KINDS = {"invoice-created": "read_invoice", "ticket-updated": "read_ticket", "payment-requested": "approve_payment"}

def dispatch_event(gateway, event_id, kind, payload, runner):
    if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", event_id):
        raise ValueError("Invalid event ID")
    tool = KINDS.get(kind, "invalid_event")
    policy = evaluate(tool, payload)
    with gateway.connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS incoming_events (id TEXT PRIMARY KEY, kind TEXT, status TEXT, run_id TEXT)")
        c.execute("BEGIN IMMEDIATE")
        try:
            c.execute("INSERT INTO incoming_events VALUES (?,?,?,?)", (event_id, kind if kind in KINDS else "invalid", "claimed", None))
        except sqlite3.IntegrityError:
            return {"status": "duplicate", "event_id": event_id}
    if policy.decision == "BLOCK":
        row = gateway.propose("Invalid synthetic event payload", "invalid_event", {}, "event")
        with gateway.connect() as c:
            c.execute("UPDATE incoming_events SET status='blocked',run_id=? WHERE id=?", (row["id"], event_id))
        return {"status": "blocked", "event_id": event_id, "action_id": row["id"]}
    if tool == "read_invoice":
        request = f'Read invoice {payload["invoice_id"]} and show its details.'
    elif tool == "read_ticket":
        request = f'Read ticket {payload["ticket_id"]} and show its details.'
    else:
        request = f'Approve payment {payload["payment_id"]} for {payload["amount"]} USD.'
    try:
        result = runner(request, gateway)
        run_id = getattr(result, "id", None)
        with gateway.connect() as c:
            c.execute("UPDATE incoming_events SET status=?,run_id=? WHERE id=?", ("running" if run_id and not getattr(result, "done", False) else "completed", run_id, event_id))
        return {"status": "started", "event_id": event_id, "run_id": run_id, "result": result}
    except Exception:
        with gateway.connect() as c:
            c.execute("UPDATE incoming_events SET status='failed' WHERE id=?", (event_id,))
        raise RuntimeError("Event workflow failed safely; event remains claimed and will not replay.") from None

def event_history(gateway):
    with gateway.connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS incoming_events (id TEXT PRIMARY KEY, kind TEXT, status TEXT, run_id TEXT)")
        return [dict(r) for r in c.execute("SELECT * FROM incoming_events ORDER BY rowid DESC")]
