"""Local MCP protocol server. No approval endpoint or unrestricted executor."""
import os
from typing import Any
from database import Gateway

def build_server(db_path=None):
    from mcp.server import MCPServer
    server = MCPServer("Agent Black Box Synthetic Gateway")
    path = db_path or os.getenv("AUDIT_DB_PATH", "data/audit.sqlite3")

    @server.tool(structured_output=True)
    def invoice_lookup(invoice_id: str) -> dict[str, Any]:
        """Synthetic invoice lookup through deterministic authorization."""
        return Gateway(path).propose("MCP synthetic invoice lookup", "read_invoice", {"invoice_id": invoice_id}, "mcp")

    @server.tool(structured_output=True)
    def ticket_lookup(ticket_id: str) -> dict[str, Any]:
        """Synthetic support-ticket lookup through deterministic authorization."""
        return Gateway(path).propose("MCP synthetic ticket lookup", "read_ticket", {"ticket_id": ticket_id}, "mcp")

    @server.tool(structured_output=True)
    def payment_proposal(payment_id: str, amount: Any, currency: str) -> dict[str, Any]:
        """Propose a synthetic payment. Gateway may block or require human review."""
        return Gateway(path).propose("MCP synthetic payment proposal", "approve_payment", {"payment_id": payment_id, "amount": amount, "currency": currency}, "mcp")
    return server

if __name__ == "__main__":
    build_server().run()
