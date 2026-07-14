# PoolAIQ MCP Server — EC2 deployment
#
# Provisions: one EC2 instance running the MCP server container, a security
# group allowing inbound access ONLY on the MCP port (from a configurable
# CIDR — default is deliberately NOT 0.0.0.0/0, see variables.tf), and an
# Elastic IP so the public address is stable across instance stop/start.
#
# This is the TEMPLATE deployment — Azure (deploy/azure/) and GCP
# (deploy/gcp/) follow the same shape: one compute instance, one
# container, one stable public address, secrets injected via each cloud's
# native secret-management primitive rather than baked into the image.
#
# Usage:
#   cd deploy/ec2
#   cp terraform.tfvars.example terraform.tfvars   # fill in your values
#   terraform init
#   terraform plan
#   terraform apply

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- Networking: security group scoped to the MCP port only ---

resource "aws_security_group" "mcp_server" {
  name        = "poolaiq-mcp-server-${var.deployment_environment}"
  description = "Inbound access to the PoolAIQ MCP server on its configured port only"

  ingress {
    description = "MCP server (streamable-http)"
    from_port   = var.mcp_port
    to_port     = var.mcp_port
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks # see variables.tf — NOT 0.0.0.0/0 by default
  }

  # SSH access for operational debugging — also scoped, not open to the world.
  ingress {
    description = "SSH (operator access only)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidr_blocks
  }

  egress {
    description = "All outbound (needed for pip install, Anthropic API calls, etc.)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "poolaiq-mcp-server-${var.deployment_environment}"
    Project     = "PoolAIQ"
    Environment = var.deployment_environment
  }
}

# --- Compute: one instance running the containerized MCP server ---

resource "aws_instance" "mcp_server" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.ssh_key_name
  vpc_security_group_ids = [aws_security_group.mcp_server.id]

  # Secrets are passed via user_data as environment variables written to a
  # restricted-permission file, NOT baked into the AMI or the container
  # image — see user_data.sh.tpl. This means the same AMI/image is
  # reusable across environments; only this instance's user_data differs.
  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    mcp_server_api_key      = var.mcp_server_api_key
    anthropic_api_key       = var.anthropic_api_key
    mcp_port                = var.mcp_port
    deployment_environment  = var.deployment_environment
    public_registration_url = var.public_registration_url
    docker_image             = var.docker_image
  })

  # Redeploy the instance if the startup script changes (e.g. a new
  # docker_image tag), rather than requiring a manual instance replacement.
  user_data_replace_on_change = true

  tags = {
    Name        = "poolaiq-mcp-server-${var.deployment_environment}"
    Project     = "PoolAIQ"
    Environment = var.deployment_environment
  }
}

# --- Stable public address ---

resource "aws_eip" "mcp_server" {
  instance = aws_instance.mcp_server.id
  domain   = "vpc"

  tags = {
    Name    = "poolaiq-mcp-server-${var.deployment_environment}"
    Project = "PoolAIQ"
  }
}
