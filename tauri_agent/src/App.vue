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
      <div v-if="hasIncomingRequest" class="incoming-overlay">
        <div class="incoming-dialog">
          <div class="incoming-header">
            <span class="incoming-pulse-dot"></span>
            <h3>Incoming Connection Request</h3>
          </div>
          <div class="incoming-content">
            <div class="caller-card">
              <span class="caller-name">{{ incomingCallerName }}</span>
              <span class="caller-id font-mono">Device ID: {{ incomingCallerId }}</span>
              <span v-if="incomingCallerVerified" class="caller-verified">Verified device</span>
              <span v-else class="caller-unverified">
                Unverified: this name and Device ID were not confirmed and may be fake.
                Only accept if you are expecting this connection.
              </span>
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
                  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px">
                    <p class="st-hint" style="margin:0">Device ID: <strong class="font-mono">{{ myAddress }}</strong></p>
                    <button class="btn btn--secondary btn--sm" @click="handleRollNewDeviceId" style="font-size:0.75rem; padding:4px 8px">Regenerate ID</button>
                  </div>
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

const hasIncomingRequest = computed(() => {
  // If user is currently in a remote session as caller, never show incoming host request modal
  if (router.currentRoute.value?.name === 'Session') return false

  // If host is already connected and controlling/sharing screen, never show incoming request modal
  if (hostSession.controlEnabled.value || hostSession.state.value === 'connected') return false

  const req = device.incomingRequest.value
  const hasPending = hostSession.pendingController.value
  return Boolean(req || hasPending)
})
const incomingCallerName = computed(() => device.incomingRequest.value?.callerName || hostSession.incomingCallerName.value || 'Remote Controller')
const incomingCallerId = computed(() => device.incomingRequest.value?.callerDeviceId || hostSession.incomingCallerId.value || 'Remote Peer')
const incomingCallerVerified = computed(() => device.incomingRequest.value
  ? device.incomingRequest.value.callerVerified === true
  : hostSession.incomingCallerVerified.value)

