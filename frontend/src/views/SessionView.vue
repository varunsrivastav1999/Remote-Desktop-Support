<template>
  <div class="session">
    <!-- Toolbar -->
    <Toolbar
      :connection-state="webrtc.connectionState.value"
      :data-channel-state="webrtc.dataChannelState.value"
      :session-code="code"
      @disconnect="handleDisconnect"
      @fullscreen="toggleFullscreen"
    />

    <!-- Remote Screen -->
    <div class="session__screen" ref="screenContainer">
      <RemoteScreen
        v-if="webrtc.connectionState.value === 'connected'"
        :stream="webrtc.remoteStream.value"
        @mouse-event="handleMouseEvent"
        @key-event="handleKeyEvent"
      />

      <!-- Connection Status Overlay -->
      <ConnectionPanel
        v-else
        :state="webrtc.connectionState.value"
        :ice-state="webrtc.iceState.value"
        :session-code="code"
        :signaling-connected="signaling.isConnected.value"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSignaling } from '../composables/useSignaling.js'
import { useWebRTC } from '../composables/useWebRTC.js'
import RemoteScreen from '../components/RemoteScreen.vue'
import ConnectionPanel from '../components/ConnectionPanel.vue'
import Toolbar from '../components/Toolbar.vue'

const props = defineProps({
  code: {
    type: String,
    required: true,
  },
})

const router = useRouter()
const screenContainer = ref(null)

// ─── Initialize composables ────────────────────────────────
const signaling = useSignaling()
const webrtc = useWebRTC(signaling)

// ─── Lifecycle ─────────────────────────────────────────────
onMounted(() => {
  // Connect to the signaling server
  signaling.connect(props.code)

  signaling.onOpen(() => {
    // Register as client (viewer/controller)
    signaling.register('client')
    
    // Load network settings from localStorage
    let settings = {}
    try {
      const stored = localStorage.getItem('ad_settings')
      if (stored) settings = JSON.parse(stored)
    } catch (e) {}

    // Initialize WebRTC with custom STUN/TURN servers
    webrtc.initAsClient(settings)
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
  height: calc(100vh - 60px); /* Subtract header */
  overflow: hidden;
}

.session__screen {
  flex: 1;
  position: relative;
  background: var(--color-bg-deep);
  overflow: hidden;
}
</style>
