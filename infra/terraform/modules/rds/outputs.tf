output "db_instance_id" {
  description = "RDS instance ID"
  value       = aws_db_instance.this.id
}

output "db_instance_endpoint" {
  description = "RDS connection endpoint"
  value       = aws_db_instance.this.endpoint
}

output "db_instance_address" {
  description = "RDS hostname"
  value       = aws_db_instance.this.address
}

output "db_instance_port" {
  description = "RDS port"
  value       = aws_db_instance.this.port
}

output "db_name" {
  description = "Database name"
  value       = aws_db_instance.this.db_name
}

output "db_security_group_id" {
  description = "Security group ID for the RDS instance"
  value       = aws_security_group.rds.id
}

output "db_kms_key_arn" {
  description = "KMS key ARN used for encryption"
  value       = aws_kms_key.rds.arn
}
