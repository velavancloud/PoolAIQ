"""
PoolAIQ MCP Server

A real MCP server (using the official Anthropic mcp SDK's FastMCP interface)
exposing five tools:

  1. find_product — looks up which product addresses a given chemistry
     issue or product_category (backed by catalog_data.py's stub catalog)
  2. send_task_notification — dispatches an SMS/push notification for an
     approved task (backed by notification_store.py's stub log)
  3. reason_about_reading — server-side Claude inference call (uses the
     server's OWN configured ANTHROPIC_API_KEY, see inference_tool.py and
     config.py) to produce a plain-language explanation of a reading
  4. get_notification_log — debug/demo helper
  5. get_server_info — returns this server's config summary (transport,
     deployment environment, which optional integrations are configured)
     with all secret VALUES redacted — useful for confirming which
     deployment (local / EC2 / Azure / GCP) an MCP client is actually
     talking to

WHY THIS MATTERS FOR THE ARCHITECTURE: any MCP client (Claude, a script,
another agent, a deployed webapp) talks to this server the same way,
regardless of what's actually running behind each tool or which machine
the server is running on. See config.py for the full environment-variable
surface, and deploy/README.md for cloud deployment.

TRANSPORT: controlled by config.py's `transport` field
(POOLAIQ_MCP_TRANSPORT env var):
  - 'stdio' (default): spawned as a subprocess by a client, as used by
    webapp/mcp_client.py and test_mcp_client.py for local development
  - 'streamable-http': network-addressable HTTP server, required for any
    deployment where the MCP server and its callers are not the same
    process/host (EC2, Azure, GCP — see deploy/). Requires
    POOLAIQ_MCP_SERVER_API_KEY to be set (bearer-token auth, enforced by
    ApiKeyAuthMiddleware below) — the server refuses to start over HTTP
    without it.

Run standalone:
    python3 server.py                                    # stdio (local dev)
    POOLAIQ_MCP_TRANSPORT=streamable-http python3 server.py   # HTTP (deployed)

Test the tools directly (bypasses the protocol layer, for fast iteration):
    python3 server.py --test
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
from catalog_data import find_products_for, CATALOG  # noqa: E402
from notification_store import send_notification, get_sent_log  # noqa: E402
from inference_tool import reason_about_reading as _reason_about_reading  # noqa: E402
from config import config  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP(
    "poolaiq",
    host=config.http_host,
    port=config.http_port,
)


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


@mcp.tool()
def reason_about_reading(ph: float = None, free_chlorine_ppm: float = None,
                          total_alkalinity_ppm: float = None,
                          cyanuric_acid_ppm: float = None,
                          copper_ppm: float = None,
                          phosphates_ppb: float = None,
                          salt_ppm: float = None) -> str:
    """
    Server-side Claude inference call: produces a 2-4 sentence plain-
    language explanation of the given readings, using the MCP SERVER's
    own configured ANTHROPIC_API_KEY (not the caller's). Useful for any
    MCP client that wants a summary/explanation capability without needing
    its own Anthropic credentials.

    Deliberately narrow scope: this tool explains readings, it does NOT
    recommend chemical dosing or products — that authority stays with
    PoolAIQ's Reasoning Agent + Safety Agent (agents/), never with a
    general-purpose inference call. If ANTHROPIC_API_KEY is not configured
    on this server, returns a clear JSON error rather than failing silently.
    """
    readings = {
        "ph": ph, "free_chlorine_ppm": free_chlorine_ppm,
        "total_alkalinity_ppm": total_alkalinity_ppm,
        "cyanuric_acid_ppm": cyanuric_acid_ppm, "copper_ppm": copper_ppm,
        "phosphates_ppb": phosphates_ppb, "salt_ppm": salt_ppm,
    }
    readings = {k: v for k, v in readings.items() if v is not None}
    result = _reason_about_reading(readings)
    return json.dumps(result)


@mcp.tool()
def get_server_info() -> str:
    """
    Returns this server's configuration summary — transport mode,
    deployment environment (local/ec2/azure/gcp), and which optional
    integrations (server-side inference, product API, notification
    provider) are configured. ALL SECRET VALUES ARE REDACTED — only
    booleans indicating whether each is set. Useful for an MCP client or
    operator to confirm which deployment they're actually talking to.
    """
    return json.dumps(config.summary())


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
    print()

    print("=== get_server_info() ===")
    print(get_server_info())
    print()

    print("=== reason_about_reading(...) ===")
    print(reason_about_reading(ph=8.0, total_alkalinity_ppm=180, free_chlorine_ppm=0.3))


def _build_http_app():
    """
    Wraps FastMCP's streamable_http_app() with a bearer-token auth check.
    Deliberately NOT using the SDK's full OAuth AuthSettings path (which
    requires standing up a real OAuth authorization server with an
    issuer_url) — that's the correct choice for a multi-tenant production
    MCP deployment, but is more machinery than this project needs. What's
    built here is a real, functional bearer-key check, honestly scoped:
    good enough to keep a deployed HTTP endpoint from being wide open to
    the internet, not a claim of enterprise-grade auth (no key rotation,
    no per-client scopes, no rate limiting — see deploy/README.md for
    what a production hardening pass would add).
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            auth_header = request.headers.get("authorization", "")
            expected = f"Bearer {config.mcp_server_api_key}"
            if auth_header != expected:
                return JSONResponse(
                    {"error": "Unauthorized. Provide 'Authorization: Bearer <POOLAIQ_MCP_SERVER_API_KEY>'."},
                    status_code=401,
                )
            return await call_next(request)

    app = mcp.streamable_http_app()
    app.add_middleware(ApiKeyAuthMiddleware)
    return app


if __name__ == "__main__":
    if "--test" in sys.argv:
        _run_manual_tests()
    elif config.transport == "streamable-http":
        problems = config.validate_for_http()
        if problems:
            print("Cannot start with streamable-http transport:")
            for p in problems:
                print(f"  - {p}")
            sys.exit(1)

        import uvicorn

        print(f"Starting PoolAIQ MCP server on http://{config.http_host}:{config.http_port}")
        print(f"Deployment environment: {config.deployment_environment}")
        if config.public_registration_url:
            print(f"Public registration URL: {config.public_registration_url}")
        print("Auth: Bearer token required (POOLAIQ_MCP_SERVER_API_KEY)")
        print(f"Server-side inference configured: {bool(config.anthropic_api_key)}")

        uvicorn.run(_build_http_app(), host=config.http_host, port=config.http_port)
    else:
        mcp.run(transport="stdio")
