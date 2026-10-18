<template>
  <div class="home">
    <div class="workspace">
      <!-- ═══ Left Panel: This Desk ═══ -->
      <aside class="this-desk">
        <div class="this-desk__card">
          <div class="this-desk__card-header">
            <h2 class="this-desk__title">This Device</h2>
            <span :class="['status-pill', agentStatus === 'online' ? 'status-pill--online' : agentStatus === 'connected' ? 'status-pill--connected' : 'status-pill--offline']">
              <span class="status-dot"></span>
              {{ agentStatus.toUpperCase() }}
            </span>
          </div>

          <p class="this-desk__label">Permanent Device ID</p>
          <div class="this-desk__address-row">
            <span :class="['this-desk__address', 'font-mono', {'this-desk__address--offline': agentStatus === 'offline'}]">
              {{ myAddress }}
            </span>
            <button class="copy-btn" @click="copyMyId" title="Copy Device ID">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
          </div>

          <p class="this-desk__sub">
            {{ deskStatus }}
          </p>
          <p v-if="host.error.value" class="desk-error">{{ host.error.value }}</p>

          <div class="this-desk__meta-box">
            <div class="meta-row">
              <span class="meta-label">Agent Version:</span>
              <span class="meta-val">Remote Desktop Agent 1.0</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">Transport:</span>
              <span class="meta-val">WebRTC P2P (Direct/STUN/TURN)</span>
            </div>
          </div>

          <div class="this-desk__setup-box">
            <p class="this-desk__label">Share this computer</p>
            <p class="this-desk__sub" style="margin-bottom:12px">Allow another remote client to view and control this screen upon your approval.</p>
            <button class="share-start" @click="startHosting">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6"/><path d="M10 14L21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>
              Share This Desk
            </button>
          </div>
        </div>
      </aside>

      <!-- ═══ Right Panel: Remote Desk & Dashboard ═══ -->
      <section class="remote-desk">
        <!-- Dashboard Metrics Banner -->
        <div class="dashboard-banner">
          <div class="metric-card">
            <span class="metric-num font-mono">{{ totalDevicesCount }}</span>
            <span class="metric-label">Network Devices</span>
          </div>
          <div class="metric-card">
            <span class="metric-num font-mono text-cyan">{{ onlineDevicesCount }}</span>
            <span class="metric-label">Online Devices</span>
          </div>
          <div class="metric-card">
            <span class="metric-num font-mono text-green">{{ history.length }}</span>
            <span class="metric-label">Recent Sessions</span>
          </div>
        </div>

        <!-- ═══ Quick Connect Bar ═══ -->
        <div class="quick-connect-bar">
          <div class="qc-input-wrap">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input
              type="text"
              v-model="quickConnectInput"
              placeholder="Enter Remote Device ID (e.g. AG-735-281-904)"
              class="qc-input font-mono"
              @keydown.enter="handleDirectConnect"
            />
          </div>
          <button class="qc-btn" :disabled="!quickConnectInput.trim()" @click="handleDirectConnect">
            Connect
          </button>
        </div>

        <!-- ═══ Tabs Row ═══ -->
        <div class="tabs-bar">
          <div class="tabs">
            <button v-for="tab in tabs" :key="tab.id" :class="['tab', {'tab--active': activeTab === tab.id}]" @click="activeTab = tab.id">
              {{ tab.label }}
            </button>
          </div>
          <div class="tabs-right">
            <select v-model="quality" class="quality-select" title="Connection Quality">
              <option value="low">Low Bandwidth</option>
              <option value="medium">Balanced</option>
              <option value="high">High Quality</option>
            </select>
            <div class="view-modes">
              <button :class="['vbtn', {'vbtn--active': viewMode === 'grid-lg'}]" @click="viewMode = 'grid-lg'" title="Large Grid">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/></svg>
              </button>
              <button :class="['vbtn', {'vbtn--active': viewMode === 'grid-sm'}]" @click="viewMode = 'grid-sm'" title="Small Grid">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="5" height="5" rx="1"/><rect x="10" y="3" width="5" height="5" rx="1"/><rect x="17" y="3" width="5" height="5" rx="1"/><rect x="3" y="10" width="5" height="5" rx="1"/><rect x="10" y="10" width="5" height="5" rx="1"/><rect x="17" y="10" width="5" height="5" rx="1"/><rect x="3" y="17" width="5" height="5" rx="1"/><rect x="10" y="17" width="5" height="5" rx="1"/><rect x="17" y="17" width="5" height="5" rx="1"/></svg>
              </button>
              <button :class="['vbtn', {'vbtn--active': viewMode === 'list'}]" @click="viewMode = 'list'" title="List View">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="4" width="18" height="3" rx="1"/><rect x="3" y="10.5" width="18" height="3" rx="1"/><rect x="3" y="17" width="18" height="3" rx="1"/></svg>
              </button>
            </div>
          </div>
        </div>

        <!-- ═══ Tab: Favorites ═══ -->
        <div v-if="activeTab === 'favorites'" class="tab-content">
          <div class="section-label">Favorites</div>
          <div v-if="favSessions.length" :class="gridClass">
            <div v-for="s in favSessions" :key="s.id" class="scard" @click="quickConnect(s.code)">
              <div class="scard__thumb" :style="{ background: getColor(s.id) }">
                <span :class="['sdot', s.host_online ? 'sdot--on' : 'sdot--off']"></span>
                <button class="scard__star" @click.stop="toggleFav(s)"><svg width="12" height="12" viewBox="0 0 24 24" fill="#f59e0b" stroke="#f59e0b" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></button>
              </div>
              <div class="scard__info">
                <div class="scard__row">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                  <span class="scard__name">{{ getDisplayName(s) }}</span>
                </div>
                <span class="scard__code font-mono">{{ s.code }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="1.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
            <p class="empty-state__title">No Favorites</p>
            <p class="empty-state__sub">Star devices for quick one-click access</p>
          </div>
        </div>

        <!-- ═══ Tab: Recent Sessions (Local History) ═══ -->
        <div v-else class="tab-content">
          <div class="section-label">My Recent Connections</div>
          <div v-if="history.length" :class="gridClass">
            <div v-for="s in history" :key="s.code" class="scard" @click="quickConnect(s.code)">
              <div class="scard__thumb" :style="{ background: getColor(s.id || 0) }">
                <span :class="['sdot', s.host_online ? 'sdot--on' : 'sdot--off']"></span>
                <button class="scard__star" @click.stop="toggleFav(s)">
                  <svg width="12" height="12" viewBox="0 0 24 24" :fill="favIds.has(s.id) ? '#f59e0b' : 'none'" :stroke="favIds.has(s.id) ? '#f59e0b' : 'rgba(255,255,255,0.7)'" stroke-width="2">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                  </svg>
                </button>
              </div>
              <div class="scard__info">
                <div class="scard__row">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                  <span class="scard__name">{{ getDisplayName(s) }}</span>
                </div>
                <span class="scard__code font-mono">{{ s.code }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="1.2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
            <p class="empty-state__title">No Recent Devices</p>
            <p class="empty-state__sub">Computers you connect to will appear here</p>
          </div>
        </div>

      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSessions } from '../composables/useSessions'
import { useMyAddress } from '../composables/useMyAddress'
import { useHostSession } from '../composables/useHostSession.js'
import { useDevice } from '../composables/useDevice.js'
import { apiUrl, isNativeApp, loadNetworkSettings } from '../composables/serverConfig.js'

const router = useRouter()
const { myAddress, agentStatus } = useMyAddress()
const host = useHostSession()
const device = useDevice()
const nativeHost = isNativeApp()

const {
  sessions,
  loading,
  favIds,
  favSessions,
  history,
  startPolling,
  stopPolling,
  loadHistory,
  addToHistory,
  toggleFav,
  getDisplayName,
} = useSessions()

const activeTab = ref('recent')
const viewMode = ref('grid-lg')
const quality = ref('medium')
const quickConnectInput = ref('')
const totalDevicesCount = ref(1)
const onlineDevicesCount = ref(1)

const deskStatus = computed(() => {
  if (device.deviceStatus.value === 'offline') return 'Offline. Connecting to signaling server...'
  if (host.state.value === 'connected') return 'Remote control active.'
  if (host.localStream.value) return 'Screen selected. Ready for incoming connections.'
  return 'Online. Screen access starts only after your approval.'
})

const tabs = [
  { id: 'recent', label: 'Recent Devices' },
  { id: 'favorites', label: 'Favorites' },
]

const gridClass = computed(() => ({
  sgrid: true,
  'sgrid--sm': viewMode.value === 'grid-sm',
  'sgrid--list': viewMode.value === 'list',
}))

const colors = [
  'linear-gradient(135deg,#00b4db,#0083b0)',
  'linear-gradient(135deg,#4facfe,#00f2fe)',
  'linear-gradient(135deg,#43e97b,#38f9d7)',
  'linear-gradient(135deg,#a18cd1,#fbc2eb)',
  'linear-gradient(135deg,#667eea,#764ba2)',
]
function getColor(id) {
  const numeric = Number.parseInt(String(id).replace(/\D/g, '').slice(-3), 10) || 1
  return colors[(numeric - 1) % colors.length]
}

function copyMyId() {
  if (myAddress.value) {
    navigator.clipboard?.writeText(myAddress.value.replace(/\s/g, ''))
  }
}

function quickConnect(code) {
  if (code && code === device.deviceId.value) {
    alert('Cannot connect to your own Device ID. Please enter the Device ID of another computer.')
    return
  }
  router.push({ name: 'Session', params: { code } })
}

function handleDirectConnect() {
  let raw = (quickConnectInput.value || '').trim()
  if (!raw) return
  let target = raw.toUpperCase()
  const digits = target.replace(/\D/g, '')
  if (digits.length === 9) {
    target = `AG-${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6, 9)}`
  }

  // Prevent connecting to self
  if (target === device.deviceId.value) {
    alert('Cannot connect to your own Device ID. Please enter the Device ID of another computer or open another browser tab.')
    return
  }

  // Record in connection history
  addToHistory({ code: target, id: target, host_online: true })

  // Send connection request to backend in background
  try {
    fetch(apiUrl('/api/v1/sessions/connect', loadNetworkSettings()), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        caller_device_id: device.deviceId.value || 'AG-000-000-000',
        caller_name: device.deviceName.value || 'Remote Client',
        target_device_id: target,
      }),
    }).catch(() => {})
  } catch (_) {}

  // Immediately start connection by pushing to Session view
  router.push({ name: 'Session', params: { code: target } })
}

