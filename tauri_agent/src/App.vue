<template>
  <div class="app">
    <!-- ═══ Top Bar (Desktop Bar) ═══ -->
    <header class="topbar">
      <div class="topbar__left">
        <div class="topbar__logo" title="Remote Desktop Support">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <circle cx="12" cy="12" r="10" stroke="#00e5ff"/>
            <path d="M12 6v6l4 2" stroke="#fff"/>
            <circle cx="12" cy="12" r="2" fill="#00e5ff"/>
          </svg>
          <span class="brand-text">Remote<span class="brand-accent">Support</span></span>
        </div>

        <div class="topbar__connect">
          <svg class="topbar__search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#00e5ff" stroke-width="2.2">
            <circle cx="11" cy="11" r="8"/>
            <path d="m21 21-4.3-4.3"/>
          </svg>
          <input
            type="text"
            class="topbar__input font-mono"
            placeholder="Enter Device ID (AG-XXX-XXX-XXX)"
            :value="sessionCode"
            @input="formatCode"
            @keydown.enter.prevent="joinSession"
          />
          <button
            class="topbar__inline-connect-btn"
            :disabled="!isValidCode || isLoading"
            @click="joinSession"
            title="Connect to Remote Device (Press Enter)"
          >
            <svg v-if="!isLoading" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
            <span v-else class="spinner-sm"></span>
          </button>
        </div>
      </div>

      <div class="topbar__center">
        <span class="topbar__label">This Device:</span>
        <span class="topbar__status-badge" :title="`Status: ${agentStatus}`">
          <span :class="['status-dot', agentStatus === 'online' ? 'status-dot--online' : agentStatus === 'connected' ? 'status-dot--connected' : 'status-dot--offline']"></span>
        </span>
        <span :class="['topbar__address', 'font-mono', {'topbar__address--offline': agentStatus === 'offline'}]">
          {{ myAddress }}
        </span>
        <button class="topbar__icon-btn" :disabled="agentStatus === 'offline'" @click="copyAddress" title="Copy My Device ID">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        </button>
        <button class="topbar__icon-btn" @click="showSettings = true; settingsTab = 'security'" title="Security & Unattended PIN">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        </button>
      </div>

      <div class="topbar__right">
        <button class="topbar__icon-btn" title="Toggle Theme" @click="toggleTheme">
          <svg v-if="isLightMode" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        </button>
        <button class="topbar__icon-btn" title="Settings" @click="showSettings = true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
      </div>
    </header>

    <p v-if="errorMsg" class="global-error fade-in">{{ errorMsg }}</p>

    <!-- ═══ Main Content ═══ -->
    <main class="main">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- ═══ Incoming Connection Request Modal (Host-Side) ═══ -->
    <transition name="fade">
      <div v-if="device.incomingRequest.value" class="incoming-overlay">
        <div class="incoming-dialog">
          <div class="incoming-header">
            <span class="incoming-pulse-dot"></span>
            <h3>Incoming Connection Request</h3>
          </div>
          <div class="incoming-content">
            <div class="caller-card">
              <span class="caller-name">{{ device.incomingRequest.value.callerName }}</span>
              <span class="caller-id font-mono">Device ID: {{ device.incomingRequest.value.callerDeviceId }}</span>
            </div>
            <p class="incoming-sub">
              This computer requests access to view your screen and provide remote support.
            </p>
          </div>
          <div class="incoming-actions">
            <button class="btn btn--danger" @click="handleRejectIncoming">Reject</button>
            <button class="btn btn--primary" @click="handleAcceptIncoming">Accept Connection</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ═══ Caller Outgoing Request Waiting Modal ═══ -->
    <transition name="fade">
      <div v-if="outgoingRequestWaiting" class="incoming-overlay">
        <div class="incoming-dialog">
          <div class="incoming-header">
            <span class="spinner-sm" style="margin-right:10px"></span>
            <h3>Connecting to Remote Device...</h3>
          </div>
          <div class="incoming-content">
            <div class="caller-card">
              <span class="caller-name">Target Device</span>
              <span class="caller-id font-mono">{{ sessionCode }}</span>
            </div>
            <p class="incoming-sub">Waiting for the remote user to accept your connection request...</p>
          </div>
          <div class="incoming-actions">
            <button class="btn btn--secondary" @click="cancelOutgoingRequest">Cancel</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ═══ Global Settings Modal ═══ -->
    <transition name="fade">
      <div v-if="showSettings" class="settings-overlay" @click.self="showSettings = false">
        <div class="settings-modal">
          <div class="settings-sidebar">
            <h3 class="settings-sidebar__title">Settings</h3>
            <button :class="['st-tab', {'st-tab--active': settingsTab === 'user_interface'}]" @click="settingsTab = 'user_interface'">User Interface</button>
            <button :class="['st-tab', {'st-tab--active': settingsTab === 'security'}]" @click="settingsTab = 'security'">Security & PIN</button>
            <button :class="['st-tab', {'st-tab--active': settingsTab === 'network'}]" @click="settingsTab = 'network'">Network</button>
            <button :class="['st-tab', {'st-tab--active': settingsTab === 'about'}]" @click="settingsTab = 'about'">About</button>
          </div>

          <div class="settings-content">
            <div class="settings-header">
              <h2>{{ settingsTabTitle }}</h2>
              <button class="settings-close" @click="showSettings = false">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>

            <div class="settings-body">
              <!-- User Interface -->
              <div v-if="settingsTab === 'user_interface'" class="st-section">
                <div class="st-group">
                  <label>Device Name</label>
                  <input type="text" v-model="settings.deviceName" class="st-input" placeholder="e.g. My Laptop"/>
                  <p class="st-hint">Name displayed to remote computers when connecting.</p>
                </div>
                <div class="st-group">
                  <label>Language</label>
                  <select v-model="settings.language" class="st-input">
                    <option>English</option>
                    <option>German</option>
                    <option>French</option>
                    <option>Spanish</option>
                  </select>
                </div>
              </div>

              <!-- Security & PIN -->
              <div v-if="settingsTab === 'security'" class="st-section">
                <div class="st-group st-row">
                  <div class="st-text">
                    <label>Unattended Access</label>
                    <p class="st-hint">Allow connections with a secure PIN without requiring manual approval.</p>
                  </div>
                  <label class="toggle">
                    <input type="checkbox" v-model="settings.unattendedEnabled" @change="saveSecuritySettings"/>
                    <span class="toggle__slider"></span>
                  </label>
                </div>

                <div v-if="settings.unattendedEnabled" class="st-group">
                  <label>Unattended Access PIN</label>
                  <input
                    type="password"
                    v-model="settings.unattendedPin"
                    class="st-input"
                    placeholder="Enter secure access PIN"
                    @change="saveSecuritySettings"
                  />
                  <p class="st-hint">Never share your PIN publicly. Anyone with this PIN can access this device.</p>
                </div>

                <div class="st-group">
                  <p class="st-hint">Permanent Device ID: <strong class="font-mono">{{ myAddress }}</strong></p>
                  <p class="st-hint">Device authentication uses SHA-256 tokens and constant-time comparison.</p>
                </div>
              </div>

              <!-- Network & Signaling -->
              <div v-if="settingsTab === 'network'" class="st-section">
                <div class="st-group">
                  <label>Signaling Server URL</label>
                  <input type="text" v-model="settings.signalingServer" class="st-input" placeholder="ws://localhost:8000/ws/"/>
                  <p class="st-hint">Self-hosted Remote Desktop server address (ws://, wss://, http://, https://).</p>
                </div>
                <div class="st-group">
                  <label>STUN Servers (one per line)</label>
                  <textarea v-model="settings.stunServers" class="st-input" rows="3" placeholder="stun:stun.l.google.com:19302"></textarea>
                </div>
                <div class="st-group">
                  <label>TURN Relay Servers (optional)</label>
                  <textarea v-model="settings.turnServers" class="st-input" rows="3" placeholder="turn:relay.example.com:3478?transport=udp"></textarea>
                  <p class="st-hint">Required as fallback when direct P2P cannot traverse symmetric NAT.</p>
                </div>
                <div class="st-group">
                  <label>TURN Username</label>
                  <input type="text" v-model="settings.turnUsername" class="st-input" placeholder="remote"/>
                </div>
                <div class="st-group">
                  <label>TURN Password</label>
                  <input type="password" v-model="settings.turnPassword" class="st-input" placeholder="Relay password"/>
                </div>
                <div class="st-group st-row">
                  <div class="st-text">
                    <label>Always Use Relay (Force TURN)</label>
                    <p class="st-hint">Force all traffic through TURN server if direct P2P is restricted.</p>
                  </div>
                  <label class="toggle"><input type="checkbox" v-model="settings.alwaysRelay"/><span class="toggle__slider"></span></label>
                </div>
              </div>

              <!-- About -->
              <div v-if="settingsTab === 'about'" class="st-section">
                <div class="about-box">
                  <h3>Remote Desktop Support</h3>
                  <p>Self-Hosted Remote Desktop Support Platform.</p>
                  <p>WebRTC encrypted peer-to-peer transport with STUN discovery and TURN fallback.</p>
                  <p class="text-muted">License: MIT</p>
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watchEffect, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDevice } from './composables/useDevice'
import { useMyAddress } from './composables/useMyAddress'
import { useSessions } from './composables/useSessions'
import { useHostSession } from './composables/useHostSession'
import { apiUrl, isNativeApp, loadNetworkSettings } from './composables/serverConfig'

