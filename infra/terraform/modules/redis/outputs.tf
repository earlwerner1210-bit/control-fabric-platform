output "redis_endpoint" {
  description = "Primary endpoint for the Redis replication group"
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "redis_configuration_endpoint" {
  description = "Configuration endpoint for cluster-mode enabled Redis"
  value       = aws_elasticache_replication_group.this.configuration_endpoint_address
}

output "redis_port" {
  description = "Redis port"
  value       = 6379
}

output "redis_security_group_id" {
  description = "Security group ID for Redis"
  value       = aws_security_group.redis.id
}

output "redis_replication_group_id" {
  description = "ID of the replication group"
  value       = aws_elasticache_replication_group.this.id
}
