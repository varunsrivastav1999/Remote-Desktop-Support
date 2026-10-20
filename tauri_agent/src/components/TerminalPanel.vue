<template>
  <transition name="slide">
    <div v-if="visible" class="terminal-panel">
      <!-- Top Header -->
      <header class="term-topbar">
        <div class="term-header-left">
          <div class="term-title-row">
            <span class="term-title">Remote Terminal / SSH</span>
            <span class="term-badge term-badge--remote">
              <span class="badge-dot"></span>
              REMOTE: {{ remoteDeviceId || 'Remote Host' }}
            </span>
          </div>
          <div v-if="remoteInfo.hostname || remoteInfo.username" class="term-system-meta font-mono">
            {{ remoteInfo.username }}@{{ remoteInfo.hostname }}
            <span v-if="remoteInfo.primary_ip">({{ remoteInfo.primary_ip }})</span>
            <span class="term-os-tag">{{ remoteInfo.os_name || 'Remote Host' }}</span>
          </div>
        </div>

        <div class="term-header-actions">
          <button class="term-btn-action" @click="handleReconnect" title="Reconnect Session">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
            <span>Reconnect</span>
          </button>
          <button class="term-btn-action" @click="clearTerminal" title="Clear Screen">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            <span>Clear</span>
          </button>
          <button class="term-btn-close" @click="$emit('close')" title="Close Terminal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      </header>

      <!-- Mode Selector Tabs -->
      <div class="term-tabs">
        <button
          :class="['term-tab', { 'term-tab--active': mode === 'agent' }]"
          @click="switchMode('agent')"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          Remote Shell (Direct WebRTC P2P)
        </button>
        <button
          :class="['term-tab', { 'term-tab--active': mode === 'ssh' }]"
          @click="switchMode('ssh')"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          Direct SSH (sshd:22)
        </button>
      </div>

      <!-- SSH Credentials Drawer (Active in SSH mode) -->
      <div v-if="mode === 'ssh'" class="ssh-config-drawer">
        <div class="ssh-form-row">
          <div class="ssh-input-group">
            <label>Remote Host / IP</label>
            <input v-model="sshForm.host" placeholder="e.g. 192.168.1.100" class="ssh-input" />
          </div>
          <div class="ssh-input-group ssh-input-group--sm">
            <label>Port</label>
            <input v-model.number="sshForm.port" type="number" placeholder="22" class="ssh-input" />
          </div>
          <div class="ssh-input-group">
            <label>Remote User</label>
            <input v-model="sshForm.username" placeholder="e.g. ubuntu" class="ssh-input" />
          </div>
          <div class="ssh-input-group">
            <label>Password</label>
            <input v-model="sshForm.password" type="password" placeholder="Remote password" class="ssh-input" @keyup.enter="connectSSH" />
          </div>
          <div class="ssh-input-group ssh-input-group--btn">
            <button
              :disabled="sshConnecting"
              class="btn-ssh-connect"
              @click="connectSSH"
            >
              {{ sshConnecting ? 'Connecting...' : (sshConnected ? 'Disconnect' : 'Connect SSH') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Error / Alert Banner -->
      <div v-if="errorMessage" class="term-alert-banner">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <span>{{ errorMessage }}</span>
        <button class="term-alert-retry" @click="handleReconnect">Retry</button>
        <button class="term-alert-dismiss" @click="errorMessage = ''">&times;</button>
      </div>

      <!-- Terminal Container -->
      <div class="term-container" ref="terminalContainer"></div>
    </div>
  </transition>
</template>

<script setup>
import { ref, reactive, watch, onBeforeUnmount, nextTick } from 'vue'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'
import { apiUrl } from '../composables/serverConfig.js'

const props = defineProps({
  visible: Boolean,
  webrtc: Object,
  remoteDeviceId: {
    type: String,
    default: '',
  },
})

defineEmits(['close'])

const terminalContainer = ref(null)
const mode = ref('agent') // 'agent' | 'ssh'
const errorMessage = ref('')
const sshConnecting = ref(false)
const sshConnected = ref(false)

const remoteInfo = reactive({
  username: '',
  hostname: '',
  os_name: '',
  primary_ip: '',
  ssh_running: false,
})

const sshForm = reactive({
  host: '',
  port: 22,
  username: '',
  password: '',
})

let term = null
let fitAddon = null
let resizeObserver = null
let sshSocket = null

// Fetch remote machine metadata whenever device ID changes or panel opens
async function fetchRemoteMetadata() {
  // 1. Primary source: Direct WebRTC system_info from remote host
  const direct = props.webrtc?.hostInfo?.value
  if (direct) {
    if (direct.username) remoteInfo.username = direct.username
    if (direct.hostname) remoteInfo.hostname = direct.hostname
    if (direct.os_name) remoteInfo.os_name = direct.os_name
    const ip = direct.primary_ip || (Array.isArray(direct.lan_ips) ? direct.lan_ips[0] : '')
    if (ip) remoteInfo.primary_ip = ip
    if (direct.ssh_running !== undefined) remoteInfo.ssh_running = !!direct.ssh_running

    if (remoteInfo.primary_ip) sshForm.host = remoteInfo.primary_ip
    if (remoteInfo.username) sshForm.username = remoteInfo.username
  }

  // 2. Secondary source: Backend device system_info registry (needs the approved session's viewer token)
  const viewerToken = props.webrtc?.viewerToken?.value
  if (!props.remoteDeviceId || !viewerToken) return
  try {
    const res = await fetch(apiUrl(`/api/v1/devices/${props.remoteDeviceId}/system_info`), {
      headers: { Authorization: `Bearer ${viewerToken}` },
    })
    if (res.ok) {
      const d = await res.json()
      const info = d.info || {}
      if (info.username) remoteInfo.username = info.username
      if (info.hostname) remoteInfo.hostname = info.hostname
      if (info.os_name) remoteInfo.os_name = info.os_name
      const ip = info.primary_ip || (Array.isArray(info.lan_ips) ? info.lan_ips[0] : '')
      if (ip) remoteInfo.primary_ip = ip
      if (info.ssh_running !== undefined) remoteInfo.ssh_running = !!info.ssh_running

      if (remoteInfo.primary_ip && !sshForm.host) {
        sshForm.host = remoteInfo.primary_ip
      }
      if (remoteInfo.username && !sshForm.username) {
        sshForm.username = remoteInfo.username
      }
    }
  } catch (_) {}
}

watch(() => props.webrtc?.hostInfo?.value, (info) => {
  if (info) {
    if (info.username) remoteInfo.username = info.username
    if (info.hostname) remoteInfo.hostname = info.hostname
    if (info.os_name) remoteInfo.os_name = info.os_name
    const ip = info.primary_ip || (Array.isArray(info.lan_ips) ? info.lan_ips[0] : '')
    if (ip) remoteInfo.primary_ip = ip
    if (info.ssh_running !== undefined) remoteInfo.ssh_running = !!info.ssh_running

    if (remoteInfo.primary_ip) sshForm.host = remoteInfo.primary_ip
    if (remoteInfo.username) sshForm.username = remoteInfo.username
  }
}, { deep: true, immediate: true })

watch(() => props.visible, async (isVisible) => {
  if (isVisible) {
    fetchRemoteMetadata()
    await nextTick()
    if (!term && terminalContainer.value) {
      initTerminal()
    } else if (term) {
      fitAddon.fit()
    }
    nextTick(() => term?.focus())
  }
})

function switchMode(newMode) {
  if (mode.value === newMode) return
  mode.value = newMode
  errorMessage.value = ''

  if (newMode === 'agent') {
    if (sshSocket) {
      sshSocket.close()
      sshSocket = null
      sshConnected.value = false
    }
    printBanner()
  } else {
    term?.writeln('\r\n\x1b[1;36m[SSH Mode Active] Enter remote host credentials above and click Connect SSH.\x1b[0m\r\n')
  }
}

function printBanner() {
  if (!term) return
  term.writeln('\x1b[1;36m════════════════════════════════════════════════════════════════════\x1b[0m')
  term.writeln('  \x1b[1;32mREMOTE DESKTOP SUPPORT — SECURE REMOTE SHELL\x1b[0m')
  term.writeln(`  \x1b[1;37m• Target Machine: \x1b[1;33m${props.remoteDeviceId || 'Remote Device'}\x1b[0m \x1b[1;32m[REMOTE SYSTEM]\x1b[0m`)
  term.writeln('  \x1b[1;37m• Channel:        \x1b[1;34mEncrypted Direct WebRTC P2P DataChannel\x1b[0m')
  term.writeln('  \x1b[1;37m• Scope:          \x1b[1;35mCommands execute on the CONNECTED REMOTE LAPTOP\x1b[0m')
  term.writeln('\x1b[1;36m════════════════════════════════════════════════════════════════════\x1b[0m\r\n$ ')
}

function initTerminal() {
  term = new Terminal({
    cursorBlink: true,
    fontFamily: '"Fira Code", "Courier New", monospace',
    fontSize: 13,
    theme: {
      background: '#141416',
      foreground: '#d4d4d4',
      cursor: '#e53935',
      selectionBackground: 'rgba(229, 57, 53, 0.3)',
    },
  })

  fitAddon = new FitAddon()
  term.loadAddon(fitAddon)
  term.open(terminalContainer.value)
  fitAddon.fit()

  printBanner()

  // Terminal input handler
  term.onData((data) => {
    if (mode.value === 'ssh') {
      if (sshSocket && sshSocket.readyState === WebSocket.OPEN) {
        sshSocket.send(data)
      }
    } else {
      if (props.webrtc) {
        props.webrtc.sendTerminalData(data)
      }
    }
  })

  // Resize handling
  resizeObserver = new ResizeObserver(() => {
    try {
      fitAddon?.fit()
      if (mode.value === 'ssh' && sshSocket && sshSocket.readyState === WebSocket.OPEN && term) {
        sshSocket.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
      }
    } catch (_) {}
  })
  resizeObserver.observe(terminalContainer.value)
}

// Receive output from host via WebRTC data channel
watch(() => props.webrtc, (webrtcObj) => {
  if (webrtcObj) {
    webrtcObj.setTerminalCallback((data) => {
      if (mode.value === 'agent' && term) {
        term.write(data)
      }
    })
  }
}, { immediate: true })

// Connect to Remote SSH via WebSocket bridge
function connectSSH() {
  if (sshConnected.value) {
    // Disconnect
    if (sshSocket) {
      sshSocket.close()
      sshSocket = null
    }
    sshConnected.value = false
    sshConnecting.value = false
    term?.writeln('\r\n\x1b[1;33m[SSH] Disconnected from remote host.\x1b[0m\r\n')
    return
  }

  if (!sshForm.host) {
    errorMessage.value = 'Please enter the remote host IP address.'
    return
  }
  if (!sshForm.username) {
    errorMessage.value = 'Please enter the remote username.'
    return
  }

  errorMessage.value = ''
  sshConnecting.value = true

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const targetDeviceId = props.remoteDeviceId || 'default'
  const wsUrl = `${protocol}//${host}/ws/ssh/${targetDeviceId}`

  try {
    sshSocket = new WebSocket(wsUrl)
  } catch (err) {
    sshConnecting.value = false
    errorMessage.value = `Could not create SSH WebSocket: ${err.message}`
    return
  }

  const timeoutTimer = setTimeout(() => {
    if (sshConnecting.value) {
      sshConnecting.value = false
      errorMessage.value = `SSH connection to ${sshForm.host}:${sshForm.port} timed out after 12s.`
      term?.writeln(`\r\n\x1b[1;31m[!] SSH connection to ${sshForm.host}:${sshForm.port} timed out.\x1b[0m\r\n`)
      if (sshSocket) sshSocket.close()
    }
  }, 12000)

  sshSocket.onopen = () => {
    // The bridge only opens for the controller of an approved session
    sshSocket.send(JSON.stringify({ type: 'auth', token: props.webrtc?.viewerToken?.value || '' }))
    term?.writeln(`\r\n\x1b[1;36m[SSH] Connecting to ${sshForm.username}@${sshForm.host}:${sshForm.port}...\x1b[0m\r\n`)
    sshSocket.send(JSON.stringify({
      type: 'connect',
      host: sshForm.host,
      port: sshForm.port,
      username: sshForm.username,
      password: sshForm.password,
    }))
  }

  sshSocket.onmessage = (event) => {
    clearTimeout(timeoutTimer)
    try {
      const parsed = JSON.parse(event.data)
      if (parsed.type === 'connected') {
        sshConnecting.value = false
        sshConnected.value = true
        errorMessage.value = ''
        term?.writeln(`\r\n\x1b[1;32m[SSH Connected] Established session with ${parsed.target} (Remote Device: ${parsed.device_id})\x1b[0m\r\n`)
        return
      } else if (parsed.type === 'error') {
        sshConnecting.value = false
        sshConnected.value = false
        errorMessage.value = parsed.message
        term?.writeln(`\r\n\x1b[1;31m[!] ${parsed.message}\x1b[0m\r\n`)
        return
      } else if (parsed.type === 'target_info') {
        if (!sshForm.host && parsed.detected_ip) sshForm.host = parsed.detected_ip
        if (!sshForm.username && parsed.detected_user) sshForm.username = parsed.detected_user
        return
      }
    } catch (_) {}

    // Raw PTY text from remote SSH
    sshConnecting.value = false
    sshConnected.value = true
    term?.write(event.data)
  }

  sshSocket.onerror = () => {
    clearTimeout(timeoutTimer)
    sshConnecting.value = false
    sshConnected.value = false
    errorMessage.value = `SSH connection to ${sshForm.host} failed.`
  }

  sshSocket.onclose = () => {
    clearTimeout(timeoutTimer)
    sshConnecting.value = false
    sshConnected.value = false
  }
}

function handleReconnect() {
  errorMessage.value = ''
  if (mode.value === 'ssh') {
    connectSSH()
  } else {
    clearTerminal()
    printBanner()
    if (props.webrtc) {
      props.webrtc.sendTerminalData('\x03\r\nclear\r\n')
    }
  }
}

function clearTerminal() {
  term?.clear()
}

onBeforeUnmount(() => {
  if (resizeObserver && terminalContainer.value) {
    resizeObserver.unobserve(terminalContainer.value)
  }
  if (sshSocket) {
    sshSocket.close()
    sshSocket = null
  }
  if (term) {
    term.dispose()
    term = null
  }
})
</script>

<style scoped>
.terminal-panel {
  position: absolute;
  top: 0;
  bottom: 0;
  right: 0;
  width: 720px;
  max-width: 100%;
  background: #141416;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  z-index: 50;
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.6);
}

.slide-enter-active, .slide-leave-active {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-enter-from, .slide-leave-to {
  transform: translateX(100%);
}

.term-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #1b1b1e;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.term-header-left {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.term-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.term-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.01em;
}

.term-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
}

