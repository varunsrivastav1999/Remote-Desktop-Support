<template>
  <div class="host">
    <div class="host__header">
      <button class="btn btn--ghost" @click="leave">Back</button>
      <h1>Share This Desk</h1>

      <!-- In-Session Chat Button for Host -->
      <button
        v-if="session.state.value === 'connected' || session.chatMessages.value.length > 0"
        class="btn btn--secondary btn--icon chat-toggle"
        @click="toggleChat"
        title="Session Chat"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span>Chat</span>
        <span v-if="session.unreadCount.value > 0" class="chat-badge">{{ session.unreadCount.value }}</span>
      </button>

      <button v-if="session.localStream.value" class="btn btn--danger" @click="stopSharing">Stop Sharing</button>
    </div>

    <div class="host__content">
      <section class="share-card">
        <p class="label">Your Remote Address</p>
        <p class="code font-mono">{{ formattedCode }}</p>
        <p class="status">
          <span :class="['status-dot', statusDot]"></span>
          {{ session.statusText.value }}
        </p>

        <!-- Native Control Agent Status -->
        <div class="agent-status-badge" :class="session.hasAgent.value ? 'agent-status-badge--active' : 'agent-status-badge--warn'">
          <span class="agent-status-indicator"></span>
          <span>{{ session.hasAgent.value ? 'Native Remote Control Active (Clicks, Keys & Terminal Enabled)' : 'Remote Control Companion Offline' }}</span>
        </div>

        <!-- 1-Click Launch Command for Browser Host -->
        <div v-if="!session.hasAgent.value && session.sessionCode.value" class="agent-launcher-box">
          <p class="agent-launcher-title">To enable mouse, keyboard, and terminal control on this computer:</p>
          <div class="agent-launcher-command">
            <code class="font-mono">{{ agentCommand }}</code>
            <button class="btn btn--xs btn--secondary" @click="copyAgentCommand">
              {{ copiedCmd ? 'Copied!' : 'Copy' }}
            </button>
          </div>
          <p class="agent-launcher-hint">Run this in your terminal. It connects automatically to this desk.</p>
        </div>

        <button v-if="!session.localStream.value" class="btn btn--primary btn--lg" @click="beginShare">
          Select Screen to Share
        </button>
        <button v-if="session.sessionCode.value" class="btn btn--secondary" @click="copyCode">Copy Address</button>
        <p v-if="session.error.value" class="error">{{ session.error.value }}</p>
        <p class="privacy">
          Sharing begins only after you select a screen. Remote keyboard and mouse access begins only after you approve a controller request.
        </p>
      </section>

      <section class="preview">
        <video ref="videoEl" autoplay playsinline muted></video>
        <p v-if="!session.localStream.value" class="preview__empty">Your selected screen preview appears here.</p>
        <span v-else class="preview__badge">You are sharing</span>
      </section>
    </div>

    <!-- Incoming Control Request Banner inside Host View -->
    <div v-if="session.pendingController.value && !device.incomingRequest.value" class="host-approval-banner">
      <div class="host-approval-info">
        <span class="incoming-pulse-dot"></span>
        <div>
          <h4>Incoming Control Request</h4>
          <p>
            {{ session.incomingCallerName.value || 'Remote Controller' }} ({{ session.incomingCallerId.value || 'Remote Peer' }}) is requesting to view and control this screen.
          </p>
          <p v-if="session.incomingCallerVerified.value" class="host-approval-verified">Verified device</p>
          <p v-else class="host-approval-unverified">
            Unverified: this name and Device ID were not confirmed and may be fake.
          </p>
        </div>
      </div>
      <div class="host-approval-actions">
        <button class="btn btn--danger" @click="session.denyController()">Deny</button>
        <button class="btn btn--primary" @click="handleApproveHost">{{ approvalButton }}</button>
      </div>
    </div>

    <!-- Host Side Chat Panel -->
    <ChatPanel
      :visible="showChat"
      :messages="session.chatMessages.value"
      @close="showChat = false"
      @send="handleHostSendChat"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { setHostedAddress } from '../composables/useMyAddress.js'
import { useHostSession } from '../composables/useHostSession.js'
import { useDevice } from '../composables/useDevice.js'
import { apiUrl, isNativeApp } from '../composables/serverConfig.js'
import ChatPanel from '../components/ChatPanel.vue'

const router = useRouter()
const videoEl = ref(null)
const session = useHostSession()
const device = useDevice()
const nativeHost = isNativeApp()
const showChat = ref(false)

const formattedCode = computed(() => session.sessionCode.value?.replace(/-/g, ' ') || 'Connecting...')
const approvalButton = computed(() => session.localStream.value ? 'Allow Control' : 'Allow and Choose Screen')
const statusDot = computed(() => {
  if (session.state.value === 'connected') return 'status-dot--connected'
  if (session.sessionCode.value) return 'status-dot--waiting'
  return 'status-dot--offline'
})

const copiedCmd = ref(false)
function buildAgentCommand(token) {
  // The server this page talks to right now. Quick tunnel addresses change on every restart, so the
  // agent is told where to connect instead of relying on the address baked into agent.py.
  const server = new URL(apiUrl('/agent.py'), window.location.href).origin
  const code = session.sessionCode.value || ''
  return `curl -sSL ${server}/agent.py | python3 - --device ${code} --token ${token} --server ${server}`
}
// The screen may be shared with the controller, so only the copied command holds the token
const agentCommand = computed(() => buildAgentCommand('••••••••'))

function copyAgentCommand() {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(buildAgentCommand(device.agentToken.value))
    copiedCmd.value = true
    setTimeout(() => { copiedCmd.value = false }, 2500)
  }
}

