#!/bin/bash
# PoolAIQ MCP Server — EC2 user-data (cloud-init) script
#
# Runs once, automatically, when the EC2 instance first boots. Installs
# Docker, writes secrets to a restricted-permission env file (never to the
# container image itself, never to shell history, never logged), and
# starts the MCP server container.
#
# Templated by Terraform (main.tf's templatefile() call) — the ${...}
# values below are substituted at `terraform apply` time from your
# terraform.tfvars, not hardcoded here.

set -euo pipefail

# --- Install Docker ---
apt-get update -y
apt-get install -y docker.io
systemctl enable docker
systemctl start docker

# --- Write secrets to a restricted-permission env file ---
# chmod 600, owned by root, never world-readable — this is the actual
# secret-handling mechanism for this demo-appropriate deployment. A
# production deployment should use AWS Secrets Manager or Parameter
# Store instead of a file on disk; see deploy/README.md's "Production
# hardening" section for what that migration looks like. Stated as a
# known limitation, not hidden.
mkdir -p /etc/poolaiq
cat > /etc/poolaiq/mcp-server.env <<EOF
POOLAIQ_MCP_TRANSPORT=streamable-http
POOLAIQ_MCP_HOST=0.0.0.0
POOLAIQ_MCP_PORT=${mcp_port}
POOLAIQ_MCP_SERVER_API_KEY=${mcp_server_api_key}
ANTHROPIC_API_KEY=${anthropic_api_key}
POOLAIQ_DEPLOYMENT_ENV=${deployment_environment}
POOLAIQ_PUBLIC_URL=${public_registration_url}
EOF
chmod 600 /etc/poolaiq/mcp-server.env
chown root:root /etc/poolaiq/mcp-server.env

# --- Pull and run the container ---
# Assumes docker_image has already been built (mcp_server/Dockerfile,
# built with build context at the repo root: `docker build -f
# mcp_server/Dockerfile -t your-registry/poolaiq-mcp:latest .`) and pushed
# to a registry this instance can reach (ECR, Docker Hub, etc.) BEFORE
# running `terraform apply` — Terraform does not build/push the image for
# you, only deploys infrastructure that expects it to already exist.
docker pull ${docker_image}

docker run -d \
  --name poolaiq-mcp-server \
  --restart unless-stopped \
  --env-file /etc/poolaiq/mcp-server.env \
  -p ${mcp_port}:${mcp_port} \
  ${docker_image}

# --- Basic health confirmation, logged to cloud-init output for debugging ---
sleep 5
docker ps --filter "name=poolaiq-mcp-server" --format "{{.Status}}"
echo "PoolAIQ MCP server container started. Check 'docker logs poolaiq-mcp-server' for startup details."