function startHosting() {
  router.push({ name: 'Host' })
}

async function fetchNetworkDevices() {
  try {
    const res = await fetch(apiUrl('/api/v1/devices', loadNetworkSettings()))
    if (res.ok) {
      const list = await res.json()
      totalDevicesCount.value = list.length || 1
      onlineDevicesCount.value = list.filter(d => d.status === 'online').length || 1
    }
  } catch (_) {}
}

onMounted(async () => {
  loadHistory()
  startPolling()
  await host.ensureOnline()
  fetchNetworkDevices()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.home {
  height: calc(100vh - 48px);
  background: var(--ad-bg);
  color: var(--ad-text);
  overflow-y: auto;
  transition: background var(--transition-base), color var(--transition-base);
}
.workspace {
  display: grid;
  grid-template-columns: 340px 1fr;
  height: 100%;
}
.this-desk {
  background: var(--ad-sidebar);
  border-right: 1px solid var(--ad-border);
  padding: 24px;
  overflow-y: auto;
  transition: background var(--transition-base), border-color var(--transition-base);
}
.this-desk__card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.this-desk__card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.this-desk__title {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--ad-text);
}
.status-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  padding: 3px 8px;
  border-radius: 12px;
}
.status-pill--online {
  background: var(--ad-accent-subtle);
  color: var(--ad-accent);
}
.status-pill--connected {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}
.status-pill--offline {
  background: rgba(100, 116, 139, 0.12);
  color: var(--ad-text-muted);
}

