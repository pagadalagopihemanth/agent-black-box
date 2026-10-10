"""Local Tool Registry Search; visibility never grants execution permission."""
import copy
from agent import TOOLS

def search(query="", permissions=None):
    permissions = {t["name"] for t in TOOLS} if permissions is None else set(permissions)
    words = query.lower().replace("_", " ").split()
    return [dict(schema=copy.deepcopy(t), name=t["name"], description=t["description"],
                 policy="Always BLOCK" if t["name"] == "update_supplier_bank_account" else "Deterministic validation; payments above USD 10,000 REVIEW")
            for t in TOOLS if t["name"] in permissions and all(w in (t["name"] + " " + t["description"]).lower().replace("_", " ") for w in words)]
