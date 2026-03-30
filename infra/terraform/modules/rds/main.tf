################################################################################
# RDS Module — Control Fabric Platform
# PostgreSQL 16 with pgvector extension, multi-AZ, encrypted, automated backups.
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
    module      = "rds"
  })
}

################################################################################
# Subnet Group
################################################################################

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-${var.environment}-db-subnet"
  subnet_ids = var.private_subnet_ids

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-${var.environment}-db-subnet"
  })
}

################################################################################
# Security Group
################################################################################

resource "aws_security_group" "rds" {
  name_prefix = "${var.name_prefix}-${var.environment}-rds-"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from VPC"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    cidr_blocks     = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-${var.environment}-rds-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

################################################################################
# Parameter Group (enables pgvector)
################################################################################

resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.name_prefix}-${var.environment}-pg16-"
  family      = "postgres16"
  description = "PostgreSQL 16 parameters for Control Fabric"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements,pgvector"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = var.log_min_duration_ms
  }

  tags = local.tags

  lifecycle {
    create_before_destroy = true
  }
}

################################################################################
# KMS Key for encryption at rest
################################################################################

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption — ${var.name_prefix}-${var.environment}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = local.tags
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.name_prefix}-${var.environment}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

################################################################################
# RDS Instance
################################################################################

resource "aws_db_instance" "this" {
  identifier = "${var.name_prefix}-${var.environment}-postgres"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = var.database_name
  username = var.master_username
  password = var.master_password

  multi_az               = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.this.name

  backup_retention_period   = var.backup_retention_days
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:30-sun:05:30"
  copy_tags_to_snapshot     = true
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.environment == "dev" ? true : false
  final_snapshot_identifier = var.environment != "dev" ? "${var.name_prefix}-${var.environment}-final-snapshot" : null

  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.rds.arn

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-${var.environment}-postgres"
  })
}
