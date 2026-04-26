<template>
  <div class="app">
    <!-- ═══ Top Bar (AnyDesk style) ═══ -->
    <header class="topbar">
      <div class="topbar__left">
        <div class="topbar__logo">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        </div>
        <div class="topbar__connect">
          <span class="topbar__status-icon">
            <span class="status-dot status-dot--online"></span>
          </span>
          <input type="text" class="topbar__input" placeholder="Enter Remote Address" :value="sessionCode" @input="formatCode" @keydown.enter="joinSession" />
        </div>
      </div>
      <div class="topbar__center">
        <span class="topbar__label">Your Address</span>
        <span class="topbar__address font-mono">{{ myAddress }}</span>
        <button class="topbar__icon-btn" @click="copyAddress" title="Copy Address">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>
        </button>
        <button class="topbar__icon-btn" @click="showSecurity=!showSecurity" title="Security Settings">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        </button>
      </div>
      <div class="topbar__right">
        <button class="topbar__icon-btn" title="Toggle Theme" @click="toggleTheme">
          <svg v-if="isLightMode" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        </button>
        <button class="topbar__icon-btn" title="Settings" @click="showSettings=true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
        <button class="topbar__connect-btn" :disabled="!isValidCode||isLoading" @click="joinSession">
          <svg v-if="!isLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
          <span v-else class="spinner-sm"></span>
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

    <!-- ═══ Global Settings Modal ═══ -->
    <transition name="fade">
      <div v-if="showSettings" class="settings-overlay" @click.self="showSettings=false">
        <div class="settings-modal">
          <div class="settings-sidebar">
            <h3 class="settings-sidebar__title">Settings</h3>
            <button :class="['st-tab', {'st-tab--active': settingsTab==='user_interface'}]" @click="settingsTab='user_interface'">User Interface</button>
            <button :class="['st-tab', {'st-tab--active': settingsTab==='security'}]" @click="settingsTab='security'">Security</button>
            <button :class="['st-tab', {'st-tab--active': settingsTab==='privacy'}]" @click="settingsTab='privacy'">Privacy</button>
            <button :class="['st-tab', {'st-tab--active': settingsTab==='recording'}]" @click="settingsTab='recording'">Recording</button>
            <button :class="['st-tab', {'st-tab--active': settingsTab==='connection'}]" @click="settingsTab='connection'">Connection</button>
            <button :class="['st-tab', {'st-tab--active': settingsTab==='network'}]" @click="settingsTab='network'">Network</button>
            <button :class="['st-tab', {'st-tab--active': settingsTab==='ssh'}]" @click="settingsTab='ssh'">SSH Access</button>
            <div class="st-divider"></div>
            <button :class="['st-tab', {'st-tab--active': settingsTab==='license'}]" @click="settingsTab='license'">License</button>
          </div>
          
          <div class="settings-content">
            <div class="settings-header">
              <h2>{{ settingsTabTitle }}</h2>
              <button class="settings-close" @click="showSettings=false">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            
            <div class="settings-body">
              <!-- User Interface -->
              <div v-if="settingsTab==='user_interface'" class="st-section">
                <div class="st-group">
                  <label>Language</label>
                  <select v-model="settings.language" class="st-input">
                    <option>System Default</option>
                    <option>English</option>
                    <option>German</option>
                    <option>French</option>
                  </select>
                </div>
                <div class="st-group">
                  <label>Alias configuration</label>
                  <input type="text" v-model="settings.alias" class="st-input" placeholder="Choose an alias (e.g. name@ad)"/>
                  <p class="st-hint">An alias is a permanent, easy-to-remember address.</p>
                </div>
              </div>

              <!-- Security -->
              <div v-if="settingsTab==='security'" class="st-section">
                <div class="st-group">
                  <label>Interactive Access</label>
                  <select v-model="settings.interactiveAccess" class="st-input">
                    <option value="allow">Always allow</option>
                    <option value="confirm">Always show accept window</option>
                    <option value="deny">Deny incoming requests</option>
                  </select>
                </div>
                <div class="st-group st-row">
                  <div class="st-text">
                    <label>TCP Tunneling</label>
                    <p class="st-hint">Allow remote users to map local ports to remote ports.</p>
                  </div>
                  <label class="toggle"><input type="checkbox" v-model="settings.tcpTunneling"/><span class="toggle__slider"></span></label>
                </div>
              </div>

              <!-- Privacy -->
              <div v-if="settingsTab==='privacy'" class="st-section">
                <div class="st-group st-row">
                  <div class="st-text">
                    <label>Privacy Mode</label>
                    <p class="st-hint">Black out the remote screen and disable input for other users.</p>
                  </div>
                  <label class="toggle"><input type="checkbox" v-model="settings.privacyMode"/><span class="toggle__slider"></span></label>
                </div>
              </div>

              <!-- Recording -->
              <div v-if="settingsTab==='recording'" class="st-section">
                <div class="st-group st-row">
                  <div class="st-text">
                    <label>Auto-Record Sessions</label>
                    <p class="st-hint">Automatically record incoming and outgoing sessions.</p>
                  </div>
                  <label class="toggle"><input type="checkbox" v-model="settings.autoRecord"/><span class="toggle__slider"></span></label>
                </div>
              </div>

              <!-- Connection -->
              <div v-if="settingsTab==='connection'" class="st-section">
                <div class="st-group st-row">
                  <div class="st-text">
                    <label>Direct Connections (P2P)</label>
                    <p class="st-hint">Attempt direct peer-to-peer connection via STUN. Recommended for low latency.</p>
                  </div>
                  <label class="toggle"><input type="checkbox" v-model="settings.directConnection"/><span class="toggle__slider"></span></label>
                </div>
                <div class="st-group st-row">
                  <div class="st-text">
                    <label>Always Use Relay</label>
                    <p class="st-hint">Force all traffic through the TURN/Relay server. Use if P2P is blocked by firewalls.</p>
                  </div>
                  <label class="toggle"><input type="checkbox" v-model="settings.alwaysRelay"/><span class="toggle__slider"></span></label>
                </div>
                <div class="st-group st-row">
                  <div class="st-text">
                    <label>Allow Direct IP Access</label>
                    <p class="st-hint">Enable connection attempts directly to the host's IP address without signaling.</p>
                  </div>
                  <label class="toggle"><input type="checkbox" v-model="settings.directIP"/><span class="toggle__slider"></span></label>
                </div>
                <div class="st-group st-row">
                  <div class="st-text">
                    <label>Wake-on-LAN</label>
                    <p class="st-hint">Allow this device to be woken up by other devices on the network.</p>
                  </div>
                  <label class="toggle"><input type="checkbox" v-model="settings.wakeOnLan"/><span class="toggle__slider"></span></label>
                </div>
                <div class="st-group">
                  <label>HTTP Proxy</label>
                  <input type="text" v-model="settings.httpProxy" class="st-input" placeholder="http://proxy.example.com:8080"/>
                </div>
              </div>

              <!-- Network & Signaling -->
              <div v-if="settingsTab==='network'" class="st-section">
                <div class="st-group">
                  <label>Signaling Server URL</label>
                  <input type="text" v-model="settings.signalingServer" class="st-input" placeholder="ws://localhost:8000/ws/signaling/"/>
                  <p class="st-hint">Specify a custom signaling server for world-wide connection.</p>
                </div>
                <div class="st-group">
                  <label>STUN Servers (one per line)</label>
                  <textarea v-model="settings.stunServers" class="st-input" rows="3" placeholder="stun:stun.l.google.com:19302"></textarea>
                </div>
                <div class="st-group">
                  <label>TURN Servers (optional)</label>
                  <textarea v-model="settings.turnServers" class="st-input" rows="3" placeholder="turn:relay.example.com?transport=udp"></textarea>
                  <p class="st-hint">Required for symmetric NAT traversal over the internet.</p>
                </div>
              </div>

              <!-- SSH Access -->
              <div v-if="settingsTab==='ssh'" class="st-section">
                <div class="st-group st-row">
                  <div class="st-text">
                    <label>Online SSH Access</label>
                    <p class="st-hint">Enable feature-wise SSH access for secure remote terminal administration.</p>
                  </div>
                  <label class="toggle"><input type="checkbox" v-model="settings.sshAccess"/><span class="toggle__slider"></span></label>
                </div>
                <div v-if="settings.sshAccess" class="st-group fade-in">
                  <label>Default SSH Port</label>
                  <input type="number" v-model="settings.sshPort" class="st-input" style="max-width:150px" placeholder="22"/>
                </div>
                <div v-if="settings.sshAccess" class="st-group fade-in">
                  <label>Authorized Keys</label>
                  <textarea v-model="settings.sshKeys" class="st-input" rows="4" placeholder="ssh-rsa AAAAB3..."></textarea>
                  <p class="st-hint">Paste your public SSH keys here to allow key-based authentication.</p>
                </div>
              </div>

              <!-- License -->
              <div v-if="settingsTab==='license'" class="st-section">
                <div class="st-license-card">
                  <h4>Remote Desktop Ultimate</h4>
                  <p>Your license covers all advanced features.</p>
                  <div class="license-badge">Active</div>
                </div>
                <div class="st-group" style="margin-top:20px">
                  <label>Change License Key</label>
                  <div style="display:flex;gap:8px">
                    <input type="text" class="st-input" placeholder="Enter new license key..."/>
                    <button class="st-btn st-btn--primary">Apply</button>
                  </div>
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
import { ref, computed, watchEffect, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useMyAddress } from './composables/useMyAddress'
import { useSessions } from './composables/useSessions'