const router = useRouter()
const device = useDevice()
const { myAddress, agentStatus } = useMyAddress()
const { addToHistory } = useSessions()
const hostSession = useHostSession()
const nativeHost = isNativeApp()

const sessionCode = ref('')
const isLoading = ref(false)
const errorMsg = ref('')
const showSettings = ref(false)
const isLightMode = ref(false)
const outgoingRequestWaiting = ref(false)
let outgoingPollTimer = null

// ─── Settings State ─────────────────────────────────────
const settingsTab = ref('user_interface')
const settingsTabTitle = computed(() => {
  const map = {
    user_interface: 'User Interface',
    security: 'Security & PIN',
    network: 'Network & Relay',
    about: 'About Remote Desktop',
  }
  return map[settingsTab.value]
})

const defaultSettings = {
  deviceName: '',
  language: 'English',
  unattendedEnabled: false,
  unattendedPin: '',
  alwaysRelay: false,
  signalingServer: loadNetworkSettings().signalingServer,
  stunServers: 'stun:stun.l.google.com:19302\nstun:stun1.l.google.com:19302',
  turnServers: '',
  turnUsername: '',
  turnPassword: '',
}

const settings = ref({ ...defaultSettings })

// Load from LocalStorage
try {
  const stored = localStorage.getItem('ad_settings')
  if (stored) settings.value = { ...defaultSettings, ...JSON.parse(stored) }
} catch (e) {}

