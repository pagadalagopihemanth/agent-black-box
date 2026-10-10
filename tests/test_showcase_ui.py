from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_guided_demo_single_delivery_and_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "normal.sqlite3"))
    monkeypatch.setattr("demo.DEMO_DB", tmp_path / "demo.sqlite3")
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=15).run()
    app.radio(key="navigation").set_value("Advanced Dashboard").run()
    assert len(app.tabs) == 10 and not app.exception
    assert app.tabs[-1].label == "AI Risk Intelligence"
    next(t for t in app.toggle if t.label.startswith("Demo Mode")).set_value(True).run()
    next(b for b in app.button if b.label == "Start guided payment event").click().run()
    assert app.metric[0].value == "1" and app.metric[3].value == "1"
    next(b for b in app.button if b.label == "Start guided payment event").click().run()
    assert app.metric[0].value == "1"
    next(b for b in app.button if b.label == "Reject").click().run()
    assert app.metric[3].value == "0"
    next(b for b in app.button if b.label == "Run Audit Analyst").click().run()
    assert not app.exception
    next(b for b in app.button if b.label == "Reset Demo").click().run()
    assert app.metric[0].value == "0" and not app.exception
