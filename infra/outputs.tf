output "public_ip" {
  value = aws_eip.dockship.public_ip
}

output "backup_bucket" {
  value = aws_s3_bucket.backups.bucket
}

output "ssh" {
  value = "ssh -i <key>.pem ubuntu@${aws_eip.dockship.public_ip}"
}
