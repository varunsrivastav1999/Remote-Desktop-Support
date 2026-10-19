<template>
  <div
    :class="[
      'remote-screen',
      { 'remote-screen--controlling': isControlling, 'remote-screen--viewonly': !isControlling }
    ]"
    ref="container"
    tabindex="0"
    @mousedown="handleMouse('mousedown', $event)"
    @mouseup="handleMouse('mouseup', $event)"
    @mousemove="handleMouse('mousemove', $event)"
    @dblclick.prevent="handleMouse('dblclick', $event)"
    @contextmenu.prevent="handleMouse('contextmenu', $event)"
    @wheel.prevent="handleWheel"
    @keydown.prevent="handleKey('keydown', $event)"
    @keyup.prevent="handleKey('keyup', $event)"
    @mouseleave="handleMouseLeave"
  >
    <video
      ref="videoEl"
      class="remote-screen__video"
      autoplay
      playsinline
      muted
      @loadedmetadata="onLoadedMetadata"
      @canplay="onCanPlay"
    ></video>

    <!-- Real-time controller pointer indicator (active when controlling) -->
    <div
      v-if="isControlling && pointerPos.visible"
      :class="['remote-pointer-marker', { 'remote-pointer-marker--clicking': pointerPos.clicking }]"
      :style="{ left: pointerPos.x + 'px', top: pointerPos.y + 'px' }"
    ></div>

    <!-- Active Control floating banner -->
    <div v-if="isControlling" class="screen-indicator screen-indicator--active">
      <span class="beacon-dot"></span>
      <span>CONTROL ACTIVE &bull; Remote mouse & keyboard enabled</span>
    </div>

    <!-- View Only persistent header indicator -->
    <div v-else class="screen-indicator screen-indicator--view">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
      <span>VIEW ONLY &bull; Click "Take Control" to interact</span>
    </div>

    <!-- Click-triggered View-Only Warning/Action Banner -->
    <transition name="toast-fade">
      <div v-if="!isControlling && showViewOnlyNotice" class="view-only-toast">
        <div class="view-only-toast__body">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
          <div class="view-only-toast__text">
            <strong>View Only Mode</strong>
            <p>Mouse and keyboard events are disabled. Click Take Control to interact with the remote screen.</p>
          </div>
          <button class="btn-toast-take" @click.stop="$emit('take-control')">
            Take Control
          </button>
          <button class="btn-toast-close" @click.stop="showViewOnlyNotice = false" title="Dismiss">
            ✕
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  stream: {
    type: MediaStream,
    default: null,
  },
  isControlling: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['mouse-event', 'key-event', 'clipboard-paste', 'take-control'])

const container = ref(null)
const videoEl = ref(null)
const showViewOnlyNotice = ref(false)
let noticeTimer = null

const pointerPos = reactive({
  x: 0,
  y: 0,
  visible: false,
  clicking: false,
})

// Throttle mousemove events to ~60fps
let lastMoveTime = 0
const MOVE_THROTTLE_MS = 16

watch(
  () => props.isControlling,
  (controlling) => {
    if (controlling) {
      showViewOnlyNotice.value = false
      if (noticeTimer) {
        clearTimeout(noticeTimer)
        noticeTimer = null
      }
      nextTick(() => {
        container.value?.focus()
      })
    }
  }
)

function handleMouseLeave() {
  pointerPos.visible = false
  pointerPos.clicking = false
}

function attachStream(stream) {
  if (!videoEl.value) return
  try {
    videoEl.value.muted = true
    if (videoEl.value.srcObject !== stream) {
      console.log('[RemoteScreen] Attaching remote stream:', stream)
      videoEl.value.srcObject = stream || null
    }
    if (stream) {
      stream.getVideoTracks().forEach(track => {
        track.enabled = true
        track.onunmute = () => {
          console.log('[RemoteScreen] Remote video track unmuted')
          if (videoEl.value) {
            videoEl.value.play().catch(e => console.warn('[RemoteScreen] Play on unmute:', e))
          }
        }
      })
      const p = videoEl.value.play()
      if (p !== undefined) {
        p.catch(e => console.warn('[RemoteScreen] Video play failed:', e))
      }
    }
  } catch (err) {
    console.error('[RemoteScreen] Error attaching stream:', err)
  }
}

