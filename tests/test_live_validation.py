from live_validation import safe_error

def test_live_diagnostic_redacts_credentials(monkeypatch):
    secret = "sk-proj-private_example_key"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    error = RuntimeError("Authentication failed for " + secret)
    result = safe_error(error)
    assert result["type"] == "RuntimeError"
    assert result["message"] == "Authentication failed for [REDACTED SECRET]"
    assert secret not in str(result)
