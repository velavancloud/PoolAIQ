"""
Sync bridge between Flask's synchronous request handlers and the MCP
protocol's async client API.

Why this file exists: Flask (in the simple dev-server form used by this
demo) handles requests synchronously, but the MCP Python SDK's ClientSession
is async (it's built on asyncio, matching the protocol's stdio/SSE transport
model). Rather than rewrite the Flask app as an async framework (a much
bigger change, out of scope for this capstone demo), this module spins up
a short-lived asyncio event loop per call, spawns the MCP server subprocess,
makes one tool call, and tears it down.

HONEST TRADEOFF, stated plainly: spawning a fresh subprocess per web request
is not how a production system would do this — a real deployment would keep
one long-lived MCP client session per server process (or a connection pool)
rather than paying subprocess-spawn cost on every request. This is the
simplest CORRECT implementation for a demo, not the fastest one. See
README.md's MCP section for the production alternative.
"""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MCP_SERVER_PATH = os.path.join(os.path.dirname(__file__), "..", "mcp_server", "server.py")


async def _call_tool_async(tool_name: str, arguments: dict) -> dict:
    params = StdioServerParameters(command=sys.executable, args=[MCP_SERVER_PATH])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            text = result.content[0].text
            return json.loads(text)


def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """
    Synchronous entry point Flask route handlers call directly.
    Wraps the async MCP client call in a fresh event loop.
    """
    return asyncio.run(_call_tool_async(tool_name, arguments))


def find_product_via_mcp(product_category: str = "", issue: str = "") -> dict:
    """Convenience wrapper used by app.py to enrich a recommendation's
    proposed_action with a real product lookup, via MCP rather than a
    direct import of catalog_data.py."""
    return call_mcp_tool("find_product", {
        "product_category": product_category,
        "issue": issue,
    })


def send_notification_via_mcp(channel: str, to: str, body: str, task_id: str = "") -> dict:
    """Convenience wrapper used by app.py's /api/approve endpoint to
    dispatch a notification via MCP when a user approves a task."""
    return call_mcp_tool("send_task_notification", {
        "channel": channel,
        "to": to,
        "body": body,
        "task_id": task_id,
    })


if __name__ == "__main__":
    print("=== find_product_via_mcp(product_category='clarifier') ===")
    print(json.dumps(find_product_via_mcp(product_category="clarifier"), indent=2))
    print()
    print("=== send_notification_via_mcp(...) ===")
    print(json.dumps(send_notification_via_mcp(
        channel="sms", to="+1-704-555-0100",
        body="Test from mcp_client.py sync bridge", task_id="test_task",
    ), indent=2))
