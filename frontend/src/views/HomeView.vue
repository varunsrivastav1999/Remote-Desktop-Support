<template>
  <div class="home">
    <div class="workspace">
      <!-- ═══ Left Panel: This Desk ═══ -->
      <aside class="this-desk">
        <div class="this-desk__card">
          <h2 class="this-desk__title">This Desk</h2>
          <p class="this-desk__label">Your Address</p>
          <div class="this-desk__address-row">
            <span class="this-desk__address font-mono">{{ myAddress }}</span>
          </div>
          <p class="this-desk__sub"><span class="status-dot status-dot--online"></span> Ready to connect (secure connection)</p>
          
          <div class="this-desk__setup-box" style="margin-top:20px; border-top:1px solid var(--ad-border); padding-top:16px">
            <p class="this-desk__label">Deploy Host Agent</p>
            <p class="this-desk__sub" style="margin-bottom:8px">Run this on the remote computer:</p>
            <div class="setup-command">
              <code class="font-mono">{{ setupCommand }}</code>
              <button class="copy-setup-btn" @click="copySetupCommand" title="Copy Command">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              </button>
            </div>
            <p v-if="setupCopied" class="pw-saved fade-in" style="font-size:0.65rem">✓ Copied to clipboard</p>
          </div>
        </div>
      </aside>

      <!-- ═══ Right Panel: Remote Desk ═══ -->
      <section class="remote-desk">
        <!-- ═══ Tabs Row ═══ -->
        <div class="tabs-bar">
          <div class="tabs">
            <button v-for="tab in tabs" :key="tab.id" :class="['tab',{'tab--active':activeTab===tab.id}]" @click="activeTab=tab.id">{{ tab.label }}</button>
          </div>
          <div class="tabs-right">
            <select v-model="quality" class="quality-select" title="Connection Quality">
              <option value="low">Low Bandwidth</option>
              <option value="medium">Balanced</option>
              <option value="high">High Quality</option>
            </select>
            <div class="view-modes">
              <button :class="['vbtn',{'vbtn--active':viewMode==='grid-lg'}]" @click="viewMode='grid-lg'" title="Large Grid">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/></svg>
              </button>
              <button :class="['vbtn',{'vbtn--active':viewMode==='grid-sm'}]" @click="viewMode='grid-sm'" title="Small Grid">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="5" height="5" rx="1"/><rect x="10" y="3" width="5" height="5" rx="1"/><rect x="17" y="3" width="5" height="5" rx="1"/><rect x="3" y="10" width="5" height="5" rx="1"/><rect x="10" y="10" width="5" height="5" rx="1"/><rect x="17" y="10" width="5" height="5" rx="1"/><rect x="3" y="17" width="5" height="5" rx="1"/><rect x="10" y="17" width="5" height="5" rx="1"/><rect x="17" y="17" width="5" height="5" rx="1"/></svg>
              </button>
              <button :class="['vbtn',{'vbtn--active':viewMode==='list'}]" @click="viewMode='list'" title="List View">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="4" width="18" height="3" rx="1"/><rect x="3" y="10.5" width="18" height="3" rx="1"/><rect x="3" y="17" width="18" height="3" rx="1"/></svg>
              </button>
            </div>
          </div>
        </div>

        <!-- ═══ Tab: Favorites ═══ -->
        <div v-if="activeTab==='favorites'" class="tab-content">
          <div class="section-label">Favorites</div>
          <div v-if="favSessions.length" :class="gridClass">
            <div v-for="s in favSessions" :key="s.id" class="scard" @click="$parent.quickConnect?.(s.code)">
              <div class="scard__thumb" :style="{background:getColor(s.id)}">
                <span :class="['sdot',s.status==='connected'?'sdot--on':'sdot--off']"></span>
                <button class="scard__star" @click.stop="toggleFav(s)"><svg width="12" height="12" viewBox="0 0 24 24" fill="#f59e0b" stroke="#f59e0b" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></button>
                <button class="scard__menu" @click.stop><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg></button>
              </div>
              <div class="scard__info">
                <div class="scard__row"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg><span class="scard__name">{{ getDisplayName(s) }}</span></div>
                <span class="scard__code font-mono">{{ s.code }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
            <p class="empty-state__title">No Favorites</p>
            <p class="empty-state__sub">Star sessions for quick access</p>
          </div>
        </div>

        <!-- ═══ Tab: Recent Sessions (Local History) ═══ -->
        <div v-else-if="activeTab==='recent'" class="tab-content">
          <div class="section-label">My Recent Connections</div>
          <div v-if="history.length" :class="gridClass">
            <div v-for="s in history" :key="s.code" class="scard" @click="quickConnect(s.code)">
              <div class="scard__thumb" :style="{background:getColor(s.id || 0)}">
                <span class="sdot sdot--off"></span>
                <button class="scard__star" @click.stop="toggleFav(s)"><svg width="12" height="12" viewBox="0 0 24 24" :fill="favIds.has(s.id)?'#f59e0b':'none'" :stroke="favIds.has(s.id)?'#f59e0b':'rgba(255,255,255,0.7)'" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></button>
                <!-- 3-dot Menu -->
                <div class="scard__menu-wrap">
                  <button class="scard__menu-btn" @click.stop="toggleMenu(s.id)"><svg width="12" height="12" viewBox="0 0 24 24" fill="rgba(255,255,255,0.7)"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg></button>
                  <div v-if="openMenuId===s.id" class="scard__dropdown" @click.stop>
                    <button class="dd-item" @click="quickConnect(s.code)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>Connect</button>
                    <button class="dd-item" @click="quickConnect(s.code)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>File Transfer</button>
                    <button class="dd-item" @click="openSSH(s.code)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>SSH Terminal</button>
                    <button class="dd-item" @click="startRename(s)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>Rename</button>
                    <button class="dd-item" @click="toggleFav(s);closeMenu()"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>{{ favIds.has(s.id)?'Remove from Favorites':'Add to Favorites' }}</button>
                    <button class="dd-item" @click="copyCode(s.code)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>Copy Address</button>
                    <div class="dd-divider"></div>
                    <button class="dd-item" @click="showDetails(s)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>Session Details</button>
                    <button class="dd-item dd-item--danger" @click="removeSession(s.id)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>Remove</button>
                  </div>
                </div>
              </div>
              <!-- Rename overlay -->
              <div v-if="renamingId===s.id" class="scard__rename-overlay" @click.stop>
                <input ref="renameInput" v-model="renameValue" class="rename-input" placeholder="Enter new name" @keydown.enter="confirmRename(s)" @keydown.escape="cancelRename" autofocus/>
                <div class="rename-actions">
                  <button class="rename-ok" @click="confirmRename(s)">✓</button>
                  <button class="rename-cancel" @click="cancelRename">✕</button>
                </div>
              </div>
              <!-- Normal info -->
              <div v-else class="scard__info">
                <div class="scard__row"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg><span class="scard__name">{{ getDisplayName(s) }}</span></div>
                <span class="scard__code font-mono">{{ s.code }}</span>
              </div>
            </div>
          </div>
          <!-- Empty -->
          <div v-else class="empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
            <p class="empty-state__title">No Connection History</p>
            <p class="empty-state__sub">Machines you connect to will appear here</p>
          </div>
        </div>

        <!-- ═══ Tab: Discovered (Global Server List) ═══ -->
        <div v-else class="tab-content">
          <div class="section-label">Discovered (Global Signaling Server)</div>
          
          <!-- Loading -->
          <div v-if="loading" class="empty-state"><span class="spinner-md"></span><p>Loading...</p></div>
          
          <!-- Sessions Grid -->
          <div v-else-if="sessions.length" :class="gridClass">
            <div v-for="s in sessions" :key="s.id" class="scard" @click="quickConnect(s.code)">
              <div class="scard__thumb" :style="{background:getColor(s.id)}">
                <span :class="['sdot', ['waiting', 'connected'].includes(s.status) ? 'sdot--on' : 'sdot--off']"></span>
                <button class="scard__star" @click.stop="toggleFav(s)"><svg width="12" height="12" viewBox="0 0 24 24" :fill="favIds.has(s.id)?'#f59e0b':'none'" :stroke="favIds.has(s.id)?'#f59e0b':'rgba(255,255,255,0.7)'" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></button>
                <div class="scard__menu-wrap">
                  <button class="scard__menu-btn" @click.stop="toggleMenu(s.id)"><svg width="12" height="12" viewBox="0 0 24 24" fill="rgba(255,255,255,0.7)"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg></button>
                </div>
              </div>
              <div class="scard__info">
                <div class="scard__row"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg><span class="scard__name">{{ getDisplayName(s) }}</span></div>
                <span class="scard__code font-mono">{{ s.code }}</span>
              </div>
            </div>
          </div>
          
          <div v-else class="empty-state">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
            <p class="empty-state__title">No Active Hosts</p>
            <p class="empty-state__sub">Remote agents will appear here when they come online</p>
          </div>
        </div>

        <div class="tab-content" style="padding-top:0">
          <div class="section-label" style="margin-top:24px">Settings</div>
          <div class="news-card">
            <h4 class="news-card__title">Remote Desktop Status</h4>
            <p class="news-card__text">Your version is up to date.</p>
            <div class="news-card__meta">
              <span class="text-muted">License: Professional</span>
              <span class="license-badge">Active</span>
            </div>
          </div>
          <div class="news-card">
            <h4 class="news-card__title">Security</h4>
            <div class="security-row">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              <span>Unattended Access</span>
              <label class="toggle"><input type="checkbox" v-model="unattendedEnabled"/><span class="toggle__slider"></span></label>
            </div>
            <div v-if="unattendedEnabled" class="unattended-form fade-in">
              <div class="pw-row">
                <input :type="showPw?'text':'password'" v-model="unattendedPw" class="pw-input" placeholder="Set password"/>
                <button class="pw-eye" @click="showPw=!showPw">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
              </div>
              <button class="btn-save" @click="savePw" :disabled="!unattendedPw">Save Password</button>
              <p v-if="pwSaved" class="pw-saved fade-in">✓ Password saved</p>
            </div>
            <div class="security-row" style="margin-top:8px">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              <span>Interactive Access</span>
              <select v-model="accessMode" class="access-sel"><option value="confirm">Confirm</option><option value="allow">Allow</option><option value="deny">Deny</option></select>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessions } from '../composables/useSessions'
