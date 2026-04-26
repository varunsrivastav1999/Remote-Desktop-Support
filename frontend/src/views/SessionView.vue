<template>
  <div class="session">
    <!-- Toolbar -->
    <Toolbar
      :connection-state="webrtc.connectionState.value"
      :data-channel-state="webrtc.dataChannelState.value"
      :session-code="code"
      :host-info="webrtc.hostInfo.value"
      :monitors="webrtc.monitors.value"
      :current-monitor="webrtc.currentMonitor.value"
      :unread-count="webrtc.unreadCount.value"
      @disconnect="handleDisconnect"
      @fullscreen="toggleFullscreen"
      @toggle-stats="showStats = !showStats"
      @toggle-chat="toggleChat"
      @toggle-files="showFiles = !showFiles"
      @clipboard-sync="syncClipboard"
      @switch-monitor="webrtc.switchMonitor($event)"
    />

    <!-- Remote Screen -->
    <div class="session__screen" ref="screenContainer">
      <RemoteScreen
        v-if="webrtc.connectionState.value === 'connected'"
        :stream="webrtc.remoteStream.value"
        @mouse-event="handleMouseEvent"
        @key-event="handleKeyEvent"
        @clipboard-paste="webrtc.sendClipboard($event)"
      />

      <!-- Connection Status Overlay -->
      <ConnectionPanel
        v-else
        :state="webrtc.connectionState.value"
        :ice-state="webrtc.iceState.value"
        :session-code="code"
        :signaling-connected="signaling.isConnected.value"
      />

      <!-- Stats Overlay -->
      <StatsOverlay
        :visible="showStats"
        :stats="webrtc.stats"
        :current-quality="webrtc.currentQuality.value"
        @close="showStats = false"
        @quality-change="webrtc.setQuality($event)"
      />

      <!-- Chat Panel -->
      <ChatPanel
        :visible="showChat"
        :messages="webrtc.chatMessages.value"
        @close="showChat = false"
        @send="webrtc.sendChat($event)"
      />

      <!-- File Transfer Panel -->
      <FileTransfer
        :visible="showFiles"
        :file-channel="webrtc.fileChannel.value"
        @close="showFiles = false"
      />

      <!-- Auth Overlay -->
      <div v-if="webrtc.authRequired.value" class="auth-overlay fade-in">
        <div class="auth-card">
          <div class="auth-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
          </div>
          <h3>Authentication Required</h3>
          <p>Please enter the password to access this host.</p>
          <div class="auth-input-group">
            <input type="password" v-model="passwordInput" @keydown.enter="submitAuth" placeholder="Password" class="st-input" autofocus />
            <button @click="submitAuth" class="st-btn st-btn--primary">Unlock</button>
          </div>
          <p v-if="webrtc.authFailed.value" class="auth-error fade-in">Incorrect password. Please try again.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSignaling } from '../composables/useSignaling.js'
import { useWebRTC } from '../composables/useWebRTC.js'
import RemoteScreen from '../components/RemoteScreen.vue'
import ConnectionPanel from '../components/ConnectionPanel.vue'
import Toolbar from '../components/Toolbar.vue'
import StatsOverlay from '../components/StatsOverlay.vue'
import ChatPanel from '../components/ChatPanel.vue'
import FileTransfer from '../components/FileTransfer.vue'

const props = defineProps({
  code: {
    type: String,
    required: true,
  },
})

const router = useRouter()
const screenContainer = ref(null)

// Panel visibility
const showStats = ref(false)
const showChat = ref(false)
const showFiles = ref(false)

// Auth state
const passwordInput = ref('')

// ─── Initialize composables ────────────────────────────────
const signaling = useSignaling()
const webrtc = useWebRTC(signaling)

// ─── Lifecycle ─────────────────────────────────────────────
onMounted(() => {
  const settings = loadNetworkSettings()

  // Initialize WebRTC before registering so early peer/offer messages are handled.
  webrtc.initAsClient(settings)

  // Connect to the signaling server
  signaling.connect(props.code, settings.signalingServer || '')

  signaling.onOpen(() => {
    // Register as client (viewer/controller)
    signaling.register('client')
  })

  signaling.onClose((event) => {
    if (event.code !== 1000) {
      console.warn('[Session] Signaling connection lost unexpectedly')
    }
  })
})

onUnmounted(() => {
  webrtc.close()
  signaling.disconnect()
})

// Track chat visibility for unread counter
watch(showChat, (visible) => {
  webrtc.setChatVisible(visible)
})

// ─── Event Handlers ────────────────────────────────────────
function handleMouseEvent(event) {
  webrtc.sendMouseEvent(event.type, event.x, event.y, event.extra || {})
}

function handleKeyEvent(event) {
  webrtc.sendKeyEvent(event.type, event.key, event.modifiers || {})
}

function handleDisconnect() {
  webrtc.close()
  signaling.disconnect()
  router.push('/')
}

function submitAuth() {
  if (passwordInput.value) {
    webrtc.sendAuth(passwordInput.value)
    passwordInput.value = ''
  }
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    screenContainer.value?.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

function toggleChat() {
  showChat.value = !showChat.value
  if (showChat.value) showFiles.value = false // Close files if open
}

async function syncClipboard() {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      const text = await navigator.clipboard.readText()
      if (text) {
        webrtc.sendClipboard(text)
        console.log('[Session] Clipboard synced to host')
      }
    }
  } catch (e) {
    console.warn('[Session] Clipboard access denied:', e)
  }
}

function loadNetworkSettings() {
  try {
    const stored = localStorage.getItem('ad_settings')
    return stored ? JSON.parse(stored) : {}
  } catch (e) {
    return {}
  }
}
</script>

<style scoped>
.session {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 42px);
  overflow: hidden;
}

.session__screen {
  flex: 1;
  position: relative;
  background: #000;
  overflow: hidden;
}

.auth-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(5px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.auth-card {
  background: var(--ad-surface);
  border: 1px solid var(--ad-border);
  border-radius: 12px;
  padding: 32px;
  width: 360px;
  text-align: center;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
}

.auth-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ad-text);
}

.auth-card h3 {
  margin: 0 0 8px;
  font-size: 1.25rem;
  color: var(--ad-text);
}

.auth-card p {
  font-size: 0.85rem;
  color: var(--ad-text-muted);
  margin: 0 0 24px;
}

.auth-input-group {
  display: flex;
  gap: 8px;
}

.auth-input-group .st-input {
  flex: 1;
}

.auth-error {
  color: var(--color-accent-red) !important;
  margin: 12px 0 0 !important;
  font-size: 0.8rem !important;
}
</style>
