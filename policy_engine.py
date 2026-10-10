"""Deterministic, fail-closed authorization. Never trust model arguments."""
from dataclasses import dataclass
import math
import re

@dataclass(frozen=True)
class Decision:
    decision: str
    reason: str

FIELDS = {
    "read_invoice": {"invoice_id"},
    "read_ticket": {"ticket_id"},
    "update_supplier_bank_account": {"supplier_id", "bank_account"},
    "approve_payment": {"payment_id", "amount", "currency"},
}

def evaluate(tool, args):
    block = lambda reason: Decision("BLOCK", reason)
    if not isinstance(tool, str) or tool not in FIELDS:
        return block("Unknown tool; deny by default.")
    if not isinstance(args, dict) or set(args) != FIELDS[tool]:
        return block("Arguments must contain exactly the required fields.")
    id_key = {"read_invoice": "invoice_id", "read_ticket": "ticket_id", "approve_payment": "payment_id", "update_supplier_bank_account": "supplier_id"}[tool]
    prefix = {"invoice_id": "INV", "ticket_id": "TKT", "payment_id": "PAY", "supplier_id": "SUP"}[id_key]
    if not isinstance(args[id_key], str) or not re.fullmatch(prefix + r"-[A-Z0-9]{1,32}", args[id_key]):
        return block("Invalid record identifier.")
    if tool == "update_supplier_bank_account":
        return block("Supplier banking changes are permanently prohibited.")
    if tool == "read_invoice":
        return Decision("ALLOW", "Read-only access to synthetic invoice data.")
    if tool == "read_ticket":
        return Decision("ALLOW", "Read-only access to synthetic ticket data.")
    amount = args["amount"]
    if type(amount) not in (int, float) or amount <= 0 or amount > 1e12 or not math.isfinite(amount):
        return block("Amount must be a finite positive number within the demo limit.")
    if round(amount, 2) != amount:
        return block("Amount must have at most two decimal places.")
    if args["currency"] != "USD":
        return block("Only USD is supported; no currency conversion.")
    if amount > 10000:
        return Decision("REVIEW", "Payment exceeds USD 10,000; explicit human approval required.")
    return Decision("ALLOW", "Valid USD payment within the USD 10,000 policy threshold.")
