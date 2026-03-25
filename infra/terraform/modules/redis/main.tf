################################################################################
# ElastiCache Redis Module — Control Fabric Platform
# Redis 7 cluster-mode replication group with encryption and automatic failover.
################################################################################

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

locals {
  tags = merge(var.tags, {
    project     = "control-fabric"
    environment = var.environment
    module      = "redis"
  })
}

################################################################################
# Subnet Group
################################################################################

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-${var.environment}-redis-subnet"
  subnet_ids = var.private_subnet_ids

  tags = local.tags
}

################################################################################
# Security Group
################################################################################

resource "aws_security_group" "redis" {
  name_prefix = "${var.name_prefix}-${var.environment}-redis-"
  description = "Security group for ElastiCache Redis"
  vpc_id      = var.vpc_id

  ingress {
    description = "Redis from VPC"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-${var.environment}-redis-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

################################################################################
# Parameter Group
################################################################################

resource "aws_elasticache_parameter_group" "this" {
  name   = "${var.name_prefix}-${var.environment}-redis7"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }

  tags = local.tags
}

################################################################################
# Replication Group (cluster mode)
################################################################################

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.name_prefix}-${var.environment}"
  description          = "Redis 7 cluster for Control Fabric ${var.environment}"

  engine         = "redis"
  engine_version = "7.1"
  node_type      = var.node_type
  port           = 6379

  num_node_groups         = var.num_shards
  replicas_per_node_group = var.replicas_per_shard

  automatic_failover_enabled = var.num_shards > 1 || var.replicas_per_shard > 0
  multi_az_enabled           = var.multi_az

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.redis.id]
  parameter_group_name = aws_elasticache_parameter_group.this.name

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.auth_token

  snapshot_retention_limit = var.snapshot_retention_days
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "sun:05:00-sun:06:00"

  auto_minor_version_upgrade = true

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-${var.environment}-redis"
  })
}