import { useMyAddress } from '../composables/useMyAddress'

const router = useRouter()
const { myAddress } = useMyAddress()

const {
  sessions,
  loading,
  favIds,
  favSessions,
  history,
  startPolling,
  stopPolling,
  loadHistory,
  renameSession,
  removeSessionLocally,
  toggleFav,
  getDisplayName
} = useSessions()

// ─── State ──────────────────────────────────────────────
const activeTab = ref('recent')
const viewMode = ref('grid-lg')
const quality = ref('medium')

// Security / Settings (Now moved to Discovered conceptually)
const unattendedEnabled = ref(false)
const unattendedPw = ref('')
const showPw = ref(false)
const pwSaved = ref(false)
const accessMode = ref('confirm')
const setupCopied = ref(false)

const setupCommand = computed(() => {
  const origin = window.location.origin
  return `python agent.py --server ${origin}`
})

function copySetupCommand() {
  copyText(setupCommand.value)
  setupCopied.value = true
  setTimeout(() => setupCopied.value = false, 2000)
}

const tabs = [
  { id:'favorites', label:'Favorites' },
  { id:'recent', label:'Recent Sessions' },
  { id:'discovered', label:'Discovered' },
]

const gridClass = computed(() => ({
  'sgrid':true,
  'sgrid--sm': viewMode.value==='grid-sm',
  'sgrid--list': viewMode.value==='list',
}))

