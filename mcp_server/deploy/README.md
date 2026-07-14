# Deploying the PoolAIQ MCP Server

## Status

| Target | Status |
|---|---|
| Local (stdio) | Built, tested — the default, used by `webapp/mcp_client.py` |
| Local (HTTP) | Built, tested — see "Test HTTP locally" below |
| Container image | Built (`../Dockerfile`), not tested with a real `docker build` in this environment (no Docker available where this was developed — see honest note below) |
| EC2 | **Built as real Terraform** (`ec2/`) — this is the template deployment |
| Azure | **Not built.** See "Azure and GCP" below for what carries over and what doesn't |
| GCP | **Not built.** Same as Azure |

## What changed to make deployment possible at all

Before this, the MCP server had zero configuration surface — no API keys,
stdio-only, could not run as a network service. Three things closed that
gap:

1. **`../config.py`** — every environment-dependent value (transport mode,
   API keys, deployment metadata) now comes from an environment variable
   with a local-dev default. Nothing in `server.py` reads `os.environ`
   directly anymore.
2. **Dual transport in `../server.py`** — `POOLAIQ_MCP_TRANSPORT=streamable-http`
   switches from a stdio subprocess to a real HTTP server (via `uvicorn`
   + FastMCP's `streamable_http_app()`), with a bearer-token auth
   middleware that makes the server refuse to start unauthenticated.
3. **Two new tools** — `reason_about_reading` (server-side Claude
   inference, using the server's own `ANTHROPIC_API_KEY`, distinct from
   any key the calling application uses) and `get_server_info` (returns
   config state with all secret values redacted, so a client/operator can
   confirm which deployment they're actually talking to).

## Test HTTP transport locally, before deploying anywhere

```bash
cd mcp_server
export POOLAIQ_MCP_TRANSPORT=streamable-http
export POOLAIQ_MCP_SERVER_API_KEY=$(openssl rand -hex 16)
export POOLAIQ_MCP_PORT=8420
python3 server.py &

# In another terminal:
export POOLAIQ_MCP_SERVER_API_KEY=<same value as above>
python3 test_http_client.py
```

This is the exact same code path that runs on EC2 — testing it locally
first is the fast iteration loop. Verified in development: correct 401 on
missing/wrong auth header, successful tool calls with the correct bearer
token, `get_server_info` correctly showing redacted config.

## Deploy to EC2

```bash
# 1. Build and push the container image (from the repo root)
docker build -f mcp_server/Dockerfile -t YOUR_ECR_REPO:latest .
docker push YOUR_ECR_REPO:latest

# 2. Configure and apply
cd mcp_server/deploy/ec2
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars — see the comments in that file, especially
# ami_id (region-specific!), allowed_cidr_blocks, and mcp_server_api_key

terraform init
terraform plan    # review before applying
terraform apply

# 3. Get the endpoint
terraform output mcp_endpoint_url
```

Point any MCP client (including `webapp/mcp_client.py`, if you're
deploying the webapp separately and want it to call a remote MCP server
instead of spawning a local stdio subprocess) at that URL with the
`POOLAIQ_MCP_SERVER_API_KEY` you set in `terraform.tfvars`.

### What EC2's Terraform actually provisions

- One EC2 instance (`t3.micro` by default — this is a demo-scale server,
  size up for real load) running the container via Docker, started by a
  `user_data.sh.tpl` cloud-init script
- A security group scoped to the MCP port + SSH only, from CIDR blocks
  YOU specify — `allowed_cidr_blocks` has **no default**, forcing a
  conscious choice rather than accidentally deploying to `0.0.0.0/0`
- An Elastic IP, so the address is stable across instance stop/start
- Secrets (`ANTHROPIC_API_KEY`, `POOLAIQ_MCP_SERVER_API_KEY`) written to
  `/etc/poolaiq/mcp-server.env` on the instance at boot, `chmod 600`,
  never baked into the container image or committed to version control

### Honest limitations of this EC2 deployment

- **Secrets are a file on disk (chmod 600), not a real secrets manager.**
  Stated plainly in `user_data.sh.tpl`'s comments: a production deployment
  should use AWS Secrets Manager or Parameter Store, with the instance
  granted IAM permission to read them at boot instead of receiving them
  via `user_data` (which is visible to anyone with `ec2:DescribeInstances`
  permission on the account, not just the instance itself). This is a
  demo-appropriate tradeoff, not a production-security claim.
- **No auto-scaling, no load balancer, no multi-AZ.** One instance, one
  Elastic IP. Fine for a capstone demo or low-traffic personal deployment;
  not a claim of production availability.
- **`terraform apply` was never run against real AWS in this development
  environment** (no AWS credentials/access available where this was
  built). The `.tf` files were hand-verified for internal consistency
  (every template variable referenced in `user_data.sh.tpl` is confirmed
  passed from `main.tf`'s `templatefile()` call, and brace-balance checked
  across all three `.tf` files) but have not been proven against a real
  `terraform plan`/`apply` cycle. **Run `terraform plan` yourself and
  review it carefully before `apply`** — treat this as a strong starting
  template, not a guaranteed-correct deployment.
- **Docker build was never run in this environment either** (no Docker
  available). The Dockerfile was hand-verified against the actual file
  layout (`COPY mcp_server/requirements.txt`, `COPY mcp_server/ .`,
  assuming build context at the repo root) but not test-built. Run
  `docker build -f mcp_server/Dockerfile -t test .` yourself first and
  confirm it succeeds before trusting the EC2 deployment to pull it.

## Azure and GCP

**Not built.** What carries over unchanged when you do build them:

- `../Dockerfile` — cloud-agnostic, works as-is
- `../config.py` — same environment variables, every cloud's container
  service (Azure Container Instances / App Service, GCP Cloud Run) can
  inject env vars the same way EC2's `user_data.sh.tpl` does, just via
  that platform's own mechanism instead of a cloud-init script
- The bearer-token auth middleware in `server.py` — transport-agnostic

What needs building fresh for each:

- **Azure**: likely `deploy/azure/main.bicep` or Terraform with the
  `azurerm` provider — Azure Container Instances is the closest
  equivalent to this EC2 template's "one instance, one container, one
  stable IP" shape; secrets should go in Azure Key Vault rather than a
  file on disk
- **GCP**: likely `deploy/gcp/main.tf` with the `google` provider — Cloud
  Run is arguably a BETTER fit than a persistent VM for this server (it's
  stateless, scales to zero, and GCP's Secret Manager integration is
  more native than EC2's user_data approach) — worth reconsidering the
  "one VM" shape entirely for this target rather than mechanically
  porting the EC2 approach

This EC2 template is deliberately the FIRST one built and the most
conservative shape (a persistent VM) specifically so it can serve as the
comparison point once Azure/GCP are built — if you build Cloud Run for
GCP, for instance, the interesting capstone discussion is not just
"it also works on GCP" but "here's why a serverless container model is
actually a better fit for a stateless MCP tool server than the VM model
EC2 pushed us toward first."
