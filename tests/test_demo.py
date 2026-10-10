from demo import reset_demo
from database import Gateway

def test_reset_only_isolated_demo_data(tmp_path, monkeypatch, gateway):
    path = tmp_path / "demo.sqlite3"
    monkeypatch.setattr("demo.DEMO_DB", path)
    demo = Gateway(path)
    for g in (demo, gateway):
        g.propose("read", "read_invoice", {"invoice_id": "INV-1001"})
    reset_demo()
    assert demo.history() == []
    assert len(gateway.history()) == 1
