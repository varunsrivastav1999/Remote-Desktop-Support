#!/bin/sh
set -e

if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
    echo "Starting Cloudflare Tunnel with permanent token..."
    exec /usr/local/bin/cloudflared tunnel --no-autoupdate run --token "$CLOUDFLARE_TUNNEL_TOKEN"
else
    echo "Starting Cloudflare Quick Tunnel for http://app:80..."
    exec /usr/local/bin/cloudflared tunnel --url http://app:80 --no-autoupdate
fi
