FROM python:3.11

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ─── System dependencies for aiortc, mss, pynput ────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev \
        libsrtp2-dev libvpx-dev libopus-dev \
        pkg-config \
        libx11-dev libxext-dev libxrandr-dev libxinerama-dev \
        python3-xlib \
        xvfb x11-utils \
        xdotool \
        xclip xsel \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent source
COPY . .

# ─── Entrypoint ──────────────────────────────────────────────
ENV SERVER_URL=http://backend:8000
ENV AGENT_FPS=30
ENV AGENT_QUALITY=medium
ENV AGENT_MONITOR=1

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