const router = useRouter()
const { myAddress } = useMyAddress()
const { addToHistory } = useSessions()

const sessionCode = ref('')
const isLoading = ref(false)
const errorMsg = ref('')
const showSecurity = ref(false)
const showSettings = ref(false)
const isLightMode = ref(false)

// ─── Settings State ─────────────────────────────────────
const settingsTab = ref('user_interface')
const settingsTabTitle = computed(() => {
  const map = {
    user_interface: 'User Interface',
    security: 'Security',
    privacy: 'Privacy',
    recording: 'Recording',
    connection: 'Connection',
    network: 'Network',
    ssh: 'SSH Access',
    license: 'License'
  }
  return map[settingsTab.value]
})

const defaultSettings = {
  language: 'System Default',
  alias: '',
  interactiveAccess: 'confirm',
  tcpTunneling: true,
  privacyMode: false,
  autoRecord: false,
  directConnection: true,
  alwaysRelay: false,
  directIP: false,
  wakeOnLan: false,
  httpProxy: '',
  signalingServer: '',
  stunServers: 'stun:stun.l.google.com:19302\nstun:stun1.l.google.com:19302',
  turnServers: '',
  sshAccess: false,
  sshPort: 22,
  sshKeys: ''
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

// ─── Theme ──────────────────────────────────────────────
watchEffect(() => {
  if (isLightMode.value) {
    document.body.classList.add('theme-light')
  } else {
    document.body.classList.remove('theme-light')
  }
})

const isValidCode = computed(() => {
  const val = sessionCode.value.trim()
  if (!val) return false
  // Standard 9-digit check
  const digitsOnly = val.replace(/[-\s]/g, '')
  if (/^\d{9}$/.test(digitsOnly)) return true
  // Allow IP addresses or aliases (minimum 3 chars)
  return val.length >= 3
})

function formatCode(e) {
  let v = e.target.value
  const input = e.target
  const selectionStart = input.selectionStart

  // If input contains letters or dots, it's an IP/Alias. Don't format it.
  if (/[a-zA-Z\.]/.test(v)) {
    sessionCode.value = v
    return
  }

  // Otherwise, if it's mostly digits, format as 9-digit XXX-XXX-XXX
  let digits = v.replace(/[^\d]/g, '')
  if (digits.length > 9) digits = digits.slice(0, 9)
  
  let formatted = ''
  if (digits.length > 0) formatted += digits.slice(0, 3)
  if (digits.length > 3) formatted += '-' + digits.slice(3, 6)
  if (digits.length > 6) formatted += '-' + digits.slice(6, 9)
  
  // Only update ref if value changed to prevent cursor jumping
  if (sessionCode.value !== formatted) {
    sessionCode.value = formatted
    
    // Restore cursor position roughly
    nextTick(() => {
      input.setSelectionRange(selectionStart, selectionStart)
    })
  }
}

async function joinSession() {
  if (!isValidCode.value || isLoading.value) return
  isLoading.value = true; errorMsg.value = ''
  try {
    const r = await fetch('/api/session/join/', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({code:sessionCode.value}) })
    const d = await r.json()
    if (!r.ok) throw new Error(d.code?.[0]||d.detail||d.error||'Session not found')
    
    // Add to local history
    if (d.session) {
      addToHistory(d.session)
    }
    
    router.push({name:'Session',params:{code:sessionCode.value}})
  } catch(e) { errorMsg.value = e.message; setTimeout(()=>errorMsg.value='',4000) }
  finally { isLoading.value = false }
}