// Card gradient colors
const colors = [
  'linear-gradient(135deg,#667eea,#764ba2)','linear-gradient(135deg,#f093fb,#f5576c)',
  'linear-gradient(135deg,#4facfe,#00f2fe)','linear-gradient(135deg,#43e97b,#38f9d7)',
  'linear-gradient(135deg,#fa709a,#fee140)','linear-gradient(135deg,#a18cd1,#fbc2eb)',
  'linear-gradient(135deg,#ffecd2,#fcb69f)','linear-gradient(135deg,#89f7fe,#66a6ff)',
]
function getColor(id) { return colors[(id-1) % colors.length] }

onMounted(() => {
  loadHistory()
  startPolling()
  document.addEventListener('click', closeMenu)
})
onUnmounted(() => {
  stopPolling()
  document.removeEventListener('click', closeMenu)
})

function quickConnect(code) {
  closeMenu()
  router.push({ name:'Session', params:{ code } })
}

function openSSH(code) {
  closeMenu()
  router.push({ name:'Terminal', params:{ code } })
}

function savePw() {
  if (unattendedPw.value) { pwSaved.value = true; setTimeout(()=> pwSaved.value=false, 3000) }
}

// ─── Dropdown Menu ──────────────────────────────────────
const openMenuId = ref(null)
function toggleMenu(id) { openMenuId.value = openMenuId.value===id ? null : id }
function closeMenu() { openMenuId.value = null }

