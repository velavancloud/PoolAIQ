"""
PoolAIQ MCP Server — Configuration

Central place for every environment-dependent value the MCP server needs.
Nothing in server.py, catalog_data.py, or notification_store.py should
read os.environ directly — they import from here, so there is exactly ONE
place that defines what configuration exists and what its defaults are.

WHY THIS MATTERS FOR DEPLOYMENT: before this file existed, the server had
zero config surface — no API keys, no way to run over a network, nothing
that would differ between your laptop and an EC2 instance. Every value here
is read from an environment variable with a sensible local-dev default, so
the exact same server.py runs unchanged on localhost, EC2, Azure, or GCP —
only the environment differs, per twelve-factor app config principles.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MCPServerConfig:
    # --- Transport ---
    transport: str = field(default_factory=lambda: os.environ.get("POOLAIQ_MCP_TRANSPORT", "stdio"))
    # 'stdio' (local dev, spawned as a subprocess by a client) or
    # 'streamable-http' (network-addressable, required for any cloud deployment
    # where the MCP server and its callers are not the same process/host)

    http_host: str = field(default_factory=lambda: os.environ.get("POOLAIQ_MCP_HOST", "0.0.0.0"))
    http_port: int = field(default_factory=lambda: int(os.environ.get("POOLAIQ_MCP_PORT", "8420")))

    # --- Anthropic API key: for the SERVER's own inference calls ---
    # Used by the new reason_about_reading tool (see inference_tool.py) —
    # this lets an MCP client ask the server to run a Claude reasoning call
    # server-side, rather than every client needing its own Anthropic
    # credentials. Distinct from any key a CALLING application might use
    # for its own separate purposes.
    anthropic_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY")
    )
    inference_model: str = field(
        default_factory=lambda: os.environ.get("POOLAIQ_INFERENCE_MODEL", "claude-sonnet-4-6")
    )

    # --- External product/retailer API key ---
    # Currently unused by catalog_data.py (which is a stub, documented as
    # such in mcp_server/README.md) but wired through end-to-end so
    # swapping the stub for a real Leslie's/Amazon product API later is a
    # one-file change in catalog_data.py, not a new config surface to build.
    product_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("POOLAIQ_PRODUCT_API_KEY")
    )
    product_api_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "POOLAIQ_PRODUCT_API_BASE_URL", "https://stub.local/not-a-real-api"
        )
    )

    # --- Notification provider (SMS/push) ---
    # Same pattern: unused by notification_store.py today (also a stub,
    # documented as such), wired through so a real Twilio/OneSignal
    # integration is a config value away, not a rearchitecture.
    notification_provider_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("POOLAIQ_NOTIFICATION_API_KEY")
    )

    # --- Auth for the HTTP transport ---
    # Required whenever transport == 'streamable-http'. A bare API-key
    # bearer-token check — NOT a claim of production-grade auth (no
    # rotation, no scopes, no rate limiting). See deploy/README.md for
    # what a real deployment should add on top of this.
    mcp_server_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("POOLAIQ_MCP_SERVER_API_KEY")
    )

    # --- Cloud/registration metadata ---
    # Where this server instance is registered/discoverable — filled in
    # per-deployment (see deploy/ec2/, future deploy/azure/, deploy/gcp/).
    # Not used by the server's own logic; exposed via the new
    # get_server_info tool so a caller/operator can confirm which
    # deployment they're actually talking to.
    deployment_environment: str = field(
        default_factory=lambda: os.environ.get("POOLAIQ_DEPLOYMENT_ENV", "local")
    )
    public_registration_url: Optional[str] = field(
        default_factory=lambda: os.environ.get("POOLAIQ_PUBLIC_URL")
    )

    def validate_for_http(self) -> list:
        """Returns a list of problems if transport is streamable-http but
        required config is missing. Called at startup — fail loudly and
        immediately rather than accepting unauthenticated connections."""
        problems = []
        if self.transport == "streamable-http":
            if not self.mcp_server_api_key:
                problems.append(
                    "POOLAIQ_MCP_SERVER_API_KEY is required when "
                    "POOLAIQ_MCP_TRANSPORT=streamable-http (refusing to run "
                    "an unauthenticated network-addressable server)."
                )
        return problems

    def summary(self) -> dict:
        """Safe-to-log summary — never includes actual secret VALUES, only
        whether they're set. Used by get_server_info and startup logging."""
        return {
            "transport": self.transport,
            "http_host": self.http_host if self.transport == "streamable-http" else None,
            "http_port": self.http_port if self.transport == "streamable-http" else None,
            "anthropic_api_key_configured": bool(self.anthropic_api_key),
            "inference_model": self.inference_model,
            "product_api_key_configured": bool(self.product_api_key),
            "product_api_base_url": self.product_api_base_url,
            "notification_provider_api_key_configured": bool(self.notification_provider_api_key),
            "mcp_server_api_key_configured": bool(self.mcp_server_api_key),
            "deployment_environment": self.deployment_environment,
            "public_registration_url": self.public_registration_url,
        }


# Module-level singleton — imported by server.py and every tool module.
# A real multi-tenant deployment might construct this per-request instead;
# for this single-server demo, one process-wide config is the right level
# of complexity.
config = MCPServerConfig()


if __name__ == "__main__":
    import json
    print("Current MCP server configuration (secrets redacted):")
    print(json.dumps(config.summary(), indent=2))
    problems = config.validate_for_http()
    if problems:
        print("\nProblems if run with streamable-http transport:")
        for p in problems:
            print(f"  - {p}")
