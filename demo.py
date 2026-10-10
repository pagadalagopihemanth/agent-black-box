"""Demo reset is confined to a separate synthetic database."""
from pathlib import Path
from database import Gateway

DEMO_DB = Path(__file__).parent / "data/demo.sqlite3"

def reset_demo():
    gateway = Gateway(DEMO_DB)
    with gateway.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "incoming_events" in tables and c.execute("SELECT 1 FROM incoming_events WHERE status IN ('claimed','running')").fetchone():
            raise ValueError("Demo has an active or unresolved event; reset after it completes.")
        for table in ("payments", "events", "actions", "runs", "incoming_events", "hosted_calls"):
            if table in tables:
                c.execute(f"DELETE FROM {table}")

def demo_event(gateway, runner):
    from events import dispatch_event
    return dispatch_event(gateway, "guided-payment-event", "payment-requested", {"payment_id": "PAY-202", "amount": 15000, "currency": "USD"}, runner)
