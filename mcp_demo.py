"""Actual local stdio MCP handshake, discovery, and three secured calls."""
import asyncio
import os
import sys
from pathlib import Path

async def exchange(db_path):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
    # Never pass the API key to the synthetic MCP child process.
    env = {k: v for k, v in os.environ.items() if k.upper() in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC")}
    env["AUDIT_DB_PATH"] = str(Path(db_path).resolve())
    params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).parent / "mcp_server.py")], env=env)
    async with Client(params) as client:
        tools = await client.list_tools()
        records = []
        for name, args in [("invoice_lookup", {"invoice_id": "INV-1001"}), ("ticket_lookup", {"ticket_id": "TKT-101"}),
                           ("payment_proposal", {"payment_id": "PAY-MCP", "amount": 15000, "currency": "USD"})]:
            result = await client.call_tool(name, args)
            if result.is_error:
                raise RuntimeError("MCP tool exchange failed")
            if not isinstance(result.structured_content, dict) or result.structured_content.get("decision") not in ("ALLOW", "BLOCK", "REVIEW"):
                raise RuntimeError("Untrusted MCP response missing a gateway decision")
            from database import Gateway
            records.append(Gateway(db_path).get(result.structured_content["id"]))
        return {"status": "Connected and tested (session now closed)", "transport": "MCP stdio subprocess",
                "protocol": client.protocol_version, "tools": [t.name for t in tools.tools], "records": records}

def run_demo(db_path):
    return asyncio.run(asyncio.wait_for(exchange(db_path), timeout=20))

if __name__ == "__main__":
    import json
    print(json.dumps(run_demo("data/audit.sqlite3"), indent=2))