// Save to LocalStorage
watch(() => settings.value, (newVal) => {
  localStorage.setItem('ad_settings', JSON.stringify(newVal))
}, { deep: true })

async function saveSecuritySettings() {
  localStorage.setItem('ad_settings', JSON.stringify(settings.value))
  await device.registerDevice()
}

// ─── Theme ──────────────────────────────────────────────
watchEffect(() => {
  if (isLightMode.value) {
    document.body.classList.add('theme-light')
  } else {
    document.body.classList.remove('theme-light')
  }
})

function toggleTheme() {
  isLightMode.value = !isLightMode.value
}

// Check valid Device ID or session code
const isValidCode = computed(() => {
  const val = (sessionCode.value || '').trim()
  return val.length >= 3
})

function normalizeInputCode(val) {
  const raw = (val || '').trim().toUpperCase()
  if (!raw) return ''
  const digits = raw.replace(/[^0-9]/g, '')
  if (digits.length === 9) {
    return `AG-${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6, 9)}`
  }
  return raw
}

function formatCode(e) {
  let v = (e.target.value || '').toUpperCase()
  const input = e.target
  const selectionStart = input ? input.selectionStart : null

  let digits = v.replace(/[^0-9]/g, '')
  if (digits.length > 9) digits = digits.slice(0, 9)

  let formatted = ''
  if (digits.length > 0) {
    formatted = `AG-${digits.slice(0, 3)}`
    if (digits.length > 3) formatted += `-${digits.slice(3, 6)}`
    if (digits.length > 6) formatted += `-${digits.slice(6, 9)}`
  } else {
    formatted = v
  }

  sessionCode.value = formatted
  if (input && selectionStart !== null) {
    nextTick(() => {
      try {
        input.setSelectionRange(selectionStart, selectionStart)
      } catch (_) {}
    })
  }
}

