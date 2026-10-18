# Remote Desktop Support — Production-Grade Self-Hosted Remote Desktop

**Remote Desktop Support** is a modern, high-performance, self-hosted remote desktop application inspired by AnyDesk and RustDesk. It allows two computers to connect seamlessly using a permanent, hardware-independent **Device ID** (`AG-XXX-XXX-XXX`), establishing direct peer-to-peer **WebRTC** sessions for low-latency screen control, interactive terminal access, bidirectional clipboard sync, and file transfer.

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
│                                                                        │
│  PostgreSQL (Persistent Storage)  │  Redis (Real-time Presence)        │
│  Coturn (TURN/STUN Relay)         │  Nginx (Web Controller UI)         │
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
             • Encrypted VP8/VP9/H.264 Video Stream
             • Mouse & Keyboard Input Injection (Rust Native)
             • Bidirectional Clipboard Synchronization
             • Interactive Remote Shell / Terminal Channel
             • P2P Secure File Transfer Channel
```

---

## 2. Key Features

- **Permanent Device ID (`AG-XXX-XXX-XXX`):** Securely generated, persistent across reboots, DHCP changes, router switches, and Wi-Fi $\leftrightarrow$ Ethernet transitions.
- **Direct P2P WebRTC Transmission:** Media and control data flow directly between peers without passing through the server when direct connection is achievable.
- **Coturn TURN Fallback:** Transparent relay fallback for symmetric NATs and restricted enterprise firewalls.
- **Live Consent & Unattended Access:**
  - **Attended Mode:** Host receives an incoming connection request popup with `[ ACCEPT ]` and `[ REJECT ]` buttons.
  - **Unattended Mode:** Optional Argon2/PBKDF2-hashed security PIN allows trusted remote access without local user interaction.
- **Native Input Injection:** Rust-powered mouse movement, multi-button clicks, scrolling, keyboard input, and OS shortcuts.
- **Interactive Shell / Terminal:** Direct terminal streaming over an authenticated WebRTC data channel without exposing SSH port 22 publicly.
- **Secure File Transfer:** Chunked binary transfer with path-traversal prevention, progress tracking, and size limits.
- **Resilient Reconnection:** Automatic exponential backoff, WebSocket session recovery, and WebRTC ICE restarts on network interruptions.
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

# Start all backend and controller services
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

## 4. Native Host Agent Setup

The native host agent runs on machines being controlled or connecting. It owns OS capture, display streaming, and accessibility injection permissions.

### Prerequisites
- Node.js $\ge$ 18 & npm
- Rust $\ge$ 1.75 (`curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`)
- Platform dependencies:
  - **macOS:** Grant *Screen Recording* and *Accessibility* permissions in System Settings.
  - **Linux:** `sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev`
  - **Windows:** Standard build tools (C++ desktop development workload).

### One-Command Launch (Docker + PM2 Tauri Agent)
To bring up the entire Docker stack and automatically launch the Tauri Host Agent in the background using PM2:
```bash
./start.sh
```
This runs:
1. `docker compose up -d` (PostgreSQL, Redis, Coturn, FastAPI Backend, Web App)
2. Waits for the backend healthcheck (`http://localhost:8000/health`)
3. Launches the Tauri host agent with PM2 via `ecosystem.config.js`

To manage the background agent:
```bash
# View live logs
npx pm2 logs remote-support-agent

# View process status
npx pm2 status

# Stop everything (PM2 agent + Docker containers)
./stop.sh
```

### Running Host Agent Manually in Development
```bash
cd tauri_agent
npm install
npm run tauri dev
```

### Building Production Installers
```bash
cd tauri_agent
npm run tauri build
```
Built binaries and native bundles are created in `tauri_agent/src-tauri/target/release/bundle/`:
- **macOS:** `.dmg` / `.app`
- **Linux:** `.deb` / `.AppImage`
- **Windows:** `.msi` / `.exe`

---

## 5. Connection Workflow

### Attended Support Flow
1. **Host (Computer B):** Starts Remote Desktop Support. The app generates or restores its permanent Device ID (e.g. `AG-735-281-904`) and registers with the backend.
2. **Controller (Computer A):** Enters `AG-735-281-904` and clicks **CONNECT**.
3. **Backend:** Locates Computer B, checks online presence, and pushes a connection request via WebSocket `/ws/device/AG-735-281-904`.
4. **Host (Computer B):** Displays incoming connection popup:
   ```text
   Incoming Connection Request
   Origin: Computer A (AG-482-193-721)
   [ ACCEPT ]   [ REJECT ]
   ```
