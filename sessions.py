"""Application-level context summarizer. Audit records remain authoritative."""
import json
from audit import export_json

def summarize_context(rows, run_ids=()):
    original = export_json(rows)
    preserved = [{k: row[k] for k in ("id", "tool", "decision", "approval", "execution")} for row in rows]
    summary = {"method": "Application-level context summarizer", "authority": "History only; never permission or approval",
        "run_ids": list(run_ids), "actions": preserved,
        "unresolved_action_ids": [r["id"] for r in rows if r["approval"] == "pending" or r["execution"] in ("pending", "failed")]}
    compressed = json.dumps(summary)
    return {"original_chars": len(original), "compressed_chars": len(compressed), "preserved": summary, "context": compressed}

def save_run(gateway, trace):
    with gateway.connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, trace TEXT, action_ids TEXT)")
        c.execute("INSERT INTO runs VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET trace=excluded.trace,action_ids=excluded.action_ids", (trace.id, json.dumps(trace.snapshot()), json.dumps([r["id"] for r in (trace.result or {}).get("actions", [])])))
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='incoming_events'").fetchone():
            c.execute("UPDATE incoming_events SET status='completed' WHERE run_id=?", (trace.id,))

def list_runs(gateway):
    with gateway.connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, trace TEXT, action_ids TEXT)")
        return [{"id": r["id"], "trace": json.loads(r["trace"]), "action_ids": json.loads(r["action_ids"])} for r in c.execute("SELECT * FROM runs ORDER BY rowid DESC LIMIT 100")]