async function joinSession() {
  const raw = (sessionCode.value || '').trim()
  if (!raw || isLoading.value) return
  const targetId = normalizeInputCode(raw)
  if (!targetId) return

  isLoading.value = true
  errorMsg.value = ''

  // 1. Immediately record in connection history
  addToHistory({ code: targetId, id: targetId, host_online: true })

  // 2. Dispatch connection notification to backend in background
  try {
    fetch(apiUrl('/api/v1/sessions/connect', loadNetworkSettings()), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        caller_device_id: device.deviceId.value || 'AG-000-000-000',
        caller_name: device.deviceName.value || 'Remote Client',
        target_device_id: targetId,
      }),
    }).catch(() => {})
  } catch (_) {}

  // 3. Immediately launch the remote session connection screen!
  router.push({ name: 'Session', params: { code: targetId } })
  isLoading.value = false
}

async function legacyJoin(code) {
  const r = await fetch(apiUrl('/api/session/join/', loadNetworkSettings()), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  const d = await r.json()
  if (!r.ok) throw new Error(d.detail || d.error || 'Remote device offline or not found')
  if (d.session) addToHistory(d.session)
  router.push({ name: 'Session', params: { code } })
}

function pollRequestApproval(requestId, targetId) {
  if (outgoingPollTimer) clearInterval(outgoingPollTimer)
  outgoingPollTimer = setInterval(async () => {
    try {
      const res = await fetch(apiUrl(`/api/v1/sessions/request/${requestId}`, loadNetworkSettings()))
      if (!res.ok) return
      const data = await res.json()
      if (data.status === 'accepted') {
        cancelOutgoingRequest()
        addToHistory({ code: targetId, id: targetId, host_online: true })
        router.push({ name: 'Session', params: { code: targetId } })
      } else if (data.status === 'rejected') {
        cancelOutgoingRequest()
        errorMsg.value = 'Connection rejected by remote host.'
        setTimeout(() => { errorMsg.value = '' }, 4000)
      }
    } catch (_) {}
  }, 2000)
}

function cancelOutgoingRequest() {
  outgoingRequestWaiting.value = false
  if (outgoingPollTimer) {
    clearInterval(outgoingPollTimer)
    outgoingPollTimer = null
  }
}

async function handleAcceptIncoming() {
  const req = device.incomingRequest.value
  if (!req) return
  try {
    await device.acceptRequest(req.requestId)
    // Start host sharing session immediately
    await hostSession.start()
    router.push('/host')
  } catch (e) {
    errorMsg.value = 'Failed to accept request'
  }
}

async function handleRejectIncoming() {
  const req = device.incomingRequest.value
  if (req) {
    await device.rejectRequest(req.requestId)
  }
}

function copyAddress() {
  if (agentStatus.value === 'offline') return
  navigator.clipboard?.writeText(myAddress.value.replace(/\s/g, ''))
}

onMounted(async () => {
  await device.registerDevice()
})
</script>

<style>
:root {
  --ad-bg-dark: #18191c;
  --ad-surface-dark: #202226;
  --ad-border-dark: #2e3138;
  --ad-text-dark: #e1e4ea;
  --ad-text-muted-dark: #8b92a0;

  --ad-bg-light: #f5f6f8;
  --ad-surface-light: #ffffff;
  --ad-border-light: #e0e3e8;
  --ad-text-light: #1f2328;
  --ad-text-muted-light: #656d76;

  --ad-bg: var(--ad-bg-dark);
  --ad-surface: var(--ad-surface-dark);
  --ad-border: var(--ad-border-dark);
  --ad-text: var(--ad-text-dark);
  --ad-text-muted: var(--ad-text-muted-dark);
  --color-accent-primary: #00bcd4;
}

body.theme-light {
  --ad-bg: var(--ad-bg-light);
  --ad-surface: var(--ad-surface-light);
  --ad-border: var(--ad-border-light);
  --ad-text: var(--ad-text-light);
  --ad-text-muted: var(--ad-text-muted-light);
}

.brand-text {
  font-size: 0.95rem;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.02em;
  margin-left: 6px;
}
.brand-accent {
  color: #00e5ff;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  background: #111215;
  border-bottom: 1px solid var(--ad-border);
  padding: 0 16px;
  user-select: none;
}
.topbar__left, .topbar__center, .topbar__right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.topbar__logo {
  display: flex;
  align-items: center;
}
.topbar__connect {
  display: flex;
  align-items: center;
  background: #18191d;
  border: 1px solid #33363f;
  border-radius: 8px;
  padding: 3px 6px 3px 10px;
  gap: 8px;
  transition: all 0.2s ease;
}
.topbar__connect:focus-within {
  border-color: #00e5ff;
  box-shadow: 0 0 0 2px rgba(0, 229, 255, 0.15);
  background: #1c1d22;
}
.topbar__search-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.85;
}
.topbar__input {
  background: transparent;
  border: none;
  outline: none;
  color: #fff;
  font-size: 0.84rem;
  width: 255px;
  padding: 3px 4px;
  letter-spacing: 0.04em;
}
.topbar__input::placeholder {
  color: #626673;
}
.topbar__inline-connect-btn {
  background: #00e5ff;
  color: #0a0b0d;
  border: none;
  border-radius: 5px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s ease;
}
.topbar__inline-connect-btn:hover:not(:disabled) {
  background: #33ecff;
  transform: scale(1.05);
}
.topbar__inline-connect-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  background: #2a2c33;
  color: #666;
}
.topbar__status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 0 2px;
}
.topbar__address {
  font-size: 0.95rem;
  font-weight: 700;
  color: #00e5ff;
  letter-spacing: 0.05em;
  background: rgba(0, 229, 255, 0.08);
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid rgba(0, 229, 255, 0.2);
}
.topbar__address--offline {
  color: #888;
  border-color: #444;
  background: transparent;
}
.topbar__icon-btn {
  background: transparent;
  border: none;
  color: #aaa;
  cursor: pointer;
  padding: 6px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.topbar__icon-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}
.topbar__connect-btn {
  background: #00bcd4;
  border: none;
  color: #fff;
  border-radius: 6px;
  padding: 6px 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: opacity 0.2s;
}
.topbar__connect-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Incoming Modal */
.incoming-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.incoming-dialog {
  background: #1f2126;
  border: 1px solid #3a3e47;
  border-radius: 14px;
  padding: 28px;
  max-width: 440px;
  width: 90%;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6);
}
.incoming-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.incoming-header h3 {
  font-size: 1.15rem;
  color: #fff;
  font-weight: 600;
}
.incoming-pulse-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #00e5ff;
  box-shadow: 0 0 12px #00e5ff;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}
.caller-card {
  background: #16171b;
  border: 1px solid #2b2e36;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 14px;
}
.caller-name {
  font-size: 1rem;
  font-weight: 600;
  color: #fff;
}
.caller-id {
  font-size: 0.9rem;
  color: #00e5ff;
  letter-spacing: 0.05em;
}
.incoming-sub {
  color: #9aa0ac;
  font-size: 0.88rem;
  line-height: 1.5;
  margin-bottom: 22px;
}
.incoming-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
