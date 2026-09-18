#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y docker git jq
systemctl enable --now docker
usermod -aG docker ec2-user

compose_version=v5.5.0
compose_checksum=ff42489f5a9b879d5d117c5ffea6defc27390b3286da8ad52cbc9c6ab5df590e
compose_directory=/usr/local/lib/docker/cli-plugins
compose_binary="$compose_directory/docker-compose"
mkdir -p "$compose_directory"
curl --fail --location --silent --show-error \
  "https://github.com/docker/compose/releases/download/$compose_version/docker-compose-linux-aarch64" \
  --output "$compose_binary"
echo "$compose_checksum  $compose_binary" | sha256sum --check --strict
chmod +x "$compose_binary"
docker compose version

buildx_version=v0.37.1
buildx_checksum=e5cc9fe3bbff5cbc91230981f7860e06076110730a2db997082652199042a1f2
buildx_binary="$compose_directory/docker-buildx"
curl --fail --location --silent --show-error \
  "https://github.com/docker/buildx/releases/download/$buildx_version/buildx-$buildx_version.linux-arm64" \
  --output "$buildx_binary"
echo "$buildx_checksum  $buildx_binary" | sha256sum --check --strict
chmod +x "$buildx_binary"
docker buildx version

mkdir -p /opt/retrieval-works
chown ec2-user:ec2-user /opt/retrieval-works

if [ ! -d /opt/retrieval-works/.git ]; then
  sudo -u ec2-user git clone https://github.com/hongweihsu/dev-atlas.git /opt/retrieval-works
fi

chmod +x /opt/retrieval-works/infra/aws/runtime/*.sh

if ! swapon --show | grep -q /swapfile; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