function copyAddress() { navigator.clipboard?.writeText(myAddress.value.replace(/\s/g,'')) }
</script>

<style>
/* CSS Variables for Light/Dark mode applied globally */
:root {
  --ad-bg-dark: #2b2b2b;
  --ad-topbar-dark: #3c3c3c;
  --ad-surface-dark: #353535;
  --ad-border-dark: #4a4a4a;
  --ad-text-dark: #ffffff;
  --ad-text-muted-dark: rgba(255,255,255,0.5);
  
  --ad-bg: var(--ad-bg-dark);
  --ad-topbar: var(--ad-topbar-dark);
  --ad-surface: var(--ad-surface-dark);
  --ad-border: var(--ad-border-dark);
  --ad-text: var(--ad-text-dark);
  --ad-text-muted: var(--ad-text-muted-dark);
}

body.theme-light {
  --ad-bg: #f5f5f5;
  --ad-topbar: #ffffff;
  --ad-surface: #ffffff;
  --ad-border: #e0e0e0;
  --ad-text: #333333;
  --ad-text-muted: #757575;
}
</style>

<style scoped>
.app { display:flex; flex-direction:column; min-height:100vh; background:var(--ad-bg); color:var(--ad-text); }

/* ═══ Top Bar ═══ */
.topbar {
  display:flex; align-items:center; height:42px; background:var(--ad-topbar);
  padding:0 12px; gap:12px; flex-shrink:0; color:var(--ad-text); border-bottom:1px solid var(--ad-border);
}
.topbar__left { display:flex; align-items:center; gap:8px; flex:1; min-width:0; }
.topbar__logo { width:28px; height:28px; display:flex; align-items:center; justify-content:center; background:var(--color-accent-primary); border-radius:6px; flex-shrink:0; }
.topbar__logo svg { stroke: white; }
.topbar__connect { display:flex; align-items:center; gap:6px; flex:1; min-width:0; background:rgba(128,128,128,0.15); border-radius:6px; padding:0 10px; height:30px; }
.topbar__status-icon { display:flex; align-items:center; }
.topbar__input { flex:1; background:none; border:none; color:var(--ad-text); font-family:var(--font-sans); font-size:0.82rem; outline:none; min-width:0; }
.topbar__input::placeholder { color:var(--ad-text-muted); }

