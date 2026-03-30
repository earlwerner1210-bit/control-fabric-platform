aws_region  = "us-east-1"
environment = "dev"
name_prefix = "control-fabric"
vpc_cidr    = "10.0.0.0/16"

# Sensitive values — set via TF_VAR_* env vars or a .tfvars file excluded from VCS
# rds_master_password = ""
# redis_auth_token    = ""