// ─── Rename ─────────────────────────────────────────────
const renamingId = ref(null)
const renameValue = ref('')

function startRename(s) {
  closeMenu()
  renamingId.value = s.id
  renameValue.value = getDisplayName(s)
}

function confirmRename(s) {
  if (renameValue.value.trim() && renameValue.value !== getDisplayName(s)) {
    renameSession(s.code, renameValue.value.trim())
  }
  renamingId.value = null
}

function cancelRename() { renamingId.value = null }

function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text)
  } else {
    const textArea = document.createElement("textarea")
    textArea.value = text
    textArea.style.position = "fixed"
    textArea.style.left = "-9999px"
    textArea.style.top = "0"
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
  }
}



// ─── Copy Address ───────────────────────────────────────
function copyCode(code) {
  copyText(code)
  closeMenu()
}

// ─── Remove ─────────────────────────────────────────────
function removeSession(id) {
  removeSessionLocally(id)
  closeMenu()
}

// ─── Details ────────────────────────────────────────────
const detailSession = ref(null)
function showDetails(s) {
  detailSession.value = detailSession.value?.id===s.id ? null : s
  closeMenu()
}
</script>

<style scoped>
.home { display:flex; flex-direction:column; height:calc(100vh - 42px); overflow:hidden; background:var(--ad-bg); }

/* ═══ Workspace Layout ═══ */
.workspace { display:flex; flex:1; overflow:hidden; }

/* Left Panel */
.this-desk { width:320px; padding:24px; border-right:1px solid var(--ad-border); background:var(--ad-bg); flex-shrink:0; display:flex; flex-direction:column; }
.this-desk__card { background:var(--ad-surface); border:1px solid var(--ad-border); border-radius:8px; padding:20px; box-shadow:0 4px 12px rgba(0,0,0,0.1); }
.this-desk__title { font-size:1.1rem; font-weight:700; color:var(--ad-text); margin-bottom:16px; display:flex; align-items:center; gap:8px; }
.this-desk__label { font-size:0.8rem; color:var(--ad-text-muted); margin-bottom:4px; }
.this-desk__address-row { display:flex; align-items:center; margin-bottom:12px; }
.this-desk__address { font-size:1.8rem; font-weight:700; color:var(--color-accent-primary); letter-spacing:0.04em; }
.this-desk__sub { font-size:0.75rem; color:var(--ad-text-muted); display:flex; align-items:center; gap:6px; }

/* Right Panel */
.remote-desk { flex:1; display:flex; flex-direction:column; min-width:0; background:var(--ad-bg); }