.topbar__center { display:flex; align-items:center; gap:8px; flex-shrink:0; }
.topbar__label { font-size:0.72rem; color:var(--ad-text-muted); }
.topbar__address { font-size:1rem; font-weight:700; color:var(--color-accent-primary); letter-spacing:0.04em; }

.topbar__right { display:flex; align-items:center; gap:4px; flex-shrink:0; }

.topbar__icon-btn { background:none; border:none; color:var(--ad-text-muted); cursor:pointer; padding:4px; border-radius:4px; display:flex; align-items:center; transition:all 150ms; }
.topbar__icon-btn:hover { color:var(--ad-text); background:rgba(128,128,128,0.2); }

.topbar__connect-btn { width:30px; height:30px; display:flex; align-items:center; justify-content:center; background:var(--color-accent-primary); border:none; border-radius:6px; color:white; cursor:pointer; flex-shrink:0; transition:all 150ms; }
.topbar__connect-btn:hover:not(:disabled) { background:var(--color-accent-primary-hover); }
.topbar__connect-btn:disabled { opacity:0.35; cursor:not-allowed; }

.spinner-sm { width:14px; height:14px; border:2px solid rgba(255,255,255,0.3); border-top-color:white; border-radius:50%; animation:spin 0.6s linear infinite; }

.global-error { margin:0; padding:4px 16px; font-size:0.78rem; color:white; background:var(--color-accent-red); text-align:center; }

/* ═══ Main ═══ */
.main { flex:1; display:flex; flex-direction:column; overflow:hidden; }
.page-enter-active { animation:fade-in 0.2s ease-out; }
.page-leave-active { animation:fade-in 0.12s ease-in reverse; }

