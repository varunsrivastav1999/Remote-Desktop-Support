#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "Stopping Remote Support Host Agent in PM2..."
npx -y pm2 stop remote-support-agent || true
npx -y pm2 delete remote-support-agent || true
npx -y pm2 stop anygravity-agent || true
npx -y pm2 delete anygravity-agent || true

echo "Stopping Docker containers..."
docker compose stop
echo "Remote Desktop Support stopped."
