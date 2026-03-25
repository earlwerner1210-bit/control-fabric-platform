variable "name_prefix" {
  description = "Prefix for repository names"
  type        = string
  default     = "control-fabric"
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "repository_names" {
  description = "List of ECR repository names to create"
  type        = list(string)
  default     = ["api", "worker", "frontend"]
}

variable "image_tag_mutability" {
  description = "Tag mutability setting: MUTABLE or IMMUTABLE"
  type        = string
  default     = "MUTABLE"
}

variable "max_image_count" {
  description = "Maximum number of images to retain per repository"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}
