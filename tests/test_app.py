from streamlit.testing.v1 import AppTest
from pathlib import Path

def test_dashboard_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "ui.sqlite3"))
    # Keep dotenv from loading a developer's live key into this offline UI test.
    monkeypatch.setenv("OPENAI_API_KEY", "")
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=10).run()
    app.radio(key="navigation").set_value("Advanced Dashboard").run()
    assert not app.exception
    for label in ["01 · Safe invoice read", "02 · Block bank change", "03 · Review payment"]:
        next(b for b in app.button if b.label == label).click().run()
        next(b for b in app.button if b.label == "Run through gateway →").click().run()
        assert not app.exception
    assert app.metric[0].value == "3"
    assert app.metric[3].value == "1"
    next(b for b in app.button if b.label == "Approve once").click().run()
    assert not app.exception
    assert app.metric[3].value == "0"
    assert not any(b.label == "Approve once" for b in app.button)
    app.run()
    assert app.metric[0].value == "3"
