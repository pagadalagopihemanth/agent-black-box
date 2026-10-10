from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from audit import export_json

def pending(gateway):
    return gateway.propose("Approve PAY-202 for 15000 USD", "approve_payment", {"payment_id": "PAY-202", "amount": 15000, "currency": "USD"})

def payments(gateway):
    with gateway.connect() as c:
        return c.execute("SELECT COUNT(*) FROM payments").fetchone()[0]

def test_pending_and_approval(gateway):
    row = pending(gateway)
    assert row["execution"] == "pending" and payments(gateway) == 0
    row = gateway.resolve(row["id"], True, row["digest"])
    assert row["approval"] == "approved" and row["execution"] == "completed"
    assert payments(gateway) == 1
    with pytest.raises(ValueError):
        gateway.resolve(row["id"], True, row["digest"])
    assert payments(gateway) == 1
    assert len(row["events"]) == 3

def test_rejection(gateway):
    row = pending(gateway)
    assert gateway.resolve(row["id"], False, row["digest"])["approval"] == "rejected"
    with pytest.raises(ValueError):
        gateway.resolve(row["id"], True, row["digest"])
    assert payments(gateway) == 0

def test_bound_approval(gateway):
    row = pending(gateway)
    assert gateway.resolve(row["id"], True, "wrong digest")["approval"] == "rejected"
    assert payments(gateway) == 0

def test_tampered_arguments(gateway):
    row = pending(gateway)
    with gateway.connect() as c:
        c.execute("UPDATE actions SET arguments=? WHERE id=?", (json.dumps({"payment_id": "PAY-OTHER", "amount": 15000, "currency": "USD"}), row["id"]))
    assert gateway.resolve(row["id"], True, row["digest"])["approval"] == "rejected"
    assert payments(gateway) == 0

def test_prohibited_cannot_be_approved(gateway):
    row = gateway.propose("Set bank account 123456789", "update_supplier_bank_account", {"supplier_id": "SUP-101", "bank_account": "123456789"})
    with pytest.raises(ValueError):
        gateway.resolve(row["id"], True, row["digest"])
    assert "123456789" not in export_json(gateway.history())
    assert "[REDACTED]" in export_json(gateway.history())

def test_concurrent_approval(gateway):
    row = pending(gateway)
    def approve(_):
        try:
            return gateway.resolve(row["id"], True, row["digest"])["execution"]
        except ValueError:
            return "consumed"
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(approve, range(2))) == ["completed", "consumed"]
    assert payments(gateway) == 1

def test_persisted(gateway):
    from database import Gateway
    row = pending(gateway)
    reopened = Gateway(gateway.path)
    assert reopened.get(row["id"])["approval"] == "pending"
    reopened.resolve(row["id"], False, row["digest"])
    assert gateway.get(row["id"])["approval"] == "rejected"

def test_unknown_and_invalid_audit(gateway):
    for args in [None, {"payment_id": "PAY-1", "amount": float("nan"), "currency": "USD"}]:
        gateway.propose("invalid", "approve_payment", args)
    gateway.propose("unknown", "unknown", {"password": "sk-secret"})
    gateway.propose("malformed tool name", [], {})
    assert all(r["decision"] == "BLOCK" for r in gateway.history())
    assert "sk-secret" not in export_json(gateway.history())

def test_tool_failure_rolls_back(gateway, monkeypatch):
    def fail(tool, args, c, action_id):
        c.execute("INSERT INTO payments VALUES (?,?,?,?)", (action_id, "PAY-1", 1, "USD"))
        raise RuntimeError("sensitive")
    monkeypatch.setattr("database._execute", fail)
    row = gateway.propose("Approve PAY-1 for 1 USD", "approve_payment", {"payment_id": "PAY-1", "amount": 1, "currency": "USD"})
    assert row["execution"] == "failed" and payments(gateway) == 0
