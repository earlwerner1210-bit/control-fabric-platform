################################################################################
# Production Environment — Control Fabric Platform
# Full HA: multi-AZ RDS, 3 NAT gateways, larger instances, deletion protection.
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

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      project     = "control-fabric"
      environment = var.environment
      managed_by  = "terraform"
    }
  }
}

################################################################################
# VPC
################################################################################

module "vpc" {
  source = "../../modules/vpc"

  name_prefix       = var.name_prefix
  environment       = var.environment
  vpc_cidr          = var.vpc_cidr
  nat_gateway_count = 3 # one per AZ for HA
}

################################################################################
# RDS PostgreSQL
################################################################################

module "rds" {
  source = "../../modules/rds"

  name_prefix        = var.name_prefix
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  vpc_cidr           = module.vpc.vpc_cidr
  private_subnet_ids = module.vpc.private_subnet_ids

  instance_class        = "db.r6g.xlarge"
  allocated_storage     = 100
  max_allocated_storage = 500
  multi_az              = true
  backup_retention_days = 30
  deletion_protection   = true
  master_password       = var.rds_master_password
}

################################################################################
# ElastiCache Redis
################################################################################

module "redis" {
  source = "../../modules/redis"

  name_prefix        = var.name_prefix
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  vpc_cidr           = module.vpc.vpc_cidr
  private_subnet_ids = module.vpc.private_subnet_ids

  node_type              = "cache.r7g.large"
  num_shards             = 2
  replicas_per_shard     = 1
  multi_az               = true
  auth_token             = var.redis_auth_token
  snapshot_retention_days = 7
}

################################################################################
# EKS
################################################################################

module "eks" {
  source = "../../modules/eks"

  name_prefix        = var.name_prefix
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  public_subnet_ids  = module.vpc.public_subnet_ids
  private_subnet_ids = module.vpc.private_subnet_ids

  kubernetes_version     = "1.29"
  node_instance_types    = ["m6i.xlarge"]
  capacity_type          = "ON_DEMAND"
  node_desired_size      = 3
  node_min_size          = 3
  node_max_size          = 10
  endpoint_public_access = false # private-only in production
}

################################################################################
# ECR
################################################################################

module "ecr" {
  source = "../../modules/ecr"

  name_prefix          = var.name_prefix
  environment          = var.environment
  repository_names     = ["api", "worker", "frontend"]
  image_tag_mutability = "IMMUTABLE"
  max_image_count      = 50
}