.this-desk__label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ad-text-muted);
  margin-top: 4px;
  font-weight: 600;
}
.this-desk__address-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--ad-surface);
  border: 1px solid var(--ad-accent-glow);
  border-radius: 8px;
  padding: 10px 14px;
  box-shadow: var(--ad-shadow-sm);
  transition: background var(--transition-fast), border-color var(--transition-fast);
}
.this-desk__address {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--ad-accent);
  letter-spacing: 0.08em;
}
.this-desk__address--offline {
  color: var(--ad-text-muted);
}
.copy-btn {
  background: none;
  border: none;
  color: var(--ad-accent);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity var(--transition-fast);
}
.copy-btn:hover {
  opacity: 0.8;
}
.this-desk__sub {
  font-size: 0.82rem;
  color: var(--ad-text-muted);
  line-height: 1.5;
}
.desk-error {
  font-size: 0.8rem;
  color: #ef4444;
  line-height: 1.4;
}
.this-desk__meta-box {
  background: var(--ad-surface-alt);
  border: 1px solid var(--ad-border);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.meta-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
}
.meta-label {
  color: var(--ad-text-muted);
}
.meta-val {
  color: var(--ad-text-secondary);
  font-weight: 500;
}
.this-desk__setup-box {
  margin-top: 12px;
  border-top: 1px solid var(--ad-border);
  padding-top: 16px;
}
.share-start {
  width: 100%;
  background: var(--ad-accent);
  border: none;
  color: #fff;
  border-radius: 8px;
  padding: 10px;
  font-weight: 600;
  font-size: 0.88rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all var(--transition-fast);
  box-shadow: 0 2px 8px var(--ad-accent-glow);
}
.share-start:hover {
  background: var(--ad-accent-hover);
  transform: translateY(-1px);
}