function onLoadedMetadata() {
  console.log('[RemoteScreen] Video metadata loaded:', videoEl.value?.videoWidth, 'x', videoEl.value?.videoHeight)
  if (videoEl.value) {
    videoEl.value.play().catch(e => console.warn('[RemoteScreen] Play on loadedmetadata:', e))
  }
}

function onCanPlay() {
  if (videoEl.value) {
    videoEl.value.play().catch(e => console.warn('[RemoteScreen] Play on canplay:', e))
  }
}

watch(
  () => props.stream,
  (newStream) => {
    attachStream(newStream)
  }
)

onMounted(() => {
  attachStream(props.stream)
  nextTick(() => {
    attachStream(props.stream)
    if (props.isControlling) {
      container.value?.focus()
    }
  })
})

onUnmounted(() => {
  if (noticeTimer) clearTimeout(noticeTimer)
  if (videoEl.value) {
    videoEl.value.srcObject = null
  }
})

/**
 * Calculates normalized coordinates (0..1) accounting for CSS object-fit: contain letterboxing.
 */
function getRelativeCoordinates(event) {
  const video = videoEl.value
  if (!video) return null
  const rect = video.getBoundingClientRect()
  if (!rect.width || !rect.height) return null

  const videoWidth = video.videoWidth || rect.width
  const videoHeight = video.videoHeight || rect.height

  const videoRatio = videoWidth / videoHeight
  const elemRatio = rect.width / rect.height

  let renderedWidth = rect.width
  let renderedHeight = rect.height
  let offsetX = 0
  let offsetY = 0

  if (videoRatio > elemRatio) {
    renderedHeight = rect.width / videoRatio
    offsetY = (rect.height - renderedHeight) / 2
  } else {
    renderedWidth = rect.height * videoRatio
    offsetX = (rect.width - renderedWidth) / 2
  }

  const clientX = event.clientX
  const clientY = event.clientY

  const x = (clientX - rect.left - offsetX) / renderedWidth
  const y = (clientY - rect.top - offsetY) / renderedHeight

  return {
    x: Math.max(0, Math.min(1, x)),
    y: Math.max(0, Math.min(1, y)),
  }
}

/**
 * Convert mouse event to relative coordinates and emit.
 */
function handleMouse(type, event) {
  if (!props.isControlling) {
    // In View-Only mode: block all mouse input from reaching remote host
    if (type === 'mousedown' || type === 'click') {
      showViewOnlyNotice.value = true
      if (noticeTimer) clearTimeout(noticeTimer)
      noticeTimer = setTimeout(() => {
        showViewOnlyNotice.value = false
      }, 4000)
    }
    return
  }

  container.value?.focus()

  // Track pointer marker position relative to container
  if (container.value) {
    const cRect = container.value.getBoundingClientRect()
    pointerPos.x = event.clientX - cRect.left
    pointerPos.y = event.clientY - cRect.top
    pointerPos.visible = true
    if (type === 'mousedown') pointerPos.clicking = true
    if (type === 'mouseup') pointerPos.clicking = false
  }

  // Throttle mousemove to ~60fps
  if (type === 'mousemove') {
    const now = performance.now()
    if (now - lastMoveTime < MOVE_THROTTLE_MS) return
    lastMoveTime = now
  }

  const coords = getRelativeCoordinates(event)
  if (!coords) return

  let btn = event.button
  if (type === 'contextmenu') {
    btn = 2
  }

  emit('mouse-event', {
    type,
    x: coords.x,
    y: coords.y,
    extra: {
      button: btn,
    },
  })
}

/**
 * Handle scroll/wheel events.
 */
function handleWheel(event) {
  if (!props.isControlling) return

  const coords = getRelativeCoordinates(event)
  if (!coords) return

  emit('mouse-event', {
    type: 'scroll',
    x: coords.x,
    y: coords.y,
    extra: {
      deltaX: event.deltaX,
      deltaY: event.deltaY,
    },
  })
}

