variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "deployment_environment" {
  description = "Environment label, sets config.py's POOLAIQ_DEPLOYMENT_ENV and appears in get_server_info() output"
  type        = string
  default     = "ec2-staging"
}

variable "instance_type" {
  description = "EC2 instance type. t3.micro is sufficient for this demo-scale MCP server (a few tools, no heavy compute) — size up only if you expect real production traffic."
  type        = string
  default     = "t3.micro"
}

variable "ami_id" {
  description = "AMI to launch. Default assumes an Ubuntu 22.04 LTS AMI in us-east-1 — LOOK THIS UP for your actual region before applying, AMI IDs are region-specific. Find current ones at https://cloud-images.ubuntu.com/locator/ec2/"
  type        = string
  # This is a placeholder — Terraform will fail loudly if this AMI doesn't
  # exist in your target region, which is the correct behavior (fail fast
  # on a real misconfiguration, not a silent wrong-region deploy).
  default = "ami-0REPLACE-WITH-REAL-AMI-ID"
}

variable "ssh_key_name" {
  description = "Name of an EC2 key pair already created in your AWS account, for SSH access"
  type        = string
}

variable "mcp_port" {
  description = "Port the MCP server listens on"
  type        = number
  default     = 8420
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to reach the MCP server port. Deliberately does NOT default to 0.0.0.0/0 — set this to your webapp's outbound IP range, a VPN CIDR, or (for genuine public access) 0.0.0.0/0 explicitly and knowingly, not by default."
  type        = list(string)
  # Intentionally requires the operator to set this — no default provided,
  # forcing a conscious choice rather than an accidental wide-open server.
}

variable "ssh_allowed_cidr_blocks" {
  description = "CIDR blocks allowed to SSH into the instance for operational debugging"
  type        = list(string)
}

variable "mcp_server_api_key" {
  description = "Bearer token required by clients calling this MCP server (POOLAIQ_MCP_SERVER_API_KEY). Generate a real random value — do not reuse a value from local dev/testing."
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key for this server's OWN inference calls (reason_about_reading tool). Leave blank to deploy without server-side inference configured — the tool will return a clean error rather than failing."
  type        = string
  sensitive   = true
  default     = ""
}

variable "public_registration_url" {
  description = "The public URL this server will be reachable at once deployed (e.g. https://mcp.yourpool.example.com or the Elastic IP's http://<ip>:8420/mcp). Exposed via get_server_info() so clients/operators can confirm which deployment they're talking to."
  type        = string
  default     = ""
}

variable "docker_image" {
  description = "The container image to run. Build and push mcp_server/Dockerfile to a registry your EC2 instance can pull from (ECR, Docker Hub, etc.) before applying this Terraform."
  type        = string
}