watch(() => session.localStream.value, (stream, previousStream) => {
  if (videoEl.value) videoEl.value.srcObject = stream
  if (!stream && previousStream && session.sessionCode.value) {
    session.stopSharing()
  }
})

watch(() => session.state.value, (state) => {
  if (session.sessionCode.value) setHostedAddress(session.sessionCode.value, state)
})

function toggleChat() {
  showChat.value = !showChat.value
  if (showChat.value) {
    session.markChatRead()
  }
}

function handleHostSendChat(text) {
  session.sendChat(text)
}

async function beginShare() {
  await session.start()
}

function copyCode() {
  navigator.clipboard?.writeText(session.sessionCode.value)
}

function stopSharing() {
  session.stopSharing()
}

function leave() {
  session.stopSharing()
  router.push('/')
}

async function handleApproveHost() {
  if (!session.localStream.value) {
    const ok = await session.start()
    if (!ok) return
  }
  await session.allowController(true)
}

onMounted(async () => {
  if (videoEl.value && session.localStream.value) {
    videoEl.value.srcObject = session.localStream.value
  }
  await session.ensureOnline()
  if (session.sessionCode.value) setHostedAddress(session.sessionCode.value, session.state.value)
})

onUnmounted(() => {
  session.stopSharing()
})
</script>

<style scoped>
.host {
  height: calc(100vh - 42px);
  background: var(--ad-bg);
  color: var(--ad-text);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.host__header {
  height: 56px;
  padding: 10px 20px;
  border-bottom: 1px solid var(--ad-border);
  display: flex;
  gap: 18px;
  align-items: center;
}

.host__header h1 {
  font-size: 1.05rem;
  flex: 1;
}

.chat-toggle {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
}

.chat-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  font-size: 0.65rem;
  font-weight: 700;
  background: #f44336;
  color: white;
  min-width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  padding: 0 4px;
  border: 2px solid var(--ad-bg);
  animation: badge-pop 0.3s ease-out;
}

@keyframes badge-pop {
  from { transform: scale(0); }
  to { transform: scale(1); }
}

.host__content {
  flex: 1;
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 24px;
  padding: 28px;
  min-height: 0;
}

.share-card {
  background: var(--ad-surface);
  border: 1px solid var(--ad-border);
  border-radius: 12px;
  padding: 26px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 18px;
}

.label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ad-text-muted);
}

.code {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--color-accent-primary);
  letter-spacing: 0.08em;
}

.status {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--ad-text-muted);
  font-size: 0.84rem;
}

.privacy {
  margin-top: auto;
  border-top: 1px solid var(--ad-border);
  padding-top: 18px;
  color: var(--ad-text-muted);
  font-size: 0.78rem;
  line-height: 1.6;
}

.error {
  font-size: 0.8rem;
  color: #ef5350;
  line-height: 1.5;
}

.preview {
  border: 1px solid var(--ad-border);
  border-radius: 12px;
  background: #111;
  overflow: hidden;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.preview__empty {
  color: rgba(255,255,255,0.45);
  font-size: 0.9rem;
}

.preview__badge {
  position: absolute;
  top: 14px;
  left: 14px;
  color: #fff;
  background: #d32f2f;
  padding: 5px 10px;
  border-radius: 20px;
  font-size: 0.72rem;
  font-weight: 600;
}

.host-approval-banner {
  margin: 0 28px 24px;
  background: var(--ad-surface);
  border: 1px solid var(--color-accent-orange, #f57c00);
  border-radius: 12px;
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  box-shadow: 0 8px 24px rgba(245, 124, 0, 0.2);
  animation: pulse-border 2s infinite;
}

.host-approval-info {
  display: flex;
  align-items: center;
  gap: 14px;
}

.host-approval-info h4 {
  margin: 0 0 4px;
  font-size: 1rem;
  color: var(--ad-text);
}

.host-approval-info p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--ad-text-muted);
}

.host-approval-info p.host-approval-verified {
  margin-top: 4px;
  font-weight: 600;
  color: var(--ad-status-online);
}

.host-approval-info p.host-approval-unverified {
  margin-top: 4px;
  font-weight: 600;
  color: var(--color-accent-red);
}

.host-approval-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.incoming-pulse-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--color-accent-orange, #f57c00);
  box-shadow: 0 0 12px var(--color-accent-orange, #f57c00);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}

@keyframes pulse-border {
  0%, 100% { border-color: rgba(245, 124, 0, 0.5); }
  50% { border-color: rgba(245, 124, 0, 1); }
}

.agent-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 0.76rem;
  font-weight: 600;
  margin-bottom: 8px;
}

.agent-status-badge--active {
  background: rgba(76, 175, 80, 0.15);
  border: 1px solid rgba(76, 175, 80, 0.4);
  color: #81c784;
}

.agent-status-badge--warn {
  background: rgba(255, 152, 0, 0.12);
  border: 1px solid rgba(255, 152, 0, 0.35);
  color: #ffb74d;
}

.agent-status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.agent-launcher-box {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 12px;
  text-align: left;
}

.agent-launcher-title {
  margin: 0 0 8px;
  font-size: 0.78rem;
  font-weight: 600;
  color: #e0e0e0;
}

.agent-launcher-command {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(0, 0, 0, 0.4);
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.agent-launcher-command code {
  flex: 1;
  font-size: 0.72rem;
  color: #64b5f6;
  overflow-x: auto;
  white-space: nowrap;
}

.agent-launcher-hint {
  margin: 6px 0 0;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.4);
}
</style>