/**
 * Handle keyboard events.
 * Intercepts Ctrl+V to sync clipboard to host.
 */
function handleKey(type, event) {
  if (!props.isControlling) return

  // Intercept Ctrl+V / Cmd+V to sync clipboard
  if (type === 'keydown' && event.key === 'v' && (event.ctrlKey || event.metaKey)) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.readText().then(text => {
        if (text) {
          emit('clipboard-paste', text)
        }
      }).catch(() => {})
    }
  }

  emit('key-event', {
    type,
    key: event.key,
    modifiers: {
      ctrl: event.ctrlKey,
      shift: event.shiftKey,
      alt: event.altKey,
      meta: event.metaKey,
    },
  })
}
</script>

<style scoped>
.remote-screen {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  outline: none;
  position: relative;
  overflow: hidden;
  user-select: none;
  transition: box-shadow 0.3s ease;
}

.remote-screen--viewonly {
  cursor: default;
}

.remote-screen--controlling {
  cursor: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24'%3E%3Cpath fill='%23ffffff' stroke='%23000000' stroke-width='1.5' stroke-linejoin='round' d='M3 3l7.5 18 2.5-6.5L19.5 12z'/%3E%3C/svg%3E") 0 0, default;
  box-shadow: inset 0 0 0 2px rgba(16, 185, 129, 0.5), inset 0 0 20px rgba(16, 185, 129, 0.15);
}

.remote-screen__video {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  pointer-events: none;
}

/* Controller Pointer Indicator */
.remote-pointer-marker {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.95);
  background: rgba(16, 185, 129, 0.6);
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.9), 0 0 2px #000;
  transform: translate(-50%, -50%);
  pointer-events: none;
  z-index: 30;
  transition: width 0.08s ease, height 0.08s ease, background-color 0.08s ease;
}

.remote-pointer-marker--clicking {
  width: 18px;
  height: 18px;
  background: rgba(16, 185, 129, 0.95);
  box-shadow: 0 0 14px rgba(16, 185, 129, 1), 0 0 2px #000;
}

/* Top Floating Indicator */
.screen-indicator {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 14px;
  font-size: 0.72rem;
  font-weight: 600;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  gap: 7px;
  pointer-events: none;
  z-index: 25;
  letter-spacing: 0.04em;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  user-select: none;
}

.screen-indicator--active {
  background: rgba(16, 185, 129, 0.2);
  border: 1px solid rgba(16, 185, 129, 0.5);
  color: #34d399;
  box-shadow: 0 2px 10px rgba(16, 185, 129, 0.2);
}

.screen-indicator--view {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.6);
}

.beacon-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 6px #34d399;
  animation: beacon-pulse 1.5s infinite;
}

@keyframes beacon-pulse {
  0% { transform: scale(0.9); opacity: 0.7; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.7; }
}

/* View-Only Interactive Warning Toast */
.view-only-toast {
  position: absolute;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 40;
  max-width: 90%;
  width: 480px;
}

.view-only-toast__body {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(17, 24, 39, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(59, 130, 246, 0.4);
  border-radius: 10px;
  padding: 10px 16px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6), 0 0 15px rgba(59, 130, 246, 0.2);
  color: white;
}

.view-only-toast__text {
  flex: 1;
}

.view-only-toast__text strong {
  display: block;
  font-size: 0.82rem;
  color: #93c5fd;
  margin-bottom: 2px;
}

.view-only-toast__text p {
  margin: 0;
  font-size: 0.76rem;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.3;
}

.btn-toast-take {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border: none;
  font-size: 0.78rem;
  font-weight: 700;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.35);
}

.btn-toast-take:hover {
  background: linear-gradient(135deg, #34d399 0%, #10b981 100%);
  transform: translateY(-1px);
}

.btn-toast-close {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.4);
  font-size: 0.9rem;
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}

.btn-toast-close:hover {
  color: white;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, 15px);
}
</style>