/* ═══ Tabs Bar ═══ */
.tabs-bar { display:flex; align-items:center; justify-content:space-between; padding:0 16px; border-bottom:1px solid var(--ad-border); flex-shrink:0; background:var(--ad-bg); }
.tabs { display:flex; gap:0; }
.tab { padding:10px 16px; font-size:0.8rem; font-weight:500; color:var(--ad-text-muted); background:none; border:none; cursor:pointer; border-bottom:2px solid transparent; transition:all 150ms; font-family:var(--font-sans); }
.tab:hover { color:var(--ad-text); }
.tab--active { color:#d32f2f; border-bottom-color:#d32f2f; }
.tabs-right { display:flex; align-items:center; gap:8px; }
.quality-select { padding:3px 8px; font-size:0.72rem; background:var(--ad-surface); color:var(--ad-text); border:1px solid var(--ad-border); border-radius:4px; outline:none; cursor:pointer; }
.view-modes { display:flex; gap:2px; }
.vbtn { padding:5px; background:none; border:none; color:var(--ad-text-muted); cursor:pointer; border-radius:4px; display:flex; transition:all 150ms; }
.vbtn:hover { color:var(--ad-text); }
.vbtn--active { color:var(--ad-text); background:rgba(128,128,128,0.2); }

/* ═══ Tab Content ═══ */
.tab-content { flex:1; overflow-y:auto; padding:20px 24px; }
.section-label { font-size:0.72rem; text-transform:uppercase; letter-spacing:0.08em; color:var(--ad-text-muted); margin-bottom:12px; }

/* ═══ News Cards ═══ */
.news-card { background:var(--ad-surface); border-radius:8px; padding:16px 20px; margin-bottom:12px; max-width:400px; border:1px solid var(--ad-border); box-shadow:0 2px 8px rgba(0,0,0,0.05); }
.news-card__title { font-size:0.85rem; font-weight:700; color:var(--ad-text); margin-bottom:6px; }
.news-card__text { font-size:0.8rem; color:var(--ad-text-muted); margin-bottom:8px; }
.news-card__meta { display:flex; align-items:center; gap:8px; font-size:0.75rem; }
.license-badge { font-size:0.7rem; font-weight:600; color:#4caf50; background:rgba(76,175,80,0.15); padding:2px 8px; border-radius:20px; }

/* Security */
.security-row { display:flex; align-items:center; gap:8px; font-size:0.85rem; color:var(--ad-text); }
.toggle { position:relative; width:34px; height:18px; flex-shrink:0; margin-left:auto; }
.toggle input { opacity:0; width:0; height:0; }
.toggle__slider { position:absolute; inset:0; background:var(--ad-border); border-radius:9px; cursor:pointer; transition:250ms; }
.toggle__slider::before { content:''; position:absolute; height:12px; width:12px; left:3px; bottom:3px; background:white; border-radius:50%; transition:250ms; }
.toggle input:checked + .toggle__slider { background:#d32f2f; }
.toggle input:checked + .toggle__slider::before { transform:translateX(16px); }
.access-sel { margin-left:auto; padding:3px 6px; font-size:0.75rem; background:var(--ad-bg); color:var(--ad-text); border:1px solid var(--ad-border); border-radius:4px; outline:none; cursor:pointer; }
.unattended-form { margin-top:10px; }
.pw-row { display:flex; gap:6px; }
.pw-input { flex:1; padding:6px 10px; font-size:0.8rem; background:var(--ad-bg); color:var(--ad-text); border:1px solid var(--ad-border); border-radius:4px; outline:none; }
.pw-input::placeholder { color:var(--ad-text-muted); }
.pw-input:focus { border-color:#d32f2f; }
.pw-eye { background:none; border:none; color:var(--ad-text-muted); cursor:pointer; display:flex; padding:4px; }
.btn-save { margin-top:8px; width:100%; padding:6px; font-size:0.8rem; font-weight:600; background:#d32f2f; color:white; border:none; border-radius:4px; cursor:pointer; transition:150ms; }
.btn-save:hover:not(:disabled) { background:#b71c1c; }
.btn-save:disabled { opacity:0.4; cursor:not-allowed; }
.pw-saved { margin-top:4px; font-size:0.75rem; color:#4caf50; }

/* ═══ Session Cards Grid ═══ */
.sgrid { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:12px; }
.sgrid--sm { grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); }
.sgrid--list { grid-template-columns:1fr 1fr; }
.sgrid--list .scard { flex-direction:row; height:60px; }
.sgrid--list .scard__thumb { width:100px; height:100%; border-radius:6px 0 0 6px; }
.sgrid--list .scard__info { padding:8px 12px; justify-content:center; }

.scard { position:relative; display:flex; flex-direction:column; background:var(--ad-surface); border:1px solid var(--ad-border); border-radius:6px; cursor:pointer; transition:transform 200ms,box-shadow 200ms; }
.scard:hover { transform:translateY(-2px); box-shadow:0 6px 16px rgba(0,0,0,0.15); border-color:var(--color-accent-primary); }
.scard__thumb { position:relative; height:100px; border-radius:6px 6px 0 0; }
.scard__info { padding:8px 10px; display:flex; flex-direction:column; gap:2px; border-radius:0 0 6px 6px; }
.scard__row { display:flex; align-items:center; gap:6px; color:var(--ad-text-muted); }
.scard__name { font-size:0.75rem; font-weight:600; color:var(--ad-text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.scard__code { font-size:0.7rem; color:var(--ad-text-muted); letter-spacing:0.04em; }

.sdot { position:absolute; top:8px; left:8px; width:10px; height:10px; border-radius:50%; border:2px solid rgba(0,0,0,0.2); }
.sdot--on { background:#4caf50; }
.sdot--off { background:#f44336; }

.scard__star { position:absolute; top:6px; right:30px; background:none; border:none; color:rgba(255,255,255,0.8); cursor:pointer; padding:4px; display:flex; transition:150ms; z-index:2; }
.scard__star:hover { transform:scale(1.2); }

/* Dropdown Menu */
.scard__menu-wrap { position:absolute; top:6px; right:6px; z-index:10; }
.scard__menu-btn { background:none; border:none; color:rgba(255,255,255,0.8); cursor:pointer; padding:4px; display:flex; border-radius:4px; }
.scard__menu-btn:hover { background:rgba(255,255,255,0.2); }
.scard__dropdown { position:absolute; top:100%; right:0; background:var(--ad-topbar); border:1px solid var(--ad-border); border-radius:6px; box-shadow:0 8px 24px rgba(0,0,0,0.15); min-width:200px; padding:4px; display:flex; flex-direction:column; gap:2px; animation:fade-in 0.15s ease-out; }
.dd-item { display:flex; align-items:center; gap:10px; width:100%; padding:8px 10px; font-size:0.8rem; color:var(--ad-text); background:none; border:none; border-radius:4px; cursor:pointer; text-align:left; transition:background 100ms; }
.dd-item:hover { background:#d32f2f; color:white; }
.dd-item--danger:hover { background:#b71c1c; color:white; }
.dd-divider { height:1px; background:var(--ad-border); margin:4px 0; }

/* Rename Overlay */
/* Rename Overlay */
.scard__rename-overlay { padding:8px 10px; background:var(--ad-surface); display:flex; flex-direction:column; gap:6px; border-radius:0 0 6px 6px; }
.rename-input { width:100%; padding:6px 8px; font-size:0.75rem; font-weight:600; border:1px solid var(--ad-border); border-radius:4px; outline:none; color:var(--ad-text); background:var(--ad-bg); }
.rename-input:focus { border-color:#d32f2f; }
.rename-actions { display:flex; gap:6px; align-self:flex-end; }
.rename-ok, .rename-cancel { background:none; border:none; cursor:pointer; padding:4px 8px; border-radius:4px; font-size:0.8rem; font-weight:bold; }
.rename-ok { color:#4caf50; background:rgba(76,175,80,0.1); }
.rename-ok:hover { background:rgba(76,175,80,0.2); }
.rename-cancel { color:#f44336; background:rgba(244,67,54,0.1); }
.rename-cancel:hover { background:rgba(244,67,54,0.2); }
/* Setup Box */
.this-desk__setup-box { width:100%; }
.setup-command { margin-top:8px; background:var(--ad-bg); border:1px solid var(--ad-border); border-radius:4px; padding:8px 10px; display:flex; align-items:center; justify-content:space-between; gap:10px; }
.setup-command code { font-size:0.65rem; color:var(--ad-text); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1; }
.copy-setup-btn { background:none; border:none; color:var(--ad-text-muted); cursor:pointer; padding:4px; display:flex; border-radius:4px; transition:150ms; }
.copy-setup-btn:hover { color:var(--ad-text); background:rgba(128,128,128,0.2); }

/* ═══ Empty State ═══ */
.empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; flex:1; min-height:200px; gap:8px; }
.empty-state__title { font-size:0.9rem; font-weight:700; color:var(--ad-text-muted); }
.empty-state__sub { font-size:0.8rem; color:var(--ad-text-muted); text-align:center; opacity:0.7; }
.spinner-md { width:24px; height:24px; border:2.5px solid rgba(255,255,255,0.1); border-top-color:#d32f2f; border-radius:50%; animation:spin 0.8s linear infinite; }
</style>
