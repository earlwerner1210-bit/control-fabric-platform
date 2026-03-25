variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "control-fabric"
}

variable "environment" {
  description = "Environment name (dev, uat, production)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "nat_gateway_count" {
  description = "Number of NAT gateways (1 for dev, 3 for production HA)"
  type        = number
  default     = 1
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
