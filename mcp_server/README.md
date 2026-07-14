# PoolAIQ MCP Server

A real MCP server exposing 5 tools over either stdio (local dev) or HTTP
(deployed). See `../README.md` Section 3b for the architectural rationale;
this README covers running and deploying it specifically.

## Tools

| Tool | Purpose | Backing |
|---|---|---|
| `find_product` | Look up a product by chemistry issue/category | `catalog_data.py` (stub catalog) |
| `send_task_notification` | Dispatch SMS/push | `notification_store.py` (stub log) |
| `reason_about_reading` | Server-side Claude inference — plain-language explanation of a reading | `inference_tool.py`, uses this server's OWN `ANTHROPIC_API_KEY` |
| `get_notification_log` | Debug helper — everything sent so far | `notification_store.py` |
| `get_server_info` | Config summary (secrets redacted) — confirms which deployment you're talking to | `config.py` |

## Configuration

Everything environment-dependent lives in `config.py`, read from these
environment variables (all optional except where noted):

| Variable | Purpose | Default |
|---|---|---|
| `POOLAIQ_MCP_TRANSPORT` | `stdio` or `streamable-http` | `stdio` |
| `POOLAIQ_MCP_HOST` | Bind host (HTTP only) | `0.0.0.0` |
| `POOLAIQ_MCP_PORT` | Bind port (HTTP only) | `8420` |
| `POOLAIQ_MCP_SERVER_API_KEY` | Bearer token for HTTP transport — **required** if transport is `streamable-http`, server refuses to start without it | none |
| `ANTHROPIC_API_KEY` | This server's own key for `reason_about_reading` | none (tool returns a clean error if unset) |
| `POOLAIQ_INFERENCE_MODEL` | Model for server-side inference | `claude-sonnet-4-6` |
| `POOLAIQ_PRODUCT_API_KEY` | For a future real product API (currently unused — `catalog_data.py` is a stub) | none |
| `POOLAIQ_PRODUCT_API_BASE_URL` | Same | `https://stub.local/not-a-real-api` |
| `POOLAIQ_NOTIFICATION_API_KEY` | For a future real SMS/push provider (currently unused — `notification_store.py` is a stub) | none |
| `POOLAIQ_DEPLOYMENT_ENV` | Label shown in `get_server_info()` | `local` |
| `POOLAIQ_PUBLIC_URL` | This deployment's public URL, shown in `get_server_info()` | none |

Run `python3 config.py` to print the current resolved config with all
secret values redacted (booleans only, showing whether each is set).

## Run locally

```bash
pip install -r requirements.txt

# stdio (default — for use with test_mcp_client.py or webapp/mcp_client.py)
python3 server.py

# HTTP (for testing the deployed transport before actually deploying)
export POOLAIQ_MCP_TRANSPORT=streamable-http
export POOLAIQ_MCP_SERVER_API_KEY=$(openssl rand -hex 16)
python3 server.py
```

## Test

```bash
# Function-level (fast, no protocol layer)
python3 server.py --test

# Protocol-level over stdio
python3 test_mcp_client.py

# Protocol-level over HTTP (requires a running streamable-http server —
# see "Run locally" above)
export POOLAIQ_MCP_SERVER_API_KEY=<same key the server was started with>
python3 test_http_client.py
```

All three were run during development; the HTTP transport was verified
with a real bearer-token auth check (confirmed 401 without a key, 401 with
a wrong key, and a successful tool call with the correct key).

## Deploy

See `deploy/README.md` — EC2 is built as a real Terraform template.
Azure and GCP are not yet built; that README states plainly what would
carry over unchanged (the Dockerfile, `config.py`'s env-var surface) and
what needs building fresh for each cloud.
