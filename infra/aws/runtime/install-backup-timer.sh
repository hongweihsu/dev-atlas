#!/bin/bash
set -euo pipefail

runtime_directory=$(cd "$(dirname "$0")" && pwd)

cat > /etc/systemd/system/devatlas-backup.service <<EOF
[Unit]
Description=Back up the DevAtlas PostgreSQL database to S3
After=docker.service

[Service]
Type=oneshot
User=ec2-user
WorkingDirectory=$runtime_directory
ExecStart=$runtime_directory/backup-postgres.sh
EOF

cat > /etc/systemd/system/devatlas-backup.timer <<'EOF'
[Unit]
Description=Run the DevAtlas PostgreSQL backup daily

[Timer]
OnCalendar=*-*-* 03:15:00 UTC
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now devatlas-backup.timer
