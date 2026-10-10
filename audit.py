"""Conservative redaction at every persistence and display boundary."""
import json
import re
import math
import os

def redact_text(value):
    secret = os.getenv("OPENAI_API_KEY", "")
    value = str(value).replace(secret, "[REDACTED SECRET]") if secret else str(value)
    value = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED SECRET]", str(value))
    # Preserve standard internal UUID identifiers while masking account-like digit sequences.
    identifiers = []
    def protect(match):
        identifiers.append(match.group())
        return f"UUIDTOKEN{chr(65 + len(identifiers) - 1)}END"
    value = re.sub(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", protect, value)
    value = re.sub(r"\d(?:[\d -]{5,}\d)", "[REDACTED NUMBER]", value)
    for index, identifier in enumerate(identifiers):
        value = value.replace(f"UUIDTOKEN{chr(65 + index)}END", identifier)
    return value

def safe_args(tool, args):
    if not isinstance(args, dict):
        return {"invalid_arguments": "[REDACTED]"}
    allowed = {"read_invoice": {"invoice_id"}, "read_ticket": {"ticket_id"}, "approve_payment": {"payment_id", "amount", "currency"}, "update_supplier_bank_account": {"supplier_id"}}.get(tool, set()) if isinstance(tool, str) else set()
    return {k: (redact_text(v) if isinstance(v, str) else v if type(v) in (int, float) and abs(v) <= 1e12 and math.isfinite(v) else "[REDACTED]") if k in allowed else "[REDACTED]" for k, v in args.items() if k in allowed} | ({"bank_account": "[REDACTED]"} if tool == "update_supplier_bank_account" else {})

def export_json(rows):
    return json.dumps(rows, indent=2, ensure_ascii=False, allow_nan=False)