const sessionCode = ref('')
const isLoading = ref(false)
const errorMsg = ref('')
const showSettings = ref(false)
const savedTheme = (() => {
  try {
    return localStorage.getItem('remote_support_theme')
  } catch (_) {
    return null
  }
})()
const isLightMode = ref(savedTheme === 'light')
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
    try { localStorage.setItem('remote_support_theme', 'light') } catch (_) {}
  } else {
    document.body.classList.remove('theme-light')
    try { localStorage.setItem('remote_support_theme', 'dark') } catch (_) {}
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

  // Prevent connecting to self
  if (targetId === device.deviceId.value) {
    errorMsg.value = 'Cannot connect to your own Device ID. Please enter another device ID.'
    setTimeout(() => { errorMsg.value = '' }, 4000)
    return
  }

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

// requestToken: the request_token returned by /api/v1/sessions/connect; only its holder may poll
function pollRequestApproval(requestId, requestToken, targetId) {
  if (outgoingPollTimer) clearInterval(outgoingPollTimer)
  outgoingPollTimer = setInterval(async () => {
    try {
      const res = await fetch(apiUrl(`/api/v1/sessions/request/${requestId}`, loadNetworkSettings()), {
        headers: { Authorization: `Bearer ${requestToken}` },
      })
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
  const requestId = req?.requestId

  if (requestId) {
    device.markRequestHandled?.(requestId)
  }

  // CRITICAL FIX FOR CHROME / BROWSER:
  // getDisplayMedia() MUST be called directly in this user click gesture.
  // Any awaits (network requests, router navigation) prior to calling getDisplayMedia()
  // will cause Chrome to invalidate the transient user activation, throwing:
  // "DOMException: getDisplayMedia must be called from a user gesture."
  let ok = false
  if (hostSession.localStream.value) {
    ok = true
  } else {
    ok = await hostSession.start()
  }

  // Dismiss modal after screen selection attempt
  device.clearIncomingRequest?.()
  hostSession.pendingController.value = false

  if (!ok) {
    errorMsg.value = 'Screen sharing was cancelled or not selected.'
    setTimeout(() => { errorMsg.value = '' }, 4000)
    return
  }

  try {
    if (requestId && !requestId.startsWith('direct-')) {
      device.acceptRequest(requestId).catch(() => {})
    }
    // Purge pending requests in Redis on backend
    device.clearBackendPendingRequest?.().catch(() => {})

    // Navigate to host screen if not already there
    if (router.currentRoute.value?.name !== 'Host') {
      await router.push('/host')
    }
    // Initiate WebRTC offer immediately
    await hostSession.allowController(true)
  } catch (e) {
    errorMsg.value = 'Failed to accept connection request'
    setTimeout(() => { errorMsg.value = '' }, 4000)
  }
}

async function handleRejectIncoming() {
  const req = device.incomingRequest.value
  if (req?.requestId) {
    device.markRequestHandled?.(req.requestId)
  }
  device.clearIncomingRequest?.()
  hostSession.pendingController.value = false
  if (req && req.requestId && !req.requestId.startsWith('direct-')) {
    await device.rejectRequest(req.requestId).catch(() => {})
  }
  device.clearBackendPendingRequest?.().catch(() => {})
  hostSession.denyController?.()
}

async function handleRollNewDeviceId() {
  if (confirm('Generate a new Device ID for this browser tab/window?')) {
    await device.resetDeviceId()
    await hostSession.ensureOnline()
  }
}

function copyAddress() {
  if (agentStatus.value === 'offline') return
  navigator.clipboard?.writeText(myAddress.value.replace(/\s/g, ''))
}

onMounted(async () => {
  window.addEventListener('open-settings', (e) => {
    showSettings.value = true
    if (e.detail?.tab) settingsTab.value = e.detail.tab
  })
  await device.registerDevice()
  await hostSession.ensureOnline()
})
</script>

<style>
.brand-text {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--ad-text);
  letter-spacing: -0.02em;
  margin-left: 6px;
}
.brand-accent {
  color: var(--ad-accent);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 48px;
  background: var(--ad-topbar);
  border-bottom: 1px solid var(--ad-border);
  padding: 0 16px;
  user-select: none;
  transition: background var(--transition-base), border-color var(--transition-base);
}
.topbar__left, .topbar__center, .topbar__right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.topbar__logo {
  display: flex;
  align-items: center;
  cursor: pointer;
  flex-shrink: 0;
}
.topbar__connect {
  display: flex;
  align-items: center;
  background: var(--ad-input-bg);
  border: 1px solid var(--ad-input-border);
  border-radius: 8px;
  padding: 3px 6px 3px 10px;
  gap: 8px;
  transition: all var(--transition-fast);
}
.topbar__connect:focus-within {
  border-color: var(--ad-accent);
  box-shadow: 0 0 0 2px var(--ad-accent-glow);
  background: var(--ad-surface);
}
.topbar__search-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  stroke: var(--ad-accent);
}
.topbar__input {
  background: transparent;
  border: none;
  outline: none;
  color: var(--ad-input-text);
  font-size: 0.84rem;
  width: 255px;
  padding: 3px 4px;
  letter-spacing: 0.04em;
}
.topbar__input::placeholder {
  color: var(--ad-input-placeholder);
}
.topbar__inline-connect-btn {
  background: var(--ad-accent);
  color: #fff;
  border: none;
  border-radius: 5px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--transition-fast);
}
.topbar__inline-connect-btn:hover:not(:disabled) {
  background: var(--ad-accent-hover);
  transform: scale(1.05);
}
.topbar__inline-connect-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  background: var(--ad-surface-hover);
  color: var(--ad-text-muted);
}
.topbar__label {
  font-size: 0.8rem;
  color: var(--ad-text-muted);
  font-weight: 500;
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
  color: var(--ad-accent);
  letter-spacing: 0.05em;
  background: var(--ad-accent-subtle);
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid var(--ad-accent-glow);
}
.topbar__address--offline {
  color: var(--ad-text-muted);
  border-color: var(--ad-border);
  background: transparent;
}
.topbar__icon-btn {
  background: transparent;
  border: none;
  color: var(--ad-text-secondary);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}
.topbar__icon-btn:hover {
  background: var(--ad-surface-hover);
  color: var(--ad-text);
}
.topbar__icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Modals */
.incoming-overlay, .settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}
.incoming-dialog {
  background: var(--ad-surface);
  border: 1px solid var(--ad-border);
  border-radius: 14px;
  padding: 28px;
  max-width: 440px;
  width: 90%;
  box-shadow: var(--ad-shadow);
  color: var(--ad-text);
}
.incoming-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.incoming-header h3 {
  font-size: 1.15rem;
  color: var(--ad-text);
  font-weight: 600;
}
.incoming-pulse-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--ad-accent);
  box-shadow: 0 0 12px var(--ad-accent);
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}
.caller-card {
  background: var(--ad-surface-alt);
  border: 1px solid var(--ad-border);
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
  color: var(--ad-text);
}
.caller-id {
  font-size: 0.9rem;
  color: var(--ad-accent);
  letter-spacing: 0.05em;
}
.caller-verified {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--ad-status-online);
}
.caller-unverified {
  font-size: 0.82rem;
  font-weight: 600;
  line-height: 1.4;
  color: var(--color-accent-red);
}
.incoming-sub {
  color: var(--ad-text-muted);
  font-size: 0.88rem;
  line-height: 1.5;
  margin-bottom: 22px;
}
.incoming-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* Settings Modal */
.settings-modal {
  background: var(--ad-surface);
  border: 1px solid var(--ad-border);
  border-radius: 14px;
  width: 720px;
  max-width: 100%;
  height: 520px;
  max-height: 90vh;
  display: flex;
  overflow: hidden;
  box-shadow: var(--ad-shadow);
  color: var(--ad-text);
}
.settings-sidebar {
  width: 210px;
  background: var(--ad-sidebar);
  border-right: 1px solid var(--ad-border);
  padding: 18px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}
