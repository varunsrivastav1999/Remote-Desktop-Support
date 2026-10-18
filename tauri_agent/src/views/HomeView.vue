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
  router.push({ name: 'Session', params: { code } })
}

function handleDirectConnect() {
  let target = quickConnectInput.value.trim().toUpperCase()
  if (!target) return
  if (!target.startsWith('AG-') && target.replace(/\D/g, '').length === 9) {
    const d = target.replace(/\D/g, '')
    target = `AG-${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6, 9)}`
  }
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
}
.workspace {
  display: grid;
  grid-template-columns: 340px 1fr;
  height: 100%;
}
.this-desk {
  background: #141518;
  border-right: 1px solid var(--ad-border);
  padding: 24px;
  overflow-y: auto;
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
  color: #fff;
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
  background: rgba(0, 229, 255, 0.12);
  color: #00e5ff;
}
.status-pill--connected {
  background: rgba(76, 175, 80, 0.15);
  color: #4caf50;
}
.status-pill--offline {
  background: rgba(255, 255, 255, 0.06);
  color: #888;
}

.this-desk__label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #8b92a0;
  margin-top: 4px;
}
.this-desk__address-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #1b1c21;
  border: 1px solid rgba(0, 229, 255, 0.25);
  border-radius: 8px;
  padding: 8px 12px;
}
.this-desk__address {
  font-size: 1.25rem;
  font-weight: 700;
  color: #00e5ff;
  letter-spacing: 0.08em;
}
.this-desk__address--offline {
  color: #777;
}
.copy-btn {
  background: none;
  border: none;
  color: #00e5ff;
  cursor: pointer;
  padding: 4px;
}
.this-desk__sub {
  font-size: 0.82rem;
  color: #9aa0ac;
  line-height: 1.5;
}
.this-desk__meta-box {
  background: #191b1f;
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
  color: #888;
}
.meta-val {
  color: #ddd;
  font-weight: 500;
}
.this-desk__setup-box {
  margin-top: 12px;
  border-top: 1px solid var(--ad-border);
  padding-top: 16px;
}
.share-start {
  width: 100%;
  background: #00bcd4;
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
  transition: background 0.2s;
}
.share-start:hover {
  background: #00acc1;
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
  background: #1a1b20;
  border: 1px solid #292c34;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.metric-num {
  font-size: 1.8rem;
  font-weight: 700;
  color: #fff;
}
.text-cyan { color: #00e5ff; }
.text-green { color: #4caf50; }
.metric-label {
  font-size: 0.8rem;
  color: #8b92a0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
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
  background: #1a1b20;
  border: 1px solid #333640;
  border-radius: 8px;
  padding: 10px 14px;
}
.qc-input-wrap svg {
  color: #777;
}
.qc-input {
  background: transparent;
  border: none;
  outline: none;
  color: #fff;
  font-size: 1rem;
  width: 100%;
  letter-spacing: 0.05em;
}
.qc-btn {
  background: #00bcd4;
  border: none;
  color: #fff;
  font-weight: 600;
  border-radius: 8px;
  padding: 0 24px;
  cursor: pointer;
}
.qc-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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
  color: #8b92a0;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  padding: 6px 0;
  position: relative;
}
.tab--active {
  color: #00e5ff;
}
.tab--active::after {
  content: '';
  position: absolute;
  bottom: -9px;
  left: 0;
  right: 0;
  height: 2px;
  background: #00e5ff;
}

.sgrid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.scard {
  background: #1c1d22;
  border: 1px solid #2a2d35;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, border-color 0.2s;
}
.scard:hover {
  transform: translateY(-2px);
  border-color: #00bcd4;
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
  background: none;
  border: none;
  cursor: pointer;
}
.sdot {
  position: absolute;
  bottom: 8px;
  left: 8px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.sdot--on { background: #00e5ff; box-shadow: 0 0 6px #00e5ff; }
.sdot--off { background: #777; }
.scard__info {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.scard__row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  color: #fff;
}
.scard__code {
  font-size: 0.8rem;
  color: #00e5ff;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: #8b92a0;
  gap: 8px;
}
.empty-state__title {
  font-size: 1rem;
  font-weight: 600;
  color: #aaa;
}
.empty-state__sub {
  font-size: 0.82rem;
}
</style>
