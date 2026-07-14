"""
A real MCP CLIENT that connects to server.py over the actual MCP stdio
protocol (spawns server.py as a subprocess, per the MCP spec) — this is
what proves server.py is genuinely speaking MCP, not just a collection of
Python functions with docstrings that happen to have @mcp.tool() decorators.

This is also the pattern reasoning_engine.py uses in production_hooks.py
to call the MCP server for real (see that file for the integration used by
the webapp).

Run:
    python3 test_mcp_client.py
"""

import asyncio
import os
import sys
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_path = os.path.join(os.path.dirname(__file__), "server.py")
    params = StdioServerParameters(
        command=sys.executable,
        args=[server_path],
    )

    print(f"Spawning MCP server subprocess: {sys.executable} {server_path}\n")

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List tools — proves the server correctly advertises its
            # capabilities over the protocol, not just that the functions exist.
            tools_result = await session.list_tools()
            print("=== Tools advertised by server over MCP protocol ===")
            for t in tools_result.tools:
                print(f"  - {t.name}: {t.description.strip().splitlines()[0]}")
            print()

            # Call find_product through the actual protocol layer
            print("=== Calling find_product(product_category='shock') via MCP ===")
            result = await session.call_tool(
                "find_product", arguments={"product_category": "shock"}
            )
            payload = json.loads(result.content[0].text)
            print(json.dumps(payload, indent=2))
            print()

            # Call find_product with an issue-based lookup
            print("=== Calling find_product(issue='ph_high') via MCP ===")
            result = await session.call_tool(
                "find_product", arguments={"issue": "ph_high"}
            )
            payload = json.loads(result.content[0].text)
            print(json.dumps(payload, indent=2))
            print()

            # Call send_task_notification through the actual protocol layer
            print("=== Calling send_task_notification(...) via MCP ===")
            result = await session.call_tool(
                "send_task_notification",
                arguments={
                    "channel": "sms",
                    "to": "+1-704-555-0100",
                    "body": "PoolAIQ: pH root cause detected (alkalinity buffering). "
                            "Approve acid-slug task? Reply YES to confirm.",
                    "task_id": "task_root_cause_demo",
                },
            )
            payload = json.loads(result.content[0].text)
            print(json.dumps(payload, indent=2))
            print()

            # Confirm it landed in the log, retrieved via a THIRD protocol call
            print("=== Calling get_notification_log() via MCP ===")
            result = await session.call_tool("get_notification_log", arguments={})
            payload = json.loads(result.content[0].text)
            print(json.dumps(payload, indent=2))

    print("\nAll calls completed over the real MCP stdio protocol — "
          "server was a genuine subprocess, not an in-process function call.")


if __name__ == "__main__":
    asyncio.run(main())
