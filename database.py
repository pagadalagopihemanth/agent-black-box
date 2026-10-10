"""SQLite transactions bind approval, execution, and audit updates atomically."""
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from audit import redact_text, safe_args
from policy_engine import evaluate
from mock_tools import _execute

def fingerprint(tool, args):
    return hashlib.sha256(json.dumps([tool, args], sort_keys=True, allow_nan=False).encode()).hexdigest()

class Gateway:
    def __init__(self, path="data/audit.sqlite3"):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY, timestamp TEXT, request TEXT, tool TEXT,
                arguments TEXT, digest TEXT, decision TEXT, reason TEXT,
                approval TEXT, execution TEXT, result TEXT, source TEXT);
                CREATE TABLE IF NOT EXISTS payments (
                action_id TEXT PRIMARY KEY, payment_id TEXT, amount REAL, currency TEXT);
                CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, action_id TEXT, timestamp TEXT, event TEXT);''')

    def connect(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        return c

    def _event(self, c, action_id, event):
        c.execute("INSERT INTO events(action_id,timestamp,event) VALUES (?,?,?)", (action_id, datetime.now(timezone.utc).isoformat(), event))

    def propose(self, request, tool, args, source="offline"):
        decision = evaluate(tool, args)
        action_id = str(uuid.uuid4())
        # Persist executable arguments only for valid allowed/review operations.
        stored = args if decision.decision != "BLOCK" else safe_args(tool, args)
        if decision.decision != "BLOCK":
            stored = safe_args(tool, stored)
            # IDs/amounts already validated: redaction must not change approved arguments.
            if stored != args:
                decision = type(decision)("BLOCK", "Sensitive-looking arguments cannot be persisted safely.")
        digest = fingerprint(tool, stored)
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                action_id, datetime.now(timezone.utc).isoformat(), redact_text(request), redact_text(tool),
                json.dumps(stored, allow_nan=False), digest, decision.decision, decision.reason,
                "pending" if decision.decision == "REVIEW" else "not_required", "pending" if decision.decision == "REVIEW" else "prevented", "{}", source))
            self._event(c, action_id, "Policy: " + decision.decision)
            if decision.decision == "ALLOW":
                self._run(c, action_id, tool, args)
        return self.get(action_id)

    def _run(self, c, action_id, tool, args):
        c.execute("SAVEPOINT tool_execution")
        try:
            result = _execute(tool, args, c, action_id)
            execution = "failed" if "error" in result else "completed"
            c.execute("RELEASE tool_execution")
        except Exception:
            c.execute("ROLLBACK TO tool_execution")
            c.execute("RELEASE tool_execution")
            result, execution = {"error": "Simulation failed; no operation committed."}, "failed"
        c.execute("UPDATE actions SET execution=?,result=? WHERE id=?", (execution, json.dumps(result), action_id))
        self._event(c, action_id, "Execution: " + execution)

    def resolve(self, action_id, approve, expected_digest):
        if type(approve) is not bool:
            raise ValueError("Approval must be an explicit boolean")
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if not row or row["approval"] != "pending" or row["execution"] != "pending":
                raise ValueError("Request is not pending; approval is single-use.")
            args = json.loads(row["arguments"])
            policy = evaluate(row["tool"], args)
            valid = expected_digest == row["digest"] == fingerprint(row["tool"], args) and policy.decision == "REVIEW" and row["decision"] == "REVIEW"
            status = "approved" if approve and valid else "rejected"
            c.execute("UPDATE actions SET approval=?,execution=? WHERE id=?", (status, "prevented", action_id))
            self._event(c, action_id, "Human: " + status + (" (revalidation failed)" if not valid else ""))
            if status == "approved":
                self._run(c, action_id, row["tool"], args)
        return self.get(action_id)

    def get(self, action_id):
        return next(r for r in self.history() if r["id"] == action_id)

    def history(self):
        with self.connect() as c:
            rows = [dict(r) for r in c.execute("SELECT * FROM actions ORDER BY timestamp DESC")]
            for r in rows:
                r["arguments"] = json.loads(r["arguments"])
                r["result"] = json.loads(r["result"])
                r["events"] = [dict(e) for e in c.execute("SELECT timestamp,event FROM events WHERE action_id=? ORDER BY id", (r["id"],))]
        return rows
