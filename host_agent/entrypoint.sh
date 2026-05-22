#!/bin/bash
set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Remote Desktop Host Agent — Docker Container               ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# Always start Xvfb (even with host network, Docker has no display)
export DISPLAY=:99
echo "  → Starting Xvfb virtual framebuffer on $DISPLAY..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait for Xvfb to be ready
for i in $(seq 1 10); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "  → Xvfb ready (took ${i}s)"
        break
    fi
    sleep 1
done

if ! xdpyinfo -display :99 >/dev/null 2>&1; then
    echo "  ✗ Xvfb failed to start!"
    exit 1
fi

echo "  → Server URL: ${SERVER_URL}"
echo "  → FPS: ${AGENT_FPS} | Quality: ${AGENT_QUALITY} | Monitor: ${AGENT_MONITOR}"
echo ""

# Build command
CMD="python agent.py --server ${SERVER_URL} --fps ${AGENT_FPS} --quality ${AGENT_QUALITY} --monitor ${AGENT_MONITOR}"

if [ -n "$AGENT_ALIAS" ]; then CMD="$CMD --alias ${AGENT_ALIAS}"; fi
if [ -n "$AGENT_PASSWORD" ]; then CMD="$CMD --password ${AGENT_PASSWORD}"; fi
if [ -n "$TURN_SERVER" ]; then CMD="$CMD --turn-server ${TURN_SERVER}"; fi
if [ -n "$TURN_USERNAME" ]; then CMD="$CMD --turn-username ${TURN_USERNAME}"; fi
if [ -n "$TURN_PASSWORD" ]; then CMD="$CMD --turn-password ${TURN_PASSWORD}"; fi

echo "  → Starting: $CMD"
echo ""

exec $CMD
