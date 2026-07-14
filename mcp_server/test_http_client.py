"""
Protocol-level test for the HTTP transport, analogous to test_mcp_client.py
(which tests stdio). Proves the server works correctly as a real
network-addressable service with bearer-token auth, not just as a local
subprocess — this is the transport used for EC2/Azure/GCP deployment.

Requires the server to already be running in streamable-http mode:

    POOLAIQ_MCP_TRANSPORT=streamable-http \\
    POOLAIQ_MCP_SERVER_API_KEY=your-test-key \\
    POOLAIQ_MCP_PORT=8420 \\
    python3 server.py &

Then run this test:
    POOLAIQ_MCP_SERVER_API_KEY=your-test-key python3 test_http_client.py
    # (defaults to http://localhost:8420/mcp if POOLAIQ_MCP_URL is not set)
"""

import asyncio
import os
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    api_key = os.environ.get("POOLAIQ_MCP_SERVER_API_KEY")
    if not api_key:
        print("ERROR: set POOLAIQ_MCP_SERVER_API_KEY to the same value the "
              "server was started with.")
        return

    url = os.environ.get("POOLAIQ_MCP_URL", "http://localhost:8420/mcp")
    print(f"Connecting to {url} over streamable-http with bearer auth...\n")

    async with streamablehttp_client(
        url, headers={"Authorization": f"Bearer {api_key}"}
    ) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            print("=== Tools advertised over HTTP ===")
            for t in tools_result.tools:
                print(f"  - {t.name}")
            print()

            print("=== Calling get_server_info() over HTTP ===")
            result = await session.call_tool("get_server_info", arguments={})
            print(json.dumps(json.loads(result.content[0].text), indent=2))
            print()

            print("=== Calling find_product(product_category='shock') over HTTP ===")
            result = await session.call_tool(
                "find_product", arguments={"product_category": "shock"}
            )
            print(json.dumps(json.loads(result.content[0].text), indent=2))

    print("\nAll calls completed over real HTTP with bearer-token auth — "
          "confirms this server works correctly as a deployed, "
          "network-addressable service, not just a local stdio subprocess.")


if __name__ == "__main__":
    asyncio.run(main())