5. **Session Established:** Upon acceptance, an authenticated session token is created, WebRTC SDP offer/answer exchange occurs, and the direct peer-to-peer connection is opened.

### Unattended Access Flow
1. **Host:** Configures an Unattended Access PIN in **Settings > Security**. The PIN is hashed using PBKDF2-HMAC-SHA256 (100,000 iterations) with a cryptographic salt before backend synchronization.
2. **Controller:** Enters the remote Device ID and PIN. The backend validates the hash and auto-approves the session without requiring local interaction.

---

## 6. Network Change & Reconnection Resilience

Remote Desktop Support is engineered for real-world network fluctuations:
- **DHCP / IP Address Changes:** The Device ID (`AG-XXX-XXX-XXX`) remains invariant. When an IP changes, the agent detects the network event, updates its presence on the backend, and gathers fresh ICE candidates.
- **Wi-Fi $\leftrightarrow$ Ethernet Switching:** The WebRTC layer detects connection state drops and initiates an **ICE Restart** without dropping the application session.
- **Backend or Network Downtime:** Both host and client employ exponential backoff reconnect algorithms (`1s` $\to$ `2s` $\to$ `4s` $\to$ max `30s`) to resume signaling immediately when connectivity returns.

---

## 7. Interactive Terminal & File Transfer

### Terminal / Shell
- **Zero Port 22 Exposure:** The interactive shell operates strictly inside the established WebRTC encrypted peer channel.
- **Native Process Integration:** Spawns a shell (`/bin/sh`, `$SHELL`, or `cmd.exe`) on the host machine, piping stdin/stdout/stderr to an xterm.js terminal panel.
- **Security:** Requires explicit session authorization; commands cannot be injected outside of active, authenticated sessions.

### File Transfer
- **Direct P2P Data Channel:** Transfers bypass the server entirely.
- **Path Traversal Protection:** All directory listings and file operations enforce strict path sandboxing.
- **Visual Progress:** Features live speed metrics, progress bars, and upload/download cancellation.

---

## 8. Configuration Reference (`.env`)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `POSTGRES_USER` | `rsadmin` | Database username |
| `POSTGRES_PASSWORD` | `support_2026` | Database password |
| `POSTGRES_DB` | `remote_support` | Database name |
| `POSTGRES_HOST_PORT` | `5433` | Host-mapped PostgreSQL port (avoids conflict with local port 5432) |
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

## 9. Verification & Automated Testing

### Backend & Database Tests
Run the comprehensive 7-stage backend integration test suite inside Docker:
```bash
docker compose run --rm backend python tests/test_api.py
```
Test suite covers:
1. PostgreSQL schema creation & table migrations
2. Device ID format generation & string normalization
3. Host agent registration & token verification
4. Redis heartbeat, presence TTL, and last-seen updates
5. Connection request lifecycle (`pending` $\to$ `accepted` $\to$ `active`)
6. Unattended access PIN hash validation
7. FastAPI REST endpoints (`/health`, `/api/v1/devices/*`, `/api/v1/sessions/*`)

### Frontend Build & Typecheck
```bash
cd tauri_agent
npm run build
```

### Native Rust Engine Check
```bash
cd tauri_agent/src-tauri
cargo check
```

---

## 10. Security Model

- **Permanent Identity Separation:** Device IDs are routing identifiers, not authentication tokens. Possession of a Device ID alone grants zero access.
- **Mandatory Approval:** Every connection requires either interactive approval from the host user or validation against a salted, hashed PIN.
- **End-to-End Encryption:** All WebRTC video, input events, clipboard data, terminal I/O, and files are encrypted using DTLS-SRTP and SCTP.
- **Audit Logging:** Every connection request, approval, rejection, and session termination is permanently logged in the PostgreSQL `audit_logs` table.
- **Safe Clipboard Sync:** Clipboard text synchronization enforces strict payload limits (max 64 KB) and filters arbitrary binary payloads.

---

## 11. License

MIT License. See [LICENSE](LICENSE) for details.
