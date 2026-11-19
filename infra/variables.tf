variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "key_name" {
  type        = string
  description = "Existing EC2 key pair name."
}

variable "ssh_cidr" {
  type        = string
  default     = "0.0.0.0/0"
  description = "CIDR allowed to SSH to the instance."
}
