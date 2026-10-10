import pytest
from policy_engine import evaluate

def test_invoice():
    assert evaluate("read_invoice", {"invoice_id": "INV-1001"}).decision == "ALLOW"

def test_bank():
    assert evaluate("update_supplier_bank_account", {"supplier_id": "SUP-101", "bank_account": "123456789"}).decision == "BLOCK"

@pytest.mark.parametrize("amount,decision", [(10000, "ALLOW"), (10000.01, "REVIEW"), (15000, "REVIEW"), (0, "BLOCK"), (-1, "BLOCK"), (True, "BLOCK"), ("15000", "BLOCK"), (None, "BLOCK"), (float("nan"), "BLOCK"), (float("inf"), "BLOCK"), (10**1000, "BLOCK"), (0.001, "BLOCK")])
def test_amount(amount, decision):
    assert evaluate("approve_payment", {"payment_id": "PAY-202", "amount": amount, "currency": "USD"}).decision == decision

@pytest.mark.parametrize("tool,args", [("exec", {}), (None, {}), ([], {}), ("read_invoice", None), ("read_invoice", {}), ("read_invoice", {"invoice_id": 123}), ("read_invoice", {"invoice_id": "INV-1", "extra": 1}), ("approve_payment", {"payment_id": "PAY-1", "amount": 1, "currency": "INR"})])
def test_fail_closed(tool, args):
    assert evaluate(tool, args).decision == "BLOCK"
