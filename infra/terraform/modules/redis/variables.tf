variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "control-fabric"
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block for security group ingress"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for the cache subnet group"
  type        = list(string)
}

variable "node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.medium"
}

variable "num_shards" {
  description = "Number of node groups (shards) in the cluster"
  type        = number
  default     = 1
}

variable "replicas_per_shard" {
  description = "Number of read replicas per shard"
  type        = number
  default     = 1
}

variable "multi_az" {
  description = "Enable multi-AZ"
  type        = bool
  default     = false
}

variable "auth_token" {
  description = "Auth token (password) for Redis. Must be 16-128 chars."
  type        = string
  sensitive   = true
}

variable "snapshot_retention_days" {
  description = "Number of days to retain snapshots"
  type        = number
  default     = 3
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}
