# Remote Support Platform

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-Production-success.svg)

An open-source, high-performance remote desktop support platform designed as a lightweight alternative to commercial tools like AnyDesk and TeamViewer. This platform offers a beautiful, low-latency web interface that allows technicians to connect to and manage remote devices globally over the internet.

## Features

- ⚡ **Low-Latency Signaling**: Built on Django Channels for sub-millisecond WebSocket connection routing.
- 🎨 **Premium UI**: A sleek, AnyDesk-style interface with a built-in Dark/Light mode and responsive dashboard.
- 💻 **In-Browser Terminal**: A fully functional, `xterm.js` based SSH terminal embedded directly in the browser for remote administration.
- 🗄️ **Persistent Sessions**: Support for custom aliases, favorite tagging, and seamless reconnects managed via PostgreSQL.
- 🔒 **Advanced Settings**: Highly customizable settings featuring Privacy Mode, Wake-on-LAN toggles, TCP Tunneling, and Key-based authentication support.
- 🐳 **Docker Ready**: Deploy anywhere in seconds with a fully containerized architecture.

## System Architecture

The platform consists of three main components:

1. **Frontend Web Client (Vue.js + Vite)**: The technician dashboard. Runs entirely in the browser, offering a control panel, session management, WebRTC viewers, and SSH terminal access.
2. **Signaling Server (Django + Channels)**: The backend broker. Manages database persistence (PostgreSQL), REST APIs, and WebSocket signaling to negotiate P2P connections between the technician and the host.
3. **Host Agent (Python/C++)**: A lightweight daemon installed on the remote machine that captures the screen, executes input commands, and establishes the reverse connection to the signaling server.

## Quick Start (Production Deployment)

We provide a streamlined Docker Compose setup to run the platform in any environment.

### Prerequisites
- Docker & Docker Compose
- Node.js (for local frontend development)

### Deployment Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/remote-support.git
   cd remote-support
   ```

2. **Start the services:**
   Run the following command to build and launch the Postgres database, Redis broker, and Django backend:
   ```bash
   docker-compose up -d --build
   ```

3. **Run database migrations:**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

4. **Start the Frontend (Development):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   *For production frontend deployment, use `npm run build` and serve the `dist/` directory via Nginx.*

5. **Access the Dashboard:**
   Navigate to `http://localhost:5173/` in your browser.

## Local Network Setup (Two Laptops on Same Wi-Fi)

Run Docker on the server laptop, then open the dashboard from either laptop:

```bash
docker compose up -d --build
```

Find the server laptop IP address:

```bash
ipconfig getifaddr en0
# If that is empty, use:
ifconfig | grep "inet "
```

Open the web app from laptop 2:

```text
http://<server-laptop-ip>:5173/
```

Run the host agent on the laptop you want to control:

```bash
cd host_agent
python3 agent.py --server http://<server-laptop-ip>:8000
```

Use the session code printed by the host agent in the web dashboard. Full desktop sharing and keyboard/mouse control require the Python host agent to be running on the target machine.

Leave the HTTP Proxy field empty for normal home/office Wi-Fi. It is only for networks where web traffic must go through a corporate proxy.

### Local Smoke Tests

Check that laptop 2 can reach the backend:

```bash
curl http://<server-laptop-ip>:8000/api/sessions/
```

Check Django admin CSS/static files:

```bash
curl -I http://<server-laptop-ip>:8000/static/admin/css/base.css
```

Check that the web dashboard can proxy WebSocket traffic by joining a real host-agent session from `http://<server-laptop-ip>:5173/`.

## Networking & World-Wide Connectivity

To achieve a seamless connection over the internet and through strict firewalls (like AnyDesk or RustDesk):

1.  **Public Signaling Server**: Ensure the `backend` service is deployed on a server with a public IP or a domain name.
2.  **STUN/TURN Servers**: In many internet environments (Symmetric NAT), direct P2P connection fails. You must configure a **TURN Server** (e.g., Coturn) in the **Settings > Network** tab of the dashboard.
3.  **ICE Candidates**: The platform automatically exchanges ICE candidates to find the most efficient path between the technician and the host agent.
4.  **Security**: Use HTTPS/WSS for all production traffic to ensure your signaling data and remote sessions are encrypted.

Example internet environment:

```env
DJANGO_ALLOWED_HOSTS=support.example.com
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://support.example.com
CSRF_TRUSTED_ORIGINS=https://support.example.com
```

Host agent with TURN:

```bash
python3 agent.py \
  --server https://support.example.com \
  --turn-server turn:turn.example.com:3478?transport=udp \
  --turn-username <user> \
  --turn-password <password>
```

The Docker stack includes an optional free Coturn relay on port `3478` with UDP relay ports `49160-49200`. On a public server, open/forward these ports and set the same values in the dashboard's Network tab:

```text
TURN server: turn:<server-ip-or-domain>:3478?transport=udp
TURN username: remote
TURN password: support@2026
```

Set `TURN_EXTERNAL_IP` in `.env` to the LAN IP for same-Wi-Fi relay testing, or to the server's public IP on a VPS.

For the host agent, use matching CLI values or environment variables:

```bash
REMOTE_SUPPORT_TURN_SERVERS=turn:<server-ip-or-domain>:3478?transport=udp \
REMOTE_SUPPORT_TURN_USERNAME=remote \
REMOTE_SUPPORT_TURN_PASSWORD=support@2026 \
python3 agent.py --server https://support.example.com
```

## Contributing

We welcome contributions from the community! Whether you are fixing bugs, proposing features, or optimizing the codebase, please open a pull request or an issue. Ensure your code adheres to standard Vue/Django style guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
