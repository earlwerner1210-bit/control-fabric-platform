terraform {
  backend "s3" {
    bucket         = "control-fabric-terraform-state"
    key            = "environments/production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "control-fabric-terraform-locks"
  }
}