.term-badge--remote {
  background: rgba(46, 204, 113, 0.15);
  color: #2ecc71;
  border: 1px solid rgba(46, 204, 113, 0.35);
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 6px currentColor;
}

.term-system-meta {
  font-size: 0.74rem;
  color: rgba(255, 255, 255, 0.6);
  display: flex;
  align-items: center;
  gap: 8px;
}

.term-os-tag {
  background: rgba(255, 255, 255, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.75);
}

.term-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.term-btn-action {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.term-btn-action:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.term-btn-close {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}

.term-btn-close:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.term-tabs {
  display: flex;
  background: #111113;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0 12px;
  gap: 8px;
}

.term-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.term-tab:hover {
  color: #fff;
}

.term-tab--active {
  color: #fff;
  border-bottom-color: #e53935;
}

.ssh-config-drawer {
  padding: 10px 14px;
  background: #18181c;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.ssh-form-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.ssh-input-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 110px;
}

.ssh-input-group--sm {
  max-width: 70px;
  min-width: 60px;
}

.ssh-input-group--btn {
  flex: none;
}

.ssh-input-group label {
  font-size: 0.68rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
}

.ssh-input {
  background: #0f0f11;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 0.8rem;
  color: #fff;
  outline: none;
  width: 100%;
}

.ssh-input:focus {
  border-color: #e53935;
}

.btn-ssh-connect {
  background: #e53935;
  border: none;
  border-radius: 6px;
  padding: 7px 14px;
  color: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.btn-ssh-connect:hover {
  background: #d32f2f;
}

.btn-ssh-connect:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.term-alert-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: rgba(239, 68, 68, 0.15);
  border-bottom: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  font-size: 0.78rem;
}

.term-alert-retry {
  margin-left: auto;
  background: rgba(239, 68, 68, 0.3);
  border: 1px solid rgba(239, 68, 68, 0.5);
  border-radius: 4px;
  color: #fff;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 2px 8px;
  cursor: pointer;
}

.term-alert-dismiss {
  background: none;
  border: none;
  color: #fca5a5;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}

.term-container {
  flex: 1;
  padding: 12px 14px;
  overflow: hidden;
  background: #141416;
}
</style>
