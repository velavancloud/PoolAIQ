# PoolAIQ MCP Server — container image
#
# Used identically across EC2, Azure, and GCP deployment targets — the
# container is cloud-agnostic; only the surrounding infrastructure
# (deploy/ec2/, deploy/azure/, deploy/gcp/) differs per provider. This is
# the actual point of containerizing it: build once, deploy anywhere,
# per the twelve-factor principle already applied in config.py.
#
# Build from the REPO ROOT (not from mcp_server/), because it needs
# mcp_server/ as a subdirectory of the build context:
#   docker build -f mcp_server/Dockerfile -t poolaiq-mcp:latest .

FROM python:3.12-slim

WORKDIR /app

# Only the MCP server's own dependencies — NOT the webapp's (Flask, RAG,
# scikit-learn) or the agents/ package. The MCP server is deployed as an
# independent service; it does not need the rest of the monorepo at
# runtime, only at import time within its own directory.
COPY mcp_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_server/ .

# Non-root user — basic container hardening, not optional even for a demo
# deployment that will have a real public IP.
RUN useradd --create-home --shell /bin/bash poolaiq
USER poolaiq

# streamable-http is the only transport that makes sense inside a
# container reachable from outside its own host — stdio requires a
# subprocess-spawning parent on the SAME machine, which a containerized
# deployment does not have.
ENV POOLAIQ_MCP_TRANSPORT=streamable-http
ENV POOLAIQ_MCP_HOST=0.0.0.0
ENV POOLAIQ_MCP_PORT=8420

EXPOSE 8420

# POOLAIQ_MCP_SERVER_API_KEY, ANTHROPIC_API_KEY, POOLAIQ_DEPLOYMENT_ENV,
# and POOLAIQ_PUBLIC_URL are intentionally NOT set here — they are
# deployment-specific secrets/values, injected at container run time by
# whichever orchestrator starts this image (see deploy/ec2/user_data.sh.tpl
# for how EC2's deployment does this via environment variables sourced
# from a restricted-permission file, never baked into the image).

CMD ["python3", "server.py"]
