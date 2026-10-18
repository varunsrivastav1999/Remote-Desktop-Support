#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=================================================="
echo " Remote Desktop Support: Starting Docker & Agent"
echo "=================================================="

# 1. Start Docker containers (PostgreSQL, Redis, Coturn, Backend, Web App)
echo "[1/3] Bringing up Docker containers..."
docker compose up -d

# 2. Wait for backend to be healthy
echo "[2/3] Waiting for backend API to be ready..."
until curl -s http://localhost:8000/health | grep -q '"status":"ok"'; do
  sleep 1
done
echo "Backend is healthy at http://localhost:8000"

# 3. Launch or restart Tauri host agent using PM2
echo "[3/3] Launching Remote Support Host Agent with PM2..."
npx -y pm2 start ecosystem.config.js

echo "=================================================="
echo " Remote Desktop Support is running!"
echo " • Web Controller:  http://localhost:5173"
echo " • FastAPI Backend: http://localhost:8000"
echo " • View PM2 logs:   npx pm2 logs remote-support-agent"
echo " • Stop command:    ./stop.sh"
echo "=================================================="
