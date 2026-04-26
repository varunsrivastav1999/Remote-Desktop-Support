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

## Networking & World-Wide Connectivity

To achieve a seamless connection over the internet and through strict firewalls (like AnyDesk or RustDesk):

1.  **Public Signaling Server**: Ensure the `backend` service is deployed on a server with a public IP or a domain name.
2.  **STUN/TURN Servers**: In many internet environments (Symmetric NAT), direct P2P connection fails. You must configure a **TURN Server** (e.g., Coturn) in the **Settings > Network** tab of the dashboard.
3.  **ICE Candidates**: The platform automatically exchanges ICE candidates to find the most efficient path between the technician and the host agent.
4.  **Security**: Use HTTPS/WSS for all production traffic to ensure your signaling data and remote sessions are encrypted.

## Contributing

We welcome contributions from the community! Whether you are fixing bugs, proposing features, or optimizing the codebase, please open a pull request or an issue. Ensure your code adheres to standard Vue/Django style guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
