import asyncio
from mcp import Client
from mcp_server import build_server

def test_mcp_protocol_gateway(tmp_path):
    async def check():
        async with Client(build_server(tmp_path / "mcp.sqlite3")) as client:
            listed = await client.list_tools()
            assert {t.name for t in listed.tools} == {"invoice_lookup", "ticket_lookup", "payment_proposal"}
            result = await client.call_tool("payment_proposal", {"payment_id": "PAY-202", "amount": 15000, "currency": "USD"})
            assert result.structured_content["decision"] == "REVIEW"
            assert result.structured_content["execution"] == "pending"
            invalid = await client.call_tool("invoice_lookup", {"invoice_id": "bad"})
            assert invalid.structured_content["decision"] == "BLOCK"
            malformed = await client.call_tool("payment_proposal", {"payment_id": "PAY-202", "amount": True, "currency": "USD"})
            assert malformed.structured_content["decision"] == "BLOCK"
    asyncio.run(check())
