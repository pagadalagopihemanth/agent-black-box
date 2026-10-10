from types import SimpleNamespace as NS
import capabilities


def test_access_check_skips_unsupported_sol_decisions(monkeypatch, tmp_path):
    calls = []
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def request(self, method, path, **kwargs):
            calls.append((method, path))
            return NS(status_code=200, is_success=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(capabilities.httpx, "Client", Client)
    report = capabilities.check_access()
    assert calls == [("GET", "/agents/sessions?limit=1")]
    assert "unsupported" in report["Decisions API"]["reason"]
    assert "synthetic-test-secret" not in (tmp_path / "data/capabilities.json").read_text()
