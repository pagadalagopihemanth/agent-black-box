from registry import search

def test_discovery_respects_permissions():
    assert [r["name"] for r in search("invoice", {"read_invoice"})] == ["read_invoice"]
    assert search("", set()) == []
    assert search("bank", {"read_invoice"}) == []
    assert all(r["name"] != "exec" for r in search("exec"))
    assert search("nonexistent_tool") == []

def test_discovery_cannot_mutate_allowlist():
    rows = search("invoice")
    rows[0]["schema"]["name"] = "exec"
    assert search("invoice")[0]["name"] == "read_invoice"
