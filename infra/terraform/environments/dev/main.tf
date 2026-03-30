################################################################################
# Dev Environment — Control Fabric Platform
# Composes all modules with dev-sized (small, cost-effective) instances.
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
  nat_gateway_count = 1 # single NAT for dev cost savings
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

  instance_class        = "db.t4g.medium"
  allocated_storage     = 20
  max_allocated_storage = 50
  multi_az              = false
  backup_retention_days = 3
  deletion_protection   = false
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

  node_type          = "cache.t4g.micro"
  num_shards         = 1
  replicas_per_shard = 0
  multi_az           = false
  auth_token         = var.redis_auth_token
  snapshot_retention_days = 1
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
  node_instance_types    = ["t3.medium"]
  capacity_type          = "SPOT"
  node_desired_size      = 2
  node_min_size          = 1
  node_max_size          = 4
  endpoint_public_access = true
}

################################################################################
# ECR
################################################################################

module "ecr" {
  source = "../../modules/ecr"

  name_prefix      = var.name_prefix
  environment      = var.environment
  repository_names = ["api", "worker", "frontend"]
  max_image_count  = 15
}
