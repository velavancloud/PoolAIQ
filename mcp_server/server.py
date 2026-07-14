"""
PoolAIQ MCP Server

A real MCP server (using the official Anthropic mcp SDK's FastMCP interface)
exposing two tools that PoolAIQ's reasoning engine calls through the MCP
protocol rather than importing directly:

  1. find_product — looks up which product addresses a given chemistry
     issue or product_category (backed by catalog_data.py's stub catalog)
  2. send_task_notification — dispatches an SMS/push notification for an
     approved task (backed by notification_store.py's stub log)

WHY THIS MATTERS FOR THE ARCHITECTURE (not just "because the panel asked for
MCP"): before this file existed, any code that needed a product recommendation
or needed to send a notification would have imported catalog_data.py or
notification_store.py DIRECTLY. That works for a demo with one Flask app, but
it means every future consumer of PoolAIQ (a CLI tool, a second web app, an
SMS-in webhook) would need its own copy of that import logic, and swapping
the stub catalog for a real Leslie's API would mean hunting down every call
site. MCP gives external-resource access ONE protocol boundary: any MCP
client (Claude, a script, another agent) talks to this server the same way,
regardless of what's actually running behind find_product or
send_task_notification.

Run standalone (stdio transport, for use with any MCP client):
    python3 server.py

Test the tools directly (bypasses the protocol layer, for fast iteration):
    python3 server.py --test
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
from catalog_data import find_products_for, CATALOG  # noqa: E402
from notification_store import send_notification, get_sent_log  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("poolaiq")


@mcp.tool()
def find_product(product_category: str = "", issue: str = "") -> str:
    """
    Look up pool chemistry products by category or by the specific issue
    they address. Pass EITHER product_category (e.g. 'acid', 'shock',
    'clarifier', 'metal_sequestrant', 'phosphate_remover', 'stabilizer',
    'base', 'salt') OR issue (e.g. 'ph_high', 'alkalinity_high',
    'free_chlorine_low', 'copper_high', 'phosphates_high').

    Returns a JSON list of matching products with sku, name, brand, price,
    size, and a purchase URL.
    """
    results = find_products_for(product_category=product_category or None,
                                 issue=issue or None)
    if not results:
        return json.dumps({
            "found": False,
            "message": f"No products found for category='{product_category}' issue='{issue}'. "
                       f"Available categories: {sorted(set(p.category for p in CATALOG))}",
        })

    return json.dumps({
        "found": True,
        "count": len(results),
        "products": [
            {
                "sku": p.sku,
                "name": p.name,
                "brand": p.brand,
                "category": p.category,
                "addresses": p.addresses,
                "price_usd": p.price_usd,
                "size": p.size,
                "retailer": p.retailer,
                "url": p.url,
            }
            for p in results
        ],
    })


@mcp.tool()
def send_task_notification(channel: str, to: str, body: str, task_id: str = "") -> str:
    """
    Send a task notification via SMS or push. channel must be 'sms' or
    'push'. This is a stub backing store (notification_store.py) — no real
    message is delivered — but the tool boundary is real, so swapping in a
    live Twilio/OneSignal call later doesn't change any calling code.

    Returns a JSON confirmation with the notification id and timestamp.
    """
    if channel not in ("sms", "push"):
        return json.dumps({"error": f"channel must be 'sms' or 'push', got '{channel}'"})

    notif = send_notification(channel=channel, to=to, body=body,
                               task_id=task_id or None)
    return json.dumps({
        "sent": True,
        "notification_id": notif.id,
        "channel": notif.channel,
        "to": notif.to,
        "sent_at": notif.sent_at,
    })


@mcp.tool()
def get_notification_log() -> str:
    """Return all notifications sent so far in this server session, for
    debugging/demo purposes (e.g. showing what would have been texted)."""
    log = get_sent_log()
    return json.dumps({
        "count": len(log),
        "notifications": [
            {"id": n.id, "channel": n.channel, "to": n.to, "body": n.body,
             "task_id": n.task_id, "sent_at": n.sent_at}
            for n in log
        ],
    })


def _run_manual_tests():
    """Exercises the tool FUNCTIONS directly (not through the MCP protocol
    layer) for fast local iteration without needing a full client/server
    handshake. The protocol-level test lives in test_mcp_client.py."""
    print("=== find_product(product_category='acid') ===")
    print(find_product(product_category="acid"))
    print()

    print("=== find_product(issue='alkalinity_high') ===")
    print(find_product(issue="alkalinity_high"))
    print()

    print("=== find_product(product_category='nonexistent') ===")
    print(find_product(product_category="nonexistent"))
    print()

    print("=== send_task_notification(...) ===")
    print(send_task_notification(
        channel="sms",
        to="+1-704-555-0100",
        body="PoolAIQ: Approved task — add 8oz Muriatic Acid. Reply DONE when complete.",
        task_id="task_demo_1",
    ))
    print()

    print("=== get_notification_log() ===")
    print(get_notification_log())


if __name__ == "__main__":
    if "--test" in sys.argv:
        _run_manual_tests()
    else:
        mcp.run(transport="stdio")
