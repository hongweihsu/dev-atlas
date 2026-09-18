#!/bin/bash
set -euo pipefail

runtime_directory=$(cd "$(dirname "$0")" && pwd)

cat > /etc/systemd/system/retrieval-works-backup.service <<EOF
[Unit]
Description=Back up the Retrieval Works PostgreSQL database to S3
After=docker.service

[Service]
Type=oneshot
User=ec2-user
WorkingDirectory=$runtime_directory
ExecStart=$runtime_directory/backup-postgres.sh
EOF

cat > /etc/systemd/system/retrieval-works-backup.timer <<'EOF'
[Unit]
Description=Run the Retrieval Works PostgreSQL backup daily

[Timer]
OnCalendar=*-*-* 03:15:00 UTC
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now retrieval-works-backup.timer