/* ═══ Settings Modal ═══ */
.settings-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; z-index:100; backdrop-filter:blur(2px); animation:fade-in 0.2s ease-out; }
.settings-modal { width:800px; height:600px; max-width:90vw; max-height:90vh; background:var(--ad-surface); border:1px solid var(--ad-border); border-radius:8px; box-shadow:0 12px 32px rgba(0,0,0,0.3); display:flex; overflow:hidden; }

/* Settings Sidebar */
.settings-sidebar { width:220px; background:var(--ad-bg); border-right:1px solid var(--ad-border); display:flex; flex-direction:column; padding:16px 0; }
.settings-sidebar__title { font-size:0.9rem; font-weight:700; color:var(--ad-text-muted); padding:0 20px 16px 20px; text-transform:uppercase; letter-spacing:0.05em; }
.st-tab { padding:12px 20px; text-align:left; background:none; border:none; font-size:0.85rem; font-weight:500; color:var(--ad-text); cursor:pointer; transition:all 150ms; border-left:3px solid transparent; }
.st-tab:hover { background:rgba(128,128,128,0.1); }
.st-tab--active { color:var(--color-accent-primary); border-left-color:var(--color-accent-primary); background:rgba(128,128,128,0.05); }
.st-divider { height:1px; background:var(--ad-border); margin:8px 20px; }

/* Settings Content */
.settings-content { flex:1; display:flex; flex-direction:column; background:var(--ad-surface); min-width:0; }
.settings-header { display:flex; justify-content:space-between; align-items:center; padding:20px 24px; border-bottom:1px solid var(--ad-border); }
.settings-header h2 { font-size:1.2rem; font-weight:600; color:var(--ad-text); margin:0; }
.settings-close { background:none; border:none; color:var(--ad-text-muted); cursor:pointer; display:flex; padding:4px; border-radius:4px; transition:150ms; }
.settings-close:hover { color:var(--ad-text); background:rgba(128,128,128,0.2); }

.settings-body { flex:1; overflow-y:auto; padding:24px; }
.st-section { display:flex; flex-direction:column; gap:20px; animation:slide-up 0.3s ease-out; }
.st-group { display:flex; flex-direction:column; gap:8px; }
.st-row { flex-direction:row; justify-content:space-between; align-items:center; }
.st-text label { font-size:0.9rem; font-weight:600; color:var(--ad-text); margin-bottom:4px; display:block; }
.st-group > label { font-size:0.9rem; font-weight:600; color:var(--ad-text); }
.st-hint { font-size:0.75rem; color:var(--ad-text-muted); }

.st-input { padding:8px 12px; font-size:0.85rem; background:var(--ad-bg); color:var(--ad-text); border:1px solid var(--ad-border); border-radius:4px; outline:none; transition:150ms; }
.st-input:focus { border-color:var(--color-accent-primary); }

.st-btn { padding:8px 16px; font-size:0.85rem; font-weight:600; border:none; border-radius:4px; cursor:pointer; transition:150ms; }
.st-btn--primary { background:var(--color-accent-primary); color:white; }
.st-btn--primary:hover { background:var(--color-accent-primary-hover); }

/* License Card */
.st-license-card { background:linear-gradient(135deg, rgba(211,47,47,0.1), rgba(211,47,47,0.02)); border:1px solid var(--color-accent-primary); border-radius:8px; padding:20px; display:flex; flex-direction:column; gap:8px; align-items:flex-start; }
.st-license-card h4 { font-size:1.1rem; font-weight:700; color:var(--color-accent-primary); margin:0; }
.st-license-card p { font-size:0.85rem; color:var(--ad-text); margin:0; }

/* Toggles */
.toggle { position:relative; width:36px; height:20px; flex-shrink:0; }
.toggle input { opacity:0; width:0; height:0; }
.toggle__slider { position:absolute; inset:0; background:var(--ad-border); border-radius:10px; cursor:pointer; transition:250ms; }
.toggle__slider::before { content:''; position:absolute; height:14px; width:14px; left:3px; bottom:3px; background:white; border-radius:50%; transition:250ms; box-shadow:0 1px 3px rgba(0,0,0,0.2); }
.toggle input:checked + .toggle__slider { background:#d32f2f; }
.toggle input:checked + .toggle__slider::before { transform:translateX(16px); }

/* Animations */
@keyframes slide-up { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
