output "public_ip" {
  description = "The Elastic IP address of the deployed MCP server"
  value       = aws_eip.mcp_server.public_ip
}

output "mcp_endpoint_url" {
  description = "The full MCP endpoint URL to configure clients (webapp/mcp_client.py, test_http_client.py) against"
  value       = "http://${aws_eip.mcp_server.public_ip}:${var.mcp_port}/mcp"
}

output "instance_id" {
  description = "EC2 instance ID, for SSH/SSM access during debugging"
  value       = aws_instance.mcp_server.id
}

output "security_group_id" {
  description = "Security group ID, if you need to add additional ingress rules later"
  value       = aws_security_group.mcp_server.id
}
