# Remote Desktop Support — Production-Grade Self-Hosted Remote Desktop

**Remote Desktop Support** is a modern, high-performance, self-hosted remote desktop application inspired by AnyDesk and RustDesk. It allows two computers to connect seamlessly using a permanent, hardware-independent **Device ID** (`AG-XXX-XXX-XXX`), establishing direct peer-to-peer **WebRTC** sessions for low-latency screen control, interactive terminal access, bidirectional clipboard sync, two-way chat, and file transfer.

The system is **100% self-contained, open-source, and free to use** with zero reliance on paid third-party services.

---

> [!IMPORTANT]
> **Fixed Live Production Access URL:**
> 👉 **[https://webmaster-meal-classroom-colony.trycloudflare.com/](https://webmaster-meal-classroom-colony.trycloudflare.com/)**
>
> Open this URL on **any computer or browser** (macOS, Windows, Linux) to start a session, share your screen, or control a remote machine. No port forwarding or paid subscriptions required.

## 🌐 Live Public Access & Deployment URLs

| Service | Address |
| :--- | :--- |
| **Fixed Public Web App & Controller** | [https://webmaster-meal-classroom-colony.trycloudflare.com/](https://webmaster-meal-classroom-colony.trycloudflare.com/) |
| **Public Server Healthcheck** | [https://webmaster-meal-classroom-colony.trycloudflare.com/health](https://webmaster-meal-classroom-colony.trycloudflare.com/health) |
| **Public Agent Proxy Health** | [https://webmaster-meal-classroom-colony.trycloudflare.com/api/v1/agent/health](https://webmaster-meal-classroom-colony.trycloudflare.com/api/v1/agent/health) |
| **Local Web Interface** | `http://localhost:5173` |
| **Local FastAPI Backend** | `http://localhost:8000` |
| **Local PostgreSQL Database** | `localhost:5433` |
| **Local Redis Cache** | `localhost:6379` |
| **Local Coturn TURN/STUN** | `localhost:3478` (UDP/TCP) |

---

## 1. System Architecture

```text
Remote Desktop Support Server Stack
┌────────────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (Async SQLAlchemy + Redis PubSub)                     │
│  - Device Registry & Permanent AG-XXX-XXX-XXX ID Allocation            │
│  - Presence & Heartbeat Engine (Redis TTL + DB Tracking)               │
│  - Session Authorization & Unattended PIN Verification                 │
│  - Push Notifications & WebRTC Signaling Dispatch                      │
│  - Authenticated Agent Channel (/ws/agent/*) for Browser Host Control  │
│                                                                        │
│  PostgreSQL (Persistent Storage)  │  Redis (Real-time Presence)        │
│  Coturn (TURN/STUN Relay)         │  Nginx / Vite (Web App UI)         │
│  Cloudflare Tunnel (Public HTTPS) │  Watchtower & Auto Updater         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                       WebSocket / HTTPS Signaling
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          │                                                   │
    Computer A (Client)                                 Computer B (Host)
Device ID: AG-482-193-721                           Device ID: AG-735-281-904
          │                                                   │
          └══════════════ Direct WebRTC P2P ══════════════════┘
             (LAN / Internet STUN / Fallback to Coturn TURN)
             • Encrypted Video Stream (VP8/VP9/H.264)
             • Letterbox-Aware Mouse & Keyboard Input Injection
             • High-Visibility Remote Cursor & Tactile Click Indicator
             • Two-Way In-Session Chat (Host ↔ Client with Unread Badges)
             • Interactive Remote Shell / Terminal Channel
             • P2P Secure File Transfer (Upload/Download Chunks)
             • In-Session Network & Security Settings Drawer
```

---

## 2. Key Features

- **Permanent Device ID (`AG-XXX-XXX-XXX`):** Securely generated, persistent across reboots, DHCP changes, router switches, and Wi-Fi $\leftrightarrow$ Ethernet transitions.
- **Direct P2P WebRTC Transmission:** Video and control data flow directly between peers without passing through the server when direct connection is achievable.
- **Coturn TURN Fallback:** Transparent relay fallback for symmetric NATs and restricted enterprise firewalls.
- **Live Consent & Unattended Access:**
  - **Attended Mode:** Host receives an incoming connection request banner with `[ Allow Control ]` and `[ Deny ]` buttons.
  - **Unattended Mode:** Optional Argon2/PBKDF2-hashed security PIN allows trusted remote access without local user interaction.
- **Take Control / Release Control Workflow:**
  - **VIEW ONLY Mode by Default:** Sessions connect initially in View Only mode so screen monitoring does not interfere with the host.
  - **Prominent Take Control Button:** Clicking `Take Control` initiates a verified handshake with the remote host peer and companion daemon. The UI only switches to `CONTROL ACTIVE` upon real acknowledgment from the remote machine.
  - **Host-Authorized Control:** The host is the single authority for control. A browser host refuses `Take Control` (with an explanation) when its companion agent is not connected, and the server relays mouse/keyboard input to the agent only while control is granted, so View Only is enforced on the remote machine itself.
  - **Full Remote Interaction:** Dispatches mouse movements, single/double clicks, context menu right-clicks, drag-and-drop, scroll wheels, keystrokes, and keyboard shortcuts (Ctrl+C, Ctrl+V, Alt, Meta/Windows/Cmd, Function keys) directly to the remote OS input system.
  - **Instant Release Control:** Clicking `Release Control` immediately releases all pressed inputs and reverts to View Only mode without interrupting the video stream.
  - **Strict Target Isolation:** Zero local machine execution; all operations route strictly to the connected remote device ID.
- **Visible & Controllable Mouse Pointer:**
  - **Letterbox-Aware Coordinate Calculation:** Automatically scales input across any screen aspect ratio or window size with 100% pixel precision.
  - **High-Visibility Cursor:** Sharp SVG pointer with drop shadow and interactive click/drag indicator dot.
  - **Full Mouse Actions:** Single click, double click, right-click (`contextmenu`), drag-and-drop, and scroll wheel.
- **Two-Way In-Session Chat:** Host and Controller can chat seamlessly with unread message badges on both ends.
- **Interactive Shell / SSH Terminal:** Real interactive shell via `xterm.js` and WebRTC data channel with zero port 22 exposure.
- **P2P File Transfer:** Direct file browsing, downloading files in 48 KB chunks, uploading with live progress tracking, folder creation, and deletion.
- **In-Session Settings & Diagnostics:** Access network, signaling, relay, and security settings directly from the in-session toolbar; view real-time latency (RTT), FPS, bitrate, jitter, and packet loss.
- **Zero Proprietary Dependencies:** 100% self-hosted; no reliance on AnyDesk, TeamViewer, Chrome Remote Desktop, or Firebase.

---

## 3. Quick Start (Self-Hosted Server)

### Prerequisites
- Docker Engine $\ge$ 20.10 & Docker Compose $\ge$ 2.0
- Ports available: `8000` (FastAPI), `5173` (Web UI), `5433` (Postgres host mapping), `6379` (Redis), `3478` (Coturn STUN/TURN)

### Launch Server Stack
```bash
# Clone the repository
git clone https://github.com/varunsrivastav1999/Remote-Desktop-Support.git
cd Remote-Desktop-Support

# Copy environment configuration
cp .env.example .env

# Start all backend, database, relay, and web services
docker compose up -d --build
```

### Verify Running Services
```bash
docker compose ps
curl http://localhost:8000/health
```
Expected output:
```json
{"status":"ok","service":"Remote Desktop Support Server","redis":"connected","database":"connected"}
```

---

## 4. Host OS Remote Control Setup

Remote Desktop Support supports two host modes:

### Mode A: Browser Host + Native Companion Agent (Recommended for Web Users)
When sharing a screen through a web browser (Google Chrome, Microsoft Edge, Mozilla Firefox), run the lightweight companion daemon on the host computer to enable native OS mouse clicks, drag-and-drop, keyboard input, terminal commands, and file browsing.

The **Share This Desk** screen shows a one-time install command for macOS, Windows and Linux with your Device ID and agent token pre-filled (the token is masked on screen; the **Copy** button copies the full command). Run it once: the agent copies itself to a per-user folder, remembers the server, Device ID and token, and starts by itself at every login, reconnecting whenever the server or network comes back.

```bash
# macOS / Linux: install once
curl -sSL https://<your-server>/agent.py | python3 - --install --server https://<your-server> --device <YOUR_DEVICE_ID> --token <AGENT_TOKEN>

# Windows: the Host screen gives a PowerShell command that finds py/python (python3 is often missing)

# Remove it again
python3 "<install folder>/agent.py" --uninstall

# Run once in the foreground instead of installing (or from a cloned repository)
python3 scripts/local_agent.py --server https://<your-server> --device <YOUR_DEVICE_ID> --token <AGENT_TOKEN>
```

| OS | Install folder | Starts at login via |
|----|----------------|---------------------|
| macOS | `~/Library/Application Support/RemoteDesktopSupport` | LaunchAgent `~/Library/LaunchAgents/com.remotedesktopsupport.agent.plist` |
| Windows | `%LOCALAPPDATA%\RemoteDesktopSupport` | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` value `RemoteDesktopSupportAgent` (no admin rights needed) |
| Linux | `~/.local/share/remote-desktop-support` | systemd user unit `remote-desktop-support-agent.service`, or an XDG autostart entry without systemd |

- **Install once per browser:** a browser normally gives each tab its own Device ID. Copying the install command links this browser's Device ID to the installed agent; later tabs reuse it while no other tab holds it (Web Locks, so it needs HTTPS or localhost).
- **One agent per user account:** a second agent exits instead of injecting input twice. An installed agent whose token is rejected keeps waiting, and running the install command again relinks it.

- **Agent authentication:** The server accepts an agent for a Device ID only with that device's agent token, which `/api/v1/devices/register` returns as `agent_token`. The token is derived from the device token, so it changes whenever the device registers with a new token, and it cannot be used to register as the host. You can also pass it in the `AGENT_TOKEN` environment variable. An agent started by hand without a valid token exits instead of connecting.
- **No local ports:** The agent opens no listening sockets. Mouse, keyboard, terminal, and file requests reach it only through its authenticated server connection, and only the authenticated host can issue terminal and file requests.

- **Outbound WebSocket Tunneling:** The companion agent connects via persistent outbound WebSocket directly to the signaling server (`wss://.../ws/agent/{device_id}`). This bypasses all browser Mixed Content and Private Network Access (PNA) restrictions, working seamlessly across firewalls and NAT.
- **Linux (Ubuntu / Debian / Fedora / Arch):** Automatically detects and uses `pynput` or native `xdotool` (`sudo apt-get install -y xdotool`). Supports single clicks, right clicks, double clicks, dragging, scrolling, and keyboard shortcuts.
- **macOS:** Grant *Accessibility* to Python in **System Settings → Privacy & Security → Accessibility** (the installed agent asks for it; a run in Terminal needs it for Terminal).
- **Windows:** Supports all mouse and keyboard actions out of the box via `pynput` and `user32.dll`.

### Mode B: Native Tauri Desktop Application
For an all-in-one native binary (with built-in Rust engine, zero Python required):

```bash
cd tauri_agent
npm install
npm run tauri dev
```

Build production installers (`.dmg`, `.deb`, `.msi`):
```bash
npm run tauri build
```

---

## 5. How to Connect

### 1. Attended Support Flow
1. **Host Computer:** Open [https://webmaster-meal-classroom-colony.trycloudflare.com/](https://webmaster-meal-classroom-colony.trycloudflare.com/) (or `http://localhost:5173`). Click **Share This Desk** and select the screen/window to share.
2. **Controller Computer:** Open the same URL, enter the Host's Device ID (`AG-XXX-XXX-XXX`), and click **Connect**.
3. **Approval:** The Host receives an on-screen prompt:
   ```text
   Incoming Control Request
   Remote Controller is requesting to view and control this screen.
   [ Deny ]   [ Allow Control ]
   ```
4. **Active Session:** Once approved, the remote desktop stream is active with full mouse control, keyboard input, terminal access, file transfer, and chat.

### 2. Unattended Access Flow
1. **Host:** In **Settings → Security & PIN**, enable **Unattended Access** and set a secure PIN.
2. **Controller:** Connects using the Device ID and enters the PIN to establish the session without requiring manual on-screen approval.

---

## 6. Interactive Features Reference

### Remote Control & Mouse Actions
- **Single Click / Left Click:** Dispatches single OS click without double-triggering.
- **Right Click:** Context menu triggers right click across all operating systems.
- **Double Click:** Opens folders and files natively.
- **Drag-and-Drop:** Press and drag items across the desktop.
- **Scroll Wheel:** Proportional vertical and horizontal scrolling.

### In-Session Terminal / Shell
- Click the **Terminal** icon in the toolbar.
- Type commands (`ls`, `pwd`, `whoami`, etc.) and receive real shell output.
- Auto-focused with `xterm.js` and responsive resizing.

### P2P File Transfer
- Click the **File Transfer** icon in the toolbar.
- Browse remote folders, download files, drag-and-drop to upload with real-time transfer speed and progress indicators, create folders, or delete files.

### Two-Way Session Chat
- Click the **Chat** icon in the toolbar (client) or header (host).
- Instant two-way messaging with unread notification badges.

### In-Session Settings
- Click the **Settings** gear icon in the toolbar to adjust network servers, STUN/TURN configuration, or security PINs on the fly.

---

## 7. Configuration Reference (`.env`)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `POSTGRES_USER` | `rsadmin` | Database username |
| `POSTGRES_PASSWORD` | `support_2026` | Database password |
| `POSTGRES_DB` | `remote_support` | Database name |
| `POSTGRES_HOST_PORT` | `5433` | Host-mapped PostgreSQL port (avoids conflict with local 5432) |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async SQLAlchemy database URL |
| `SESSION_TTL_SECONDS` | `2592000` | Device registration TTL (30 days) |
| `CORS_ALLOWED_ORIGINS` | `*` | Allowed CORS origins for Web UI |
| `STUN_SERVERS` | `stun:stun.l.google.com:19302` | Public STUN servers for NAT discovery |
| `TURN_SERVER` | `turn:your-server:3478` | Public Coturn relay server URL |
| `TURN_USERNAME` | `remote` | Coturn authentication username |
| `TURN_PASSWORD` | `support_2026` | Coturn authentication password |
| `TURN_REALM` | `remote-support.local` | Coturn authentication realm |

---

## 8. Verification & Testing

### Backend & Database Tests
```bash
docker compose exec -T backend python tests/test_api.py
```

### End-to-End Take Control & SSH Verification
```bash
docker compose exec -T backend python tests/test_take_control_e2e.py
```

### Frontend Build & Typecheck
```bash
cd tauri_agent
npm run build
```

### Agent Healthcheck
```bash
curl -s https://webmaster-meal-classroom-colony.trycloudflare.com/api/v1/agent/health
```

---

## 9. Security Model

- **Identity Separation:** Device IDs are routing identifiers; access is only granted upon explicit approval or authenticated PIN match.
- **End-to-End Encryption:** WebRTC media, control events, clipboard data, terminal I/O, and files are encrypted using DTLS-SRTP and SCTP.
- **Audit Logging:** Every connection request, approval, rejection, and session termination is permanently logged in PostgreSQL.
- **Clipboard Sync Safety:** Clipboard text synchronization enforces strict payload limits (max 64 KB).

---

## 10. License

MIT License. See [LICENSE](LICENSE) for details.
