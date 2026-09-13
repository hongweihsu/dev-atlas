#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y docker git jq
systemctl enable --now docker
usermod -aG docker ec2-user

mkdir -p /opt/devatlas
chown ec2-user:ec2-user /opt/devatlas

if [ ! -d /opt/devatlas/.git ]; then
  sudo -u ec2-user git clone https://github.com/hongweihsu/dev-atlas.git /opt/devatlas
fi

chmod +x /opt/devatlas/infra/aws/runtime/*.sh

if ! swapon --show | grep -q /swapfile; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
