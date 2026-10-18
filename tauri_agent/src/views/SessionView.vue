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
      @toggle-terminal="showTerminal = !showTerminal"
      @toggle-files="showFiles = !showFiles"
      @toggle-chat="toggleChat"
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
        :offer-received="webrtc.offerReceived.value"
      />

      <!-- Stats Overlay -->
      <StatsOverlay
        :visible="showStats"
        :stats="webrtc.stats"
        :current-quality="webrtc.currentQuality.value"
        @close="showStats = false"
        @quality-change="webrtc.setQuality($event)"
      />

      <!-- Interactive Shell / Terminal -->
      <TerminalPanel
        :visible="showTerminal"
        :webrtc="webrtc"
        @close="showTerminal = false"
      />

      <!-- File Transfer Panel -->
      <FileTransfer
        :visible="showFiles"
        :file-channel="webrtc.fileChannel.value"
        @close="showFiles = false"
      />

      <!-- In-Session Chat Panel -->
      <ChatPanel
        :visible="showChat"
        :messages="webrtc.chatMessages.value"
        @close="showChat = false"
        @send="webrtc.sendChat($event)"
      />

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSignaling } from '../composables/useSignaling.js'
import { useWebRTC } from '../composables/useWebRTC.js'
import { useDevice } from '../composables/useDevice.js'
import RemoteScreen from '../components/RemoteScreen.vue'
import ConnectionPanel from '../components/ConnectionPanel.vue'
import Toolbar from '../components/Toolbar.vue'
import StatsOverlay from '../components/StatsOverlay.vue'
import TerminalPanel from '../components/TerminalPanel.vue'
import FileTransfer from '../components/FileTransfer.vue'
import ChatPanel from '../components/ChatPanel.vue'
import { loadNetworkSettings } from '../composables/serverConfig.js'

const props = defineProps({
  code: {
    type: String,
    required: true,
  },
})

const router = useRouter()
const screenContainer = ref(null)

const showStats = ref(false)
const showTerminal = ref(false)
const showFiles = ref(false)
const showChat = ref(false)

function toggleChat() {
  showChat.value = !showChat.value
  webrtc.setChatVisible(showChat.value)
}

// ─── Initialize composables ────────────────────────────────
const device = useDevice()
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
    signaling.register('client', '', {
      client_device_id: device.deviceId.value || 'Remote Client',
      caller_name: device.deviceName.value || 'Remote Controller',
    })
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

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    screenContainer.value?.requestFullscreen()
  } else {
    document.exitFullscreen()
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