.settings-sidebar__title {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ad-text-muted);
  padding: 6px 12px;
  margin-bottom: 6px;
  font-weight: 700;
}
.st-tab {
  text-align: left;
  padding: 10px 14px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--ad-text-secondary);
  font-size: 0.88rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.st-tab:hover {
  background: var(--ad-surface-hover);
  color: var(--ad-text);
}
.st-tab--active {
  background: var(--ad-accent-subtle);
  color: var(--ad-accent);
  font-weight: 600;
}
.settings-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--ad-surface);
  min-width: 0;
}
.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--ad-border);
}
.settings-header h2 {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--ad-text);
}
.settings-close {
  background: transparent;
  border: none;
  color: var(--ad-text-secondary);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}
.settings-close:hover {
  background: var(--ad-surface-hover);
  color: var(--ad-text);
}
.settings-body {
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
}
.st-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.st-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.st-group label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ad-text);
}
.st-row {
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.st-input {
  background: var(--ad-input-bg);
  border: 1px solid var(--ad-input-border);
  color: var(--ad-input-text);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 0.88rem;
  font-family: inherit;
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.st-input:focus {
  border-color: var(--ad-accent);
  box-shadow: 0 0 0 2px var(--ad-accent-glow);
}
.st-hint {
  font-size: 0.78rem;
  color: var(--ad-text-muted);
  line-height: 1.4;
}
.about-box {
  background: var(--ad-surface-alt);
  border: 1px solid var(--ad-border);
  border-radius: 10px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--ad-text);
}

/* Toggle Switch */
.toggle {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}
.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}
.toggle__slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background: var(--ad-border);
  transition: var(--transition-fast);
  border-radius: 24px;
}
.toggle__slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background: white;
  transition: var(--transition-fast);
  border-radius: 50%;
}
.toggle input:checked + .toggle__slider {
  background: var(--ad-accent);
}
.toggle input:checked + .toggle__slider:before {
  transform: translateX(20px);
}

/* Responsive Topbar */
@media (max-width: 900px) {
  .topbar {
    height: auto;
    padding: 8px 14px;
    flex-wrap: wrap;
    gap: 8px;
  }
  .topbar__left {
    order: 1;
    flex: 1;
    justify-content: flex-start;
  }
  .topbar__right {
    order: 2;
  }
  .topbar__center {
    order: 3;
    width: 100%;
    justify-content: space-between;
    padding-top: 6px;
    border-top: 1px solid var(--ad-border);
  }
  .topbar__input {
    width: 180px;
  }
}

@media (max-width: 600px) {
  /* Row 1: logo + icons, row 2: full-width Device ID search, row 3: this device */
  .topbar__left {
    display: contents;
  }
  .topbar__logo {
    order: 1;
    flex: 1;
  }
  .topbar__right {
    order: 2;
  }
  .topbar__connect {
    order: 3;
    width: 100%;
    min-width: 0;
  }
  .topbar__input {
    flex: 1;
    min-width: 0;
  }
  .topbar__center {
    order: 4;
  }
  .topbar__address {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

@media (max-width: 600px) {
  .incoming-dialog {
    width: 100%;
    padding: 20px 18px;
  }
  .incoming-actions {
    flex-direction: column-reverse;
  }
  .incoming-actions > .btn {
    width: 100%;
  }
  .topbar__connect {
    padding: 2px 4px 2px 8px;
  }
  .topbar__input {
    font-size: 0.78rem;
  }
  .topbar__label {
    display: none;
  }
  .settings-modal {
    flex-direction: column;
    height: auto;
    max-height: 85vh;
  }
  .settings-sidebar {
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
    border-right: none;
    border-bottom: 1px solid var(--ad-border);
    padding: 8px;
  }
  .settings-sidebar__title {
    display: none;
  }
  .st-tab {
    padding: 6px 10px;
    white-space: nowrap;
  }
}
</style>