/* Right Panel */
.remote-desk {
  padding: 24px 32px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dashboard-banner {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.metric-card {
  background: var(--ad-surface);
  border: 1px solid var(--ad-border);
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: var(--ad-shadow-sm);
  transition: all var(--transition-fast);
}
.metric-card:hover {
  border-color: var(--ad-border-hover);
}
.metric-num {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--ad-text);
}
.text-cyan { color: var(--ad-accent); }
.text-green { color: #22c55e; }
.metric-label {
  font-size: 0.8rem;
  color: var(--ad-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.quick-connect-bar {
  display: flex;
  gap: 12px;
}
.qc-input-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--ad-surface);
  border: 1px solid var(--ad-border);
  border-radius: 8px;
  padding: 10px 14px;
  box-shadow: var(--ad-shadow-sm);
  transition: all var(--transition-fast);
}
.qc-input-wrap:focus-within {
  border-color: var(--ad-accent);
  box-shadow: 0 0 0 2px var(--ad-accent-glow);
}
.qc-input-wrap svg {
  color: var(--ad-text-muted);
  flex-shrink: 0;
}
.qc-input {
  background: transparent;
  border: none;
  outline: none;
  color: var(--ad-input-text);
  font-size: 1rem;
  width: 100%;
  letter-spacing: 0.05em;
}
.qc-input::placeholder {
  color: var(--ad-input-placeholder);
}
.qc-btn {
  background: var(--ad-accent);
  border: none;
  color: #fff;
  font-weight: 600;
  border-radius: 8px;
  padding: 0 24px;
  cursor: pointer;
  transition: all var(--transition-fast);
  box-shadow: 0 2px 8px var(--ad-accent-glow);
}
.qc-btn:hover:not(:disabled) {
  background: var(--ad-accent-hover);
  transform: translateY(-1px);
}
.qc-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  box-shadow: none;
}

.tabs-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--ad-border);
  padding-bottom: 8px;
}
.tabs {
  display: flex;
  gap: 16px;
}
.tab {
  background: none;
  border: none;
  color: var(--ad-text-muted);
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  padding: 6px 0;
  position: relative;
  transition: color var(--transition-fast);
}
.tab:hover {
  color: var(--ad-text);
}
.tab--active {
  color: var(--ad-accent);
}
.tab--active::after {
  content: '';
  position: absolute;
  bottom: -9px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--ad-accent);
  border-radius: 2px;
}
.tabs-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.quality-select {
  background: var(--ad-surface);
  border: 1px solid var(--ad-border);
  color: var(--ad-text-secondary);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 0.8rem;
  outline: none;
}
.view-modes {
  display: flex;
  gap: 4px;
}
.vbtn {
  background: transparent;
  border: 1px solid var(--ad-border);
  border-radius: 6px;
  padding: 5px;
  color: var(--ad-text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}
.vbtn:hover {
  background: var(--ad-surface-hover);
  color: var(--ad-text);
}
.vbtn--active {
  background: var(--ad-accent-subtle);
  color: var(--ad-accent);
  border-color: var(--ad-accent-glow);
}

.section-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ad-text-secondary);
  margin-top: 4px;
}

.sgrid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  margin-top: 14px;
}
.scard {
  background: var(--ad-surface);
  border: 1px solid var(--ad-border);
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  box-shadow: var(--ad-shadow-sm);
  transition: transform var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.scard:hover {
  transform: translateY(-2px);
  border-color: var(--ad-accent);
  box-shadow: var(--ad-shadow);
}
.scard__thumb {
  height: 90px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}
.scard__star {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.3);
  border: none;
  cursor: pointer;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
}
.sdot {
  position: absolute;
  bottom: 8px;
  left: 8px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.sdot--on { background: #22c55e; box-shadow: 0 0 6px #22c55e; }
.sdot--off { background: #94a3b8; }
.scard__info {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--ad-surface);
}
.scard__row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ad-text);
}
.scard__code {
  font-size: 0.8rem;
  color: var(--ad-accent);
  font-weight: 600;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: var(--ad-text-muted);
  gap: 8px;
}
.empty-state__title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--ad-text-secondary);
}
.empty-state__sub {
  font-size: 0.82rem;
  color: var(--ad-text-muted);
}

/* Responsive Media Queries */
@media (max-width: 960px) {
  .home {
    height: auto;
    min-height: calc(100vh - 48px);
  }
  .workspace {
    grid-template-columns: 1fr;
    height: auto;
  }
  .this-desk {
    border-right: none;
    border-bottom: 1px solid var(--ad-border);
    padding: 20px;
  }
  .remote-desk {
    padding: 20px;
  }
}

@media (max-width: 640px) {
  .dashboard-banner {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .quick-connect-bar {
    flex-direction: column;
  }
  .qc-btn {
    width: 100%;
    height: 42px;
  }
  .tabs-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .tabs-right {
    width: 100%;
    justify-content: space-between;
  }
  .sgrid {
    grid-template-columns: 1fr;
  }
}
</style>
